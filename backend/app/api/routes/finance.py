from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.finance import Account, Budget, Category, FinancialAsset, Liability, Transaction
from app.models.sync import SyncEvent, UserSyncState
from app.models.user import User
from app.schemas.finance import (
    AccountCreate,
    AccountOut,
    BudgetCreate,
    BudgetOut,
    CategoryCreate,
    CategoryOut,
    CurrencyTotals,
    FinanceSummaryOut,
    FinancialRecordCreate,
    FinancialRecordOut,
    TransactionCreate,
    TransactionOut,
    SyncAccountInput,
    SyncCategoryInput,
    SyncEventOut,
    SyncItemResult,
    SyncPullOut,
    SyncPushInput,
    SyncPushOut,
    SyncTransactionInput,
)
from app.services.ledger import (
    ZERO,
    account_balance_deltas,
    balance_sheet_totals,
    budget_spend,
    date_range_utc,
    require_currency,
    require_currency_precision,
    transaction_request_hash,
    validate_budget_category,
)
from app.services.sync import record_sync_event
from app.services.notifications import enqueue_notification

router = APIRouter(prefix="/api/finance", tags=["finance"])


def _account_out(account: Account, balance: Decimal) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        institution=account.institution,
        currency_code=account.currency_code,
        opening_balance=account.opening_balance,
        current_balance=account.opening_balance + balance,
        is_active=account.is_active,
        created_at=account.created_at,
    )


def _account_sync_data(db: Session, account: Account) -> dict:
    balance = account_balance_deltas(db, account.user_id).get(account.id, ZERO)
    return {
        "id": account.id,
        "client_id": account.client_id,
        "name": account.name,
        "account_type": account.account_type,
        "institution": account.institution,
        "currency_code": account.currency_code,
        "opening_balance": str(account.opening_balance),
        "current_balance": str(account.opening_balance + balance),
        "is_active": account.is_active,
        "sync_version": account.sync_version,
        "updated_at": account.updated_at.isoformat(),
    }


def _category_sync_data(category: Category) -> dict:
    return {
        "id": category.id,
        "client_id": category.client_id,
        "name": category.name,
        "category_type": category.category_type,
        "sync_version": category.sync_version,
        "created_at": category.created_at.isoformat(),
    }


def _transaction_sync_data(db: Session, transaction: Transaction) -> dict:
    balances = account_balance_deltas(db, transaction.user_id)
    account_ids = {transaction.account_id}
    if transaction.transfer_account_id is not None:
        account_ids.add(transaction.transfer_account_id)
    accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
    return {
        "id": transaction.id,
        "idempotency_key": transaction.idempotency_key,
        "account_id": transaction.account_id,
        "transfer_account_id": transaction.transfer_account_id,
        "category_id": transaction.category_id,
        "reversal_of_id": transaction.reversal_of_id,
        "transaction_type": transaction.transaction_type,
        "amount": str(transaction.amount),
        "currency_code": transaction.currency_code,
        "description": transaction.description,
        "notes": transaction.notes,
        "transaction_date": transaction.transaction_date.isoformat(),
        "account_balances": {
            str(account.id): str(account.opening_balance + balances.get(account.id, ZERO))
            for account in accounts
        },
    }


def _require_account(db: Session, user_id: int, account_id: int) -> Account:
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == user_id,
        Account.is_active.is_(True),
    ).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def _existing_idempotent_transaction(
    db: Session,
    user_id: int,
    payload: TransactionCreate,
    reversal_of_id: int | None,
) -> Transaction | None:
    existing = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.idempotency_key == payload.idempotency_key,
    ).first()
    if existing is None:
        return None
    expected_hash = transaction_request_hash(payload, reversal_of_id)
    if existing.request_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different transaction",
        )
    return existing


def _create_transaction(
    db: Session,
    user_id: int,
    payload: TransactionCreate,
    response: Response,
    reversal_of_id: int | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> Transaction:
    existing = _existing_idempotent_transaction(db, user_id, payload, reversal_of_id)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    account = _require_account(db, user_id, payload.account_id)
    currency = require_currency(db, payload.currency_code)
    require_currency_precision(payload.amount, currency)
    if account.currency_code != payload.currency_code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transaction currency must match its account")

    if payload.transaction_type == "TRANSFER":
        destination = _require_account(db, user_id, payload.transfer_account_id)
        if destination.currency_code != account.currency_code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transfers between different currencies are not supported",
            )
    else:
        category = db.query(Category).filter(
            Category.id == payload.category_id,
            Category.user_id == user_id,
            Category.category_type == payload.transaction_type,
        ).first()
        if category is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matching transaction category not found")

    transaction = Transaction(
        user_id=user_id,
        account_id=payload.account_id,
        transfer_account_id=payload.transfer_account_id,
        category_id=payload.category_id,
        reversal_of_id=reversal_of_id,
        idempotency_key=payload.idempotency_key,
        request_hash=transaction_request_hash(payload, reversal_of_id),
        transaction_type=payload.transaction_type,
        amount=payload.amount,
        currency_code=payload.currency_code,
        description=payload.description,
        notes=payload.notes,
        transaction_date=payload.transaction_date,
    )
    db.add(transaction)
    try:
        db.flush()
        record_sync_event(
            db,
            user_id,
            "transaction",
            transaction.id,
            _transaction_sync_data(db, transaction),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_idempotent_transaction(db, user_id, payload, reversal_of_id)
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction conflicts with an existing ledger record") from exc
    db.refresh(transaction)
    if transaction.transaction_type == "EXPENSE":
        budgets = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.currency_code == transaction.currency_code,
            Budget.start_date <= transaction.transaction_date.date(),
            Budget.end_date >= transaction.transaction_date.date(),
        ).all()
        for budget in budgets:
            if budget.category_id is not None and budget.category_id != transaction.category_id:
                continue
            spent = budget_spend(db, user_id, budget)
            for threshold in (Decimal("0.8"), Decimal("1")):
                if spent >= budget.amount * threshold:
                    percent = int(threshold * 100)
                    enqueue_notification(
                        db,
                        user_id=user_id,
                        event_type="BUDGET",
                        event_key=f"budget:{budget.id}:threshold:{percent}",
                        title=f"{budget.name} budget threshold reached",
                        body=(
                            f"Your {budget.name} budget has reached at least {percent}% "
                            f"({spent} {budget.currency_code} of {budget.amount})."
                        ),
                        background_tasks=background_tasks,
                    )
    return transaction


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).order_by(Account.created_at, Account.id).all()
    deltas = account_balance_deltas(db, current_user.id)
    return [_account_out(account, deltas.get(account.id, ZERO)) for account in accounts]


@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    currency = require_currency(db, payload.currency_code)
    require_currency_precision(payload.opening_balance.copy_abs(), currency)
    account = Account(
        user_id=current_user.id,
        sync_version=1,
        name=payload.name,
        account_type=payload.account_type,
        institution=payload.institution,
        currency_code=payload.currency_code,
        opening_balance=payload.opening_balance,
    )
    db.add(account)
    db.flush()
    record_sync_event(db, current_user.id, "account", account.id, _account_sync_data(db, account))
    db.commit()
    db.refresh(account)
    return _account_out(account, ZERO)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Category).filter(Category.user_id == current_user.id).order_by(
        Category.category_type, Category.name
    ).all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    category = Category(
        user_id=current_user.id,
        name=payload.name,
        category_type=payload.category_type,
        sync_version=1,
    )
    db.add(category)
    try:
        db.flush()
        record_sync_event(db, current_user.id, "category", category.id, _category_sync_data(category))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists") from exc
    db.refresh(category)
    return category


def _account_sync_result(
    db: Session,
    user_id: int,
    item: SyncAccountInput,
) -> SyncItemResult:
    client_id = str(item.client_id)
    account = db.query(Account).filter(
        Account.user_id == user_id,
        Account.client_id == client_id,
    ).first()
    if account is None and item.remote_id is not None:
        account = db.query(Account).filter(
            Account.user_id == user_id,
            Account.id == item.remote_id,
        ).first()
    if account is None:
        if item.remote_id is not None:
            return SyncItemResult(
                entity_type="account",
                local_id=client_id,
                status="CONFLICT",
                message="The server account no longer exists",
            )
        if item.is_deleted:
            return SyncItemResult(entity_type="account", local_id=client_id, status="APPLIED")
        if item.base_version != 0:
            return SyncItemResult(
                entity_type="account",
                local_id=client_id,
                status="CONFLICT",
                message="The server account no longer exists",
            )
        currency = require_currency(db, item.currency_code)
        require_currency_precision(item.opening_balance.copy_abs(), currency)
        account = Account(
            user_id=user_id,
            client_id=client_id,
            name=item.name,
            account_type=item.account_type,
            institution=item.institution,
            currency_code=item.currency_code,
            opening_balance=item.opening_balance,
            sync_version=1,
        )
        db.add(account)
        try:
            db.flush()
            record_sync_event(db, user_id, "account", account.id, _account_sync_data(db, account))
            db.commit()
        except IntegrityError:
            db.rollback()
            return SyncItemResult(
                entity_type="account",
                local_id=client_id,
                status="CONFLICT",
                message="Another device created this account concurrently",
            )
        return SyncItemResult(
            entity_type="account",
            local_id=client_id,
            status="APPLIED",
            remote_id=account.id,
            server_version=account.sync_version,
        )

    desired = (
        account.name == item.name
        and account.account_type == item.account_type
        and account.institution == item.institution
        and account.currency_code == item.currency_code
        and account.opening_balance == item.opening_balance
        and account.is_active != item.is_deleted
        and account.client_id == client_id
    )
    if account.sync_version != item.base_version:
        if desired:
            return SyncItemResult(
                entity_type="account",
                local_id=client_id,
                status="APPLIED",
                remote_id=account.id,
                server_version=account.sync_version,
            )
        return SyncItemResult(
            entity_type="account",
            local_id=client_id,
            status="CONFLICT",
            remote_id=account.id,
            server_version=account.sync_version,
            server_data=_account_sync_data(db, account),
            message="Account changed on the server; resolve the conflict before retrying",
        )

    if not desired:
        currency = require_currency(db, item.currency_code)
        require_currency_precision(item.opening_balance.copy_abs(), currency)
        currency_changed = account.currency_code != item.currency_code
        has_ledger_entries = db.query(Transaction.id).filter(
            (Transaction.account_id == account.id) | (Transaction.transfer_account_id == account.id)
        ).first() is not None
        if currency_changed and has_ledger_entries:
            return SyncItemResult(
                entity_type="account",
                local_id=client_id,
                status="REJECTED",
                remote_id=account.id,
                server_version=account.sync_version,
                message="Account currency cannot change after ledger entries exist",
            )
        account.name = item.name
        account.client_id = client_id
        account.account_type = item.account_type
        account.institution = item.institution
        account.currency_code = item.currency_code
        account.opening_balance = item.opening_balance
        account.is_active = not item.is_deleted
        account.sync_version += 1
        try:
            db.flush()
            record_sync_event(
                db,
                user_id,
                "account",
                account.id,
                _account_sync_data(db, account),
                operation="DELETE" if item.is_deleted else "UPSERT",
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            return SyncItemResult(
                entity_type="account",
                local_id=client_id,
                status="REJECTED",
                remote_id=account.id,
                message="Account update violates a server constraint",
            )
    return SyncItemResult(
        entity_type="account",
        local_id=client_id,
        status="APPLIED",
        remote_id=account.id,
        server_version=account.sync_version,
    )


def _category_sync_result(
    db: Session,
    user_id: int,
    item: SyncCategoryInput,
) -> SyncItemResult:
    client_id = str(item.client_id)
    category = db.query(Category).filter(
        Category.user_id == user_id,
        Category.client_id == client_id,
    ).first()
    if category is None and item.remote_id is not None:
        category = db.query(Category).filter(
            Category.user_id == user_id,
            Category.id == item.remote_id,
        ).first()
    if item.is_deleted:
        return SyncItemResult(
            entity_type="category",
            local_id=client_id,
            status="REJECTED",
            remote_id=category.id if category else None,
            message="Categories are retained to preserve ledger history",
        )
    if category is None:
        if item.remote_id is not None:
            return SyncItemResult(
                entity_type="category",
                local_id=client_id,
                status="CONFLICT",
                message="The server category no longer exists",
            )
        if item.base_version != 0:
            return SyncItemResult(
                entity_type="category",
                local_id=client_id,
                status="CONFLICT",
                message="The server category no longer exists",
            )
        category = Category(
            user_id=user_id,
            client_id=client_id,
            name=item.name,
            category_type=item.category_type,
            sync_version=1,
        )
        db.add(category)
        try:
            db.flush()
            record_sync_event(db, user_id, "category", category.id, _category_sync_data(category))
            db.commit()
        except IntegrityError:
            db.rollback()
            return SyncItemResult(
                entity_type="category",
                local_id=client_id,
                status="REJECTED",
                message="A category with this name and type already exists",
            )
        return SyncItemResult(
            entity_type="category",
            local_id=client_id,
            status="APPLIED",
            remote_id=category.id,
            server_version=category.sync_version,
        )

    desired = (
        category.name == item.name
        and category.category_type == item.category_type
        and category.client_id == client_id
    )
    if category.sync_version != item.base_version:
        if desired:
            return SyncItemResult(
                entity_type="category",
                local_id=client_id,
                status="APPLIED",
                remote_id=category.id,
                server_version=category.sync_version,
            )
        return SyncItemResult(
            entity_type="category",
            local_id=client_id,
            status="CONFLICT",
            remote_id=category.id,
            server_version=category.sync_version,
            server_data=_category_sync_data(category),
            message="Category changed on the server; resolve the conflict before retrying",
        )
    if not desired:
        if category.category_type != item.category_type and db.query(Transaction.id).filter(
            Transaction.category_id == category.id
        ).first() is not None:
            return SyncItemResult(
                entity_type="category",
                local_id=client_id,
                status="REJECTED",
                remote_id=category.id,
                server_version=category.sync_version,
                message="Category type cannot change after ledger entries use it",
            )
        category.client_id = client_id
        category.name = item.name
        category.category_type = item.category_type
        category.sync_version += 1
        try:
            db.flush()
            record_sync_event(db, user_id, "category", category.id, _category_sync_data(category))
            db.commit()
        except IntegrityError:
            db.rollback()
            return SyncItemResult(
                entity_type="category",
                local_id=client_id,
                status="REJECTED",
                remote_id=category.id,
                message="Category update violates a server constraint",
            )
    return SyncItemResult(
        entity_type="category",
        local_id=client_id,
        status="APPLIED",
        remote_id=category.id,
        server_version=category.sync_version,
    )


@router.post("/sync/push", response_model=SyncPushOut)
def push_sync_changes(
    payload: SyncPushInput,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results: list[SyncItemResult] = []
    for item in payload.accounts:
        try:
            results.append(_account_sync_result(db, current_user.id, item))
        except HTTPException as exc:
            db.rollback()
            results.append(SyncItemResult(
                entity_type="account",
                local_id=str(item.client_id),
                status="REJECTED",
                message=str(exc.detail),
            ))
    for item in payload.categories:
        try:
            results.append(_category_sync_result(db, current_user.id, item))
        except HTTPException as exc:
            db.rollback()
            results.append(SyncItemResult(
                entity_type="category",
                local_id=str(item.client_id),
                status="REJECTED",
                message=str(exc.detail),
            ))
    for item in payload.transactions:
        source_query = db.query(Account).filter(
            Account.user_id == current_user.id,
            Account.is_active.is_(True),
        )
        source = source_query.filter(
            Account.client_id == str(item.account_client_id)
        ).first() if item.account_client_id is not None else source_query.filter(
            Account.id == item.account_remote_id
        ).first()
        destination = None
        category = None
        if item.transfer_account_client_id is not None or item.transfer_account_remote_id is not None:
            destination_query = db.query(Account).filter(
                Account.user_id == current_user.id,
                Account.is_active.is_(True),
            )
            destination = destination_query.filter(
                Account.client_id == str(item.transfer_account_client_id)
            ).first() if item.transfer_account_client_id is not None else destination_query.filter(
                Account.id == item.transfer_account_remote_id
            ).first()
        if item.category_client_id is not None or item.category_remote_id is not None:
            category_query = db.query(Category).filter(Category.user_id == current_user.id)
            category = category_query.filter(
                Category.client_id == str(item.category_client_id)
            ).first() if item.category_client_id is not None else category_query.filter(
                Category.id == item.category_remote_id
            ).first()
        if source is None or (
            (item.transfer_account_client_id is not None or item.transfer_account_remote_id is not None)
            and destination is None
        ) or (
            (item.category_client_id is not None or item.category_remote_id is not None)
            and category is None
        ):
            results.append(SyncItemResult(
                entity_type="transaction",
                local_id=item.local_id,
                status="REJECTED",
                message="Sync the referenced account and category before retrying this transaction",
            ))
            continue
        transaction_payload = TransactionCreate(
            idempotency_key=item.idempotency_key,
            account_id=source.id,
            transfer_account_id=destination.id if destination else None,
            category_id=category.id if category else None,
            transaction_type=item.transaction_type,
            amount=item.amount,
            currency_code=item.currency_code,
            description=item.description,
            notes=item.notes,
            transaction_date=item.transaction_date,
        )
        response = Response()
        try:
            transaction = _create_transaction(
                db,
                current_user.id,
                transaction_payload,
                response,
                background_tasks=background_tasks,
            )
            results.append(SyncItemResult(
                entity_type="transaction",
                local_id=item.local_id,
                status="APPLIED",
                remote_id=transaction.id,
            ))
        except HTTPException as exc:
            db.rollback()
            conflicting = db.query(Transaction).filter(
                Transaction.user_id == current_user.id,
                Transaction.idempotency_key == item.idempotency_key,
            ).first() if exc.status_code == status.HTTP_409_CONFLICT else None
            results.append(SyncItemResult(
                entity_type="transaction",
                local_id=item.local_id,
                status="CONFLICT" if exc.status_code == status.HTTP_409_CONFLICT else "REJECTED",
                remote_id=conflicting.id if conflicting else None,
                server_data=_transaction_sync_data(db, conflicting) if conflicting else None,
                message=str(exc.detail),
            ))
    if results:
        conflicts = sum(result.status == "CONFLICT" for result in results)
        event_key = hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()
        enqueue_notification(
            db,
            user_id=current_user.id,
            event_type="SYNC",
            event_key=f"sync-push:{event_key}",
            title="Sync needs attention" if conflicts else "Offline sync completed",
            body=(
                f"Sync completed with {conflicts} conflict(s). Review the affected items."
                if conflicts
                else f"Offline sync processed {len(results)} item(s)."
            ),
            background_tasks=background_tasks,
        )
    return SyncPushOut(results=results)


@router.get("/sync/pull", response_model=SyncPullOut)
def pull_sync_changes(
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    state = db.query(UserSyncState).filter(UserSyncState.user_id == current_user.id).first()
    if state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sync state is not initialized")
    if cursor > state.version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sync cursor is ahead of the server")
    events = db.query(SyncEvent).filter(
        SyncEvent.user_id == current_user.id,
        SyncEvent.version > cursor,
    ).order_by(SyncEvent.version).limit(limit).all()
    next_cursor = events[-1].version if len(events) == limit else state.version
    return SyncPullOut(
        cursor=next_cursor,
        events=[
            SyncEventOut(
                version=event.version,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                operation=event.operation,
                payload=event.payload,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    account_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if account_id is not None:
        query = query.filter(
            (Transaction.account_id == account_id) | (Transaction.transfer_account_id == account_id)
        )
    return query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).offset(offset).limit(limit).all()


@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _create_transaction(db, current_user.id, payload, response, background_tasks=background_tasks)


@router.post(
    "/transactions/{transaction_id}/reverse",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def reverse_transaction(
    transaction_id: int,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Query(..., min_length=1, max_length=120),
    category_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    original = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
    ).first()
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    existing = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.idempotency_key == idempotency_key,
    ).first()
    if existing is not None:
        if existing.reversal_of_id != original.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used for a different transaction",
            )
        response.status_code = status.HTTP_200_OK
        return existing

    transaction_type = {
        "INCOME": "EXPENSE",
        "EXPENSE": "INCOME",
        "TRANSFER": "TRANSFER",
    }[original.transaction_type]
    if transaction_type == "TRANSFER" and category_id is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transfer reversals cannot have a category")
    if transaction_type != "TRANSFER" and category_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Income and expense reversals require a category of the opposite type",
        )
    account_id, transfer_account_id = original.account_id, original.transfer_account_id
    if transaction_type == "TRANSFER":
        account_id, transfer_account_id = transfer_account_id, account_id
    payload = TransactionCreate(
        idempotency_key=idempotency_key,
        account_id=account_id,
        transfer_account_id=transfer_account_id,
        category_id=category_id if transaction_type != "TRANSFER" else None,
        transaction_type=transaction_type,
        amount=original.amount,
        currency_code=original.currency_code,
        description=f"Reversal: {original.description}"[:240],
        notes=None,
        transaction_date=datetime.now(timezone.utc),
    )
    if db.query(Transaction.id).filter(Transaction.reversal_of_id == original.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction has already been reversed")
    return _create_transaction(
        db,
        current_user.id,
        payload,
        response,
        reversal_of_id=original.id,
        background_tasks=background_tasks,
    )


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).order_by(
        Budget.start_date.desc(), Budget.id.desc()
    ).all()
    return [
        BudgetOut(
            id=budget.id,
            name=budget.name,
            category_id=budget.category_id,
            amount=budget.amount,
            spent=budget_spend(db, current_user.id, budget),
            currency_code=budget.currency_code,
            start_date=budget.start_date,
            end_date=budget.end_date,
            created_at=budget.created_at,
        )
        for budget in budgets
    ]


@router.post("/budgets", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    currency = require_currency(db, payload.currency_code)
    require_currency_precision(payload.amount, currency)
    validate_budget_category(db, current_user.id, payload.category_id)
    budget = Budget(user_id=current_user.id, **payload.model_dump())
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return BudgetOut(
        id=budget.id,
        name=budget.name,
        category_id=budget.category_id,
        amount=budget.amount,
        spent=ZERO,
        currency_code=budget.currency_code,
        start_date=budget.start_date,
        end_date=budget.end_date,
        created_at=budget.created_at,
    )


@router.post("/assets", response_model=FinancialRecordOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: FinancialRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    currency = require_currency(db, payload.currency_code)
    require_currency_precision(payload.amount, currency)
    asset = FinancialAsset(
        user_id=current_user.id,
        name=payload.name,
        asset_type=payload.record_type.upper(),
        currency_code=payload.currency_code,
        current_value=payload.amount,
        valued_at=payload.valued_at,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return FinancialRecordOut(
        id=asset.id,
        name=asset.name,
        currency_code=asset.currency_code,
        amount=asset.current_value,
        valued_at=asset.valued_at,
    )


@router.post("/liabilities", response_model=FinancialRecordOut, status_code=status.HTTP_201_CREATED)
def create_liability(
    payload: FinancialRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    currency = require_currency(db, payload.currency_code)
    require_currency_precision(payload.amount, currency)
    liability = Liability(
        user_id=current_user.id,
        name=payload.name,
        liability_type=payload.record_type.upper(),
        currency_code=payload.currency_code,
        outstanding_balance=payload.amount,
        valued_at=payload.valued_at,
    )
    db.add(liability)
    db.commit()
    db.refresh(liability)
    return FinancialRecordOut(
        id=liability.id,
        name=liability.name,
        currency_code=liability.currency_code,
        amount=liability.outstanding_balance,
        valued_at=liability.valued_at,
    )


@router.get("/reports/summary", response_model=FinanceSummaryOut)
def finance_summary(
    start_date: date,
    end_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End date must be on or after start date")
    start, end = date_range_utc(start_date, end_date)
    rows = db.query(
        Transaction.currency_code,
        Transaction.transaction_type,
        func.sum(Transaction.amount),
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_type.in_(("INCOME", "EXPENSE")),
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    ).group_by(Transaction.currency_code, Transaction.transaction_type).all()

    amounts: dict[str, dict[str, Decimal]] = {}
    for currency_code, transaction_type, amount in rows:
        amounts.setdefault(currency_code, {"INCOME": ZERO, "EXPENSE": ZERO})
        amounts[currency_code][transaction_type] = amount or ZERO

    balance_sheet = balance_sheet_totals(db, current_user.id)
    currencies = sorted(set(amounts) | set(balance_sheet))
    summaries = []
    for currency_code in currencies:
        income = amounts.get(currency_code, {}).get("INCOME", ZERO)
        expenses = amounts.get(currency_code, {}).get("EXPENSE", ZERO)
        assets = balance_sheet.get(currency_code, {}).get("total_assets", ZERO)
        liabilities = balance_sheet.get(currency_code, {}).get("total_liabilities", ZERO)
        summaries.append(
            CurrencyTotals(
                currency_code=currency_code,
                total_income=income,
                total_expenses=expenses,
                net_cash_flow=income - expenses,
                total_assets=assets,
                total_liabilities=liabilities,
                net_worth=assets - liabilities,
            )
        )
    return FinanceSummaryOut(start_date=start_date, end_date=end_date, by_currency=summaries)
