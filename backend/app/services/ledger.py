from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy import case, func, select, union_all
from sqlalchemy.orm import Session

from app.models.finance import Account, Budget, Category, FinancialAsset, Liability, Transaction
from app.models.currency import Currency
from app.schemas.finance import TransactionCreate

ZERO = Decimal("0")


def require_currency(db: Session, code: str) -> Currency:
    currency = db.query(Currency).filter(Currency.code == code, Currency.active.is_(True)).first()
    if currency is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency is not supported")
    return currency


def require_currency_precision(amount: Decimal, currency: Currency) -> None:
    quantum = Decimal(1).scaleb(-currency.decimal_places)
    if amount != amount.quantize(quantum):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Amount exceeds the supported precision for {currency.code}",
        )


def account_balance_deltas(db: Session, user_id: int) -> dict[int, Decimal]:
    source_delta = func.sum(
        case(
            (Transaction.transaction_type == "INCOME", Transaction.amount),
            (Transaction.transaction_type == "EXPENSE", -Transaction.amount),
            (Transaction.transaction_type == "TRANSFER", -Transaction.amount),
            else_=ZERO,
        )
    ).label("delta")
    source = (
        select(Transaction.account_id.label("account_id"), source_delta)
        .where(Transaction.user_id == user_id)
        .group_by(Transaction.account_id)
    )
    destination = (
        select(
            Transaction.transfer_account_id.label("account_id"),
            func.sum(Transaction.amount).label("delta"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == "TRANSFER",
            Transaction.transfer_account_id.is_not(None),
        )
        .group_by(Transaction.transfer_account_id)
    )
    effects = union_all(source, destination).subquery()
    totals = db.execute(
        select(effects.c.account_id, func.sum(effects.c.delta)).group_by(effects.c.account_id)
    ).all()
    return {account_id: amount or ZERO for account_id, amount in totals}


def transaction_request_hash(payload: TransactionCreate, reversal_of_id: int | None = None) -> str:
    body = payload.model_dump(mode="json")
    body["reversal_of_id"] = reversal_of_id
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def date_range_utc(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def budget_spend(db: Session, user_id: int, budget: Budget) -> Decimal:
    start, end = date_range_utc(budget.start_date, budget.end_date)
    query = db.query(func.coalesce(func.sum(Transaction.amount), ZERO)).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == "EXPENSE",
        Transaction.currency_code == budget.currency_code,
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )
    if budget.category_id is not None:
        query = query.filter(Transaction.category_id == budget.category_id)
    return query.scalar() or ZERO


def balance_sheet_totals(db: Session, user_id: int) -> dict[str, dict[str, Decimal]]:
    totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"total_assets": ZERO, "total_liabilities": ZERO}
    )

    deltas = account_balance_deltas(db, user_id)
    for account_id, currency_code, opening_balance in db.query(
        Account.id, Account.currency_code, Account.opening_balance
    ).filter(Account.user_id == user_id, Account.is_active.is_(True)).all():
        totals[currency_code]["total_assets"] += opening_balance + deltas.get(account_id, ZERO)

    for currency_code, amount in db.query(
        FinancialAsset.currency_code, func.sum(FinancialAsset.current_value)
    ).filter(FinancialAsset.user_id == user_id).group_by(FinancialAsset.currency_code).all():
        totals[currency_code]["total_assets"] += amount or ZERO

    for currency_code, amount in db.query(
        Liability.currency_code, func.sum(Liability.outstanding_balance)
    ).filter(Liability.user_id == user_id).group_by(Liability.currency_code).all():
        totals[currency_code]["total_liabilities"] += amount or ZERO

    return totals


def validate_budget_category(db: Session, user_id: int, category_id: int | None) -> None:
    if category_id is None:
        return
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == user_id,
        Category.category_type == "EXPENSE",
    ).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense category not found")
