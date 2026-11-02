from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.routes.finance import _create_transaction
from app.core.config import settings
from app.models.finance import Account, Category
from app.models.integrations import MpesaAccountMapping, MpesaC2BPayment, MpesaStkRequest
from app.models.user import User
from app.providers.mpesa_daraja import MpesaDarajaProvider, MpesaProviderError
from app.schemas.finance import TransactionCreate
from app.schemas.mpesa import (
    MpesaAccountMappingInput,
    MpesaAccountMappingOut,
    MpesaStkRequestInput,
    MpesaStkRequestOut,
)
from app.services.notifications import enqueue_notification

router = APIRouter(prefix="/api/integrations/mpesa", tags=["M-Pesa Daraja"])
NAIROBI = ZoneInfo("Africa/Nairobi")


def _require_enabled(*, live_stk: bool = False) -> None:
    if not settings.mpesa_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="M-Pesa integration is not configured")
    if live_stk and settings.mpesa_environment == "production" and not settings.mpesa_live_payments_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live STK Push payments are disabled by server configuration",
        )


def _validate_callback_token(token: str | None) -> None:
    configured = settings.mpesa_callback_token
    if not configured or token is None or not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid M-Pesa callback credentials")


def _callback_response(result_code: int, description: str) -> dict[str, object]:
    return {"ResultCode": result_code, "ResultDesc": description}


def _callback_transaction_date(value: object) -> datetime:
    if not isinstance(value, (str, int)):
        raise ValueError("Missing provider transaction date")
    parsed = datetime.strptime(str(value), "%Y%m%d%H%M%S")
    return parsed.replace(tzinfo=NAIROBI).astimezone(timezone.utc)


def _money(value: object) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise ValueError("M-Pesa amount must be a positive whole number of KES")
    return amount


def _validate_user_mapping(db: Session, user_id: int, payload: MpesaAccountMappingInput) -> tuple[Account, Category]:
    account = db.query(Account).filter(
        Account.id == payload.account_id,
        Account.user_id == user_id,
        Account.is_active.is_(True),
        Account.currency_code == "KES",
    ).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active KES account not found")
    category = db.query(Category).filter(
        Category.id == payload.income_category_id,
        Category.user_id == user_id,
        Category.category_type == "INCOME",
    ).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income category not found")
    return account, category


@router.get("/status")
def get_integration_status(current_user: User = Depends(get_current_user)):
    return {
        "enabled": settings.mpesa_enabled,
        "environment": settings.mpesa_environment if settings.mpesa_enabled else "unconfigured",
        "live_stk_enabled": settings.mpesa_live_payments_enabled,
        "destination_model": "platform-managed shortcode",
    }


@router.get("/account-mapping", response_model=MpesaAccountMappingOut)
def get_account_mapping(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mapping = db.query(MpesaAccountMapping).filter_by(user_id=current_user.id, active=True).first()
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="M-Pesa C2B account mapping is not configured")
    return mapping


@router.put("/account-mapping", response_model=MpesaAccountMappingOut)
def put_account_mapping(
    payload: MpesaAccountMappingInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_user_mapping(db, current_user.id, payload)
    mapping = db.query(MpesaAccountMapping).filter_by(user_id=current_user.id).first()
    if mapping is None:
        mapping = MpesaAccountMapping(user_id=current_user.id, **payload.model_dump())
        db.add(mapping)
    else:
        mapping.account_id = payload.account_id
        mapping.income_category_id = payload.income_category_id
        mapping.account_reference = payload.account_reference
        mapping.active = True
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That M-Pesa account reference is already in use",
        ) from exc
    db.refresh(mapping)
    return mapping


@router.post("/stk-push", response_model=MpesaStkRequestOut, status_code=status.HTTP_202_ACCEPTED)
async def initiate_stk_push(
    payload: MpesaStkRequestInput,
    background_tasks: BackgroundTasks,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_enabled(live_stk=True)
    if payload.amount != payload.amount.to_integral_value():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="M-Pesa STK amounts must be whole KES")
    account = db.query(Account).filter(
        Account.id == payload.account_id,
        Account.user_id == current_user.id,
        Account.is_active.is_(True),
        Account.currency_code == "KES",
    ).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active KES account not found")
    category = db.query(Category).filter(
        Category.id == payload.category_id,
        Category.user_id == current_user.id,
        Category.category_type == "EXPENSE",
    ).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense category not found")

    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    existing = db.query(MpesaStkRequest).filter_by(
        user_id=current_user.id,
        idempotency_key=payload.idempotency_key,
    ).first()
    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key was already used for a different payment")
        response.status_code = status.HTTP_200_OK
        return existing

    payment = MpesaStkRequest(
        user_id=current_user.id,
        account_id=payload.account_id,
        category_id=payload.category_id,
        idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
        amount=payload.amount,
        phone_number=payload.phone_number,
        description=payload.description,
        account_reference="FP0000000000",
        status="SUBMITTING",
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(MpesaStkRequest).filter_by(
            user_id=current_user.id,
            idempotency_key=payload.idempotency_key,
        ).first()
        if existing is None or existing.request_hash != request_hash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment request conflicts with an existing request") from exc
        response.status_code = status.HTTP_200_OK
        return existing
    db.refresh(payment)
    payment.account_reference = f"FP{payment.id:010d}"
    db.commit()

    provider = MpesaDarajaProvider()
    result: dict = {}
    try:
        result = await provider.initiate_stk_push(
            phone_number=payment.phone_number,
            amount=int(payment.amount),
            account_reference=payment.account_reference,
            description=payment.description,
        )
    except MpesaProviderError as exc:
        payment.status = "FAILED"
        payment.result_description = str(exc)[:240]
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        payment.status = "RECONCILIATION_REQUIRED"
        payment.result_description = "Provider response was lost; check this request before initiating another payment."
    except httpx.HTTPError:
        payment.status = "RECONCILIATION_REQUIRED"
        payment.result_description = "Provider connection outcome is unknown; check this request before retrying."
    finally:
        await provider.aclose()
    if payment.status == "SUBMITTING":
        merchant_value = result.get("MerchantRequestID")
        checkout_value = result.get("CheckoutRequestID")
        merchant_id = merchant_value[:100] if isinstance(merchant_value, str) else ""
        checkout_id = checkout_value[:100] if isinstance(checkout_value, str) else ""
        if not merchant_id or not checkout_id:
            payment.status = "RECONCILIATION_REQUIRED"
            payment.result_description = "Provider accepted a request without identifiers; manual reconciliation is required."
        else:
            payment.status = "PENDING"
            payment.merchant_request_id = merchant_id
            payment.checkout_request_id = checkout_id
            payment.result_description = str(result.get("CustomerMessage", "Payment prompt sent to the phone."))[:240]
    db.commit()
    db.refresh(payment)
    enqueue_notification(
        db,
        user_id=current_user.id,
        event_type="MPESA",
        event_key=f"stk:{payment.id}:{payment.status.lower()}",
        title="M-Pesa payment request update",
        body=f"Your M-Pesa payment request is {payment.status.lower().replace('_', ' ')}.",
        background_tasks=background_tasks,
    )
    return payment


@router.get("/stk-push/{payment_id}", response_model=MpesaStkRequestOut)
def get_stk_request(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = db.query(MpesaStkRequest).filter(
        MpesaStkRequest.id == payment_id,
        MpesaStkRequest.user_id == current_user.id,
    ).first()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="M-Pesa payment request not found")
    return payment


@router.get("/stk-push", response_model=list[MpesaStkRequestOut])
def list_stk_requests(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(MpesaStkRequest)
        .filter(MpesaStkRequest.user_id == current_user.id)
        .order_by(MpesaStkRequest.created_at.desc(), MpesaStkRequest.id.desc())
        .limit(limit)
        .all()
    )


@router.post("/c2b/validation")
def validate_c2b_payment(
    payload: dict,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _validate_callback_token(token)
    _require_enabled()
    if str(payload.get("BusinessShortCode", "")) != settings.mpesa_shortcode:
        return _callback_response(1, "Invalid shortcode")
    reference = str(payload.get("BillRefNumber", "")).strip().upper()
    mapping = db.query(MpesaAccountMapping).filter_by(account_reference=reference, active=True).first()
    if mapping is None:
        return _callback_response(1, "Invalid account reference")
    account = db.query(Account).filter(
        Account.id == mapping.account_id,
        Account.user_id == mapping.user_id,
        Account.is_active.is_(True),
        Account.currency_code == "KES",
    ).first()
    category = db.query(Category).filter(
        Category.id == mapping.income_category_id,
        Category.user_id == mapping.user_id,
        Category.category_type == "INCOME",
    ).first()
    try:
        _money(payload.get("TransAmount"))
        _callback_transaction_date(payload.get("TransTime"))
    except (InvalidOperation, ValueError, TypeError):
        return _callback_response(1, "Invalid payment details")
    if account is None or category is None:
        return _callback_response(1, "Account mapping is unavailable")
    return _callback_response(0, "Accepted")


@router.post("/c2b/confirmation")
def confirm_c2b_payment(
    payload: dict,
    background_tasks: BackgroundTasks,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _validate_callback_token(token)
    _require_enabled()
    receipt = str(payload.get("TransID", "")).strip().upper()
    reference = str(payload.get("BillRefNumber", "")).strip().upper()
    if not receipt or str(payload.get("BusinessShortCode", "")) != settings.mpesa_shortcode:
        return _callback_response(1, "Invalid payment details")
    mapping = db.query(MpesaAccountMapping).filter_by(account_reference=reference, active=True).first()
    if mapping is None:
        return _callback_response(1, "Invalid account reference")
    try:
        amount = _money(payload.get("TransAmount"))
        transaction_date = _callback_transaction_date(payload.get("TransTime"))
    except (InvalidOperation, ValueError, TypeError):
        return _callback_response(1, "Invalid payment details")

    c2b_payment = db.query(MpesaC2BPayment).filter_by(receipt_number=receipt).first()
    if c2b_payment is not None and c2b_payment.status == "POSTED":
        return _callback_response(0, "Already recorded")
    if c2b_payment is None:
        c2b_payment = MpesaC2BPayment(
            user_id=mapping.user_id,
            account_id=mapping.account_id,
            income_category_id=mapping.income_category_id,
            receipt_number=receipt,
            account_reference=reference,
            amount=amount,
            transaction_date=transaction_date,
            status="PROCESSING",
        )
        db.add(c2b_payment)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing_payment = db.query(MpesaC2BPayment).filter_by(receipt_number=receipt).first()
            if (
                existing_payment is not None
                and existing_payment.user_id == mapping.user_id
                and existing_payment.account_reference == reference
                and existing_payment.amount == amount
            ):
                return _callback_response(0, "Already recorded")
            return _callback_response(1, "Receipt conflicts with an existing payment")
        db.refresh(c2b_payment)
    elif (
        c2b_payment.user_id != mapping.user_id
        or c2b_payment.account_reference != reference
        or c2b_payment.amount != amount
    ):
        return _callback_response(1, "Receipt conflicts with an existing payment")

    transaction_payload = TransactionCreate(
        idempotency_key=f"mpesa-c2b:{receipt}",
        account_id=mapping.account_id,
        category_id=mapping.income_category_id,
        transaction_type="INCOME",
        amount=amount,
        currency_code="KES",
        description=f"M-Pesa payment {receipt}"[:240],
        notes="M-Pesa C2B confirmation",
        transaction_date=transaction_date,
    )
    try:
        ledger_response = Response()
        transaction = _create_transaction(
            db,
            mapping.user_id,
            transaction_payload,
            ledger_response,
            background_tasks=background_tasks,
        )
    except HTTPException:
        db.rollback()
        c2b_payment = db.query(MpesaC2BPayment).filter_by(receipt_number=receipt).first()
        if c2b_payment is not None:
            c2b_payment.status = "RECONCILIATION_REQUIRED"
            db.commit()
        enqueue_notification(
            db,
            user_id=mapping.user_id,
            event_type="MPESA",
            event_key=f"c2b:{receipt}:reconciliation",
            title="M-Pesa payment needs review",
            body=f"Payment receipt {receipt} needs ledger reconciliation.",
            background_tasks=background_tasks,
        )
        return _callback_response(0, "Payment received for reconciliation")

    c2b_payment.status = "POSTED"
    c2b_payment.transaction_id = transaction.id
    db.commit()
    enqueue_notification(
        db,
        user_id=mapping.user_id,
        event_type="MPESA",
        event_key=f"c2b:{receipt}:posted",
        title="M-Pesa payment recorded",
        body=f"Incoming payment {receipt} was recorded in your KES ledger.",
        background_tasks=background_tasks,
    )
    return _callback_response(0, "Accepted")


@router.post("/stk/callback")
def stk_callback(
    payload: dict,
    background_tasks: BackgroundTasks,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _validate_callback_token(token)
    _require_enabled()
    body = payload.get("Body")
    callback = body.get("stkCallback", {}) if isinstance(body, dict) else {}
    if not isinstance(callback, dict):
        return _callback_response(1, "Invalid callback")
    checkout_id = str(callback.get("CheckoutRequestID", ""))
    payment = db.query(MpesaStkRequest).filter_by(checkout_request_id=checkout_id).first()
    if payment is None:
        return _callback_response(1, "Unknown payment request")
    if payment.status == "SUCCEEDED":
        return _callback_response(0, "Already recorded")
    if str(callback.get("MerchantRequestID", "")) != str(payment.merchant_request_id or ""):
        return _callback_response(1, "Payment request does not match")
    result_code = str(callback.get("ResultCode", ""))
    payment.result_code = result_code[:20]
    payment.result_description = str(callback.get("ResultDesc", ""))[:240]
    if result_code != "0":
        payment.status = "FAILED"
        db.commit()
        enqueue_notification(
            db,
            user_id=payment.user_id,
            event_type="MPESA",
            event_key=f"stk:{payment.id}:failed",
            title="M-Pesa payment was not completed",
            body="The M-Pesa payment request was not completed.",
            background_tasks=background_tasks,
        )
        return _callback_response(0, "Payment status recorded")

    callback_metadata = callback.get("CallbackMetadata")
    metadata = callback_metadata.get("Item", []) if isinstance(callback_metadata, dict) else []
    values = {
        str(item.get("Name")): item.get("Value")
        for item in metadata
        if isinstance(item, dict) and item.get("Name")
    } if isinstance(metadata, list) else {}
    receipt = str(values.get("MpesaReceiptNumber", "")).strip().upper()
    try:
        amount = _money(values.get("Amount"))
        callback_phone = str(values.get("PhoneNumber", ""))
        transaction_date = _callback_transaction_date(values.get("TransactionDate"))
    except (InvalidOperation, ValueError, TypeError):
        payment.status = "RECONCILIATION_REQUIRED"
        payment.result_description = "Successful payment callback is incomplete; manual reconciliation is required."
        db.commit()
        enqueue_notification(
            db,
            user_id=payment.user_id,
            event_type="MPESA",
            event_key=f"stk:{payment.id}:reconciliation",
            title="M-Pesa payment needs review",
            body="A successful payment callback could not be matched automatically.",
            background_tasks=background_tasks,
        )
        return _callback_response(0, "Payment needs reconciliation")
    if not receipt or amount != payment.amount or callback_phone != payment.phone_number:
        payment.status = "RECONCILIATION_REQUIRED"
        payment.result_description = "Successful payment did not match the request; manual reconciliation is required."
        db.commit()
        enqueue_notification(
            db,
            user_id=payment.user_id,
            event_type="MPESA",
            event_key=f"stk:{payment.id}:reconciliation",
            title="M-Pesa payment needs review",
            body="A successful payment callback could not be matched automatically.",
            background_tasks=background_tasks,
        )
        return _callback_response(0, "Payment needs reconciliation")

    if payment.mpesa_receipt_number and payment.mpesa_receipt_number != receipt:
        payment.status = "RECONCILIATION_REQUIRED"
        payment.result_description = "Receipt does not match the recorded payment."
        db.commit()
        enqueue_notification(
            db,
            user_id=payment.user_id,
            event_type="MPESA",
            event_key=f"stk:{payment.id}:reconciliation",
            title="M-Pesa payment needs review",
            body="A successful payment callback could not be matched automatically.",
            background_tasks=background_tasks,
        )
        return _callback_response(0, "Payment needs reconciliation")
    payment.mpesa_receipt_number = receipt
    transaction_payload = TransactionCreate(
        idempotency_key=f"mpesa-stk:{receipt}",
        account_id=payment.account_id,
        category_id=payment.category_id,
        transaction_type="EXPENSE",
        amount=amount,
        currency_code="KES",
        description=payment.description[:240],
        notes=f"M-Pesa STK Push receipt {receipt}",
        transaction_date=transaction_date,
    )
    try:
        transaction = _create_transaction(
            db,
            payment.user_id,
            transaction_payload,
            Response(),
            background_tasks=background_tasks,
        )
    except HTTPException:
        db.rollback()
        payment = db.query(MpesaStkRequest).filter_by(id=payment.id).first()
        payment.mpesa_receipt_number = receipt
        payment.status = "RECONCILIATION_REQUIRED"
        payment.result_description = "Payment succeeded but could not be posted to the ledger; reconciliation is required."
        db.commit()
        enqueue_notification(
            db,
            user_id=payment.user_id,
            event_type="MPESA",
            event_key=f"stk:{payment.id}:reconciliation",
            title="M-Pesa payment needs review",
            body=f"Payment receipt {receipt} needs ledger reconciliation.",
            background_tasks=background_tasks,
        )
        return _callback_response(0, "Payment received for reconciliation")

    payment.status = "SUCCEEDED"
    payment.transaction_id = transaction.id
    db.commit()
    enqueue_notification(
        db,
        user_id=payment.user_id,
        event_type="MPESA",
        event_key=f"stk:{payment.id}:succeeded",
        title="M-Pesa payment recorded",
        body=f"Payment receipt {receipt} was recorded in your KES ledger.",
        background_tasks=background_tasks,
    )
    return _callback_response(0, "Accepted")
