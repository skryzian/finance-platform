from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AccountType = Literal["CASH", "BANK", "MOBILE_MONEY", "SAVINGS", "CREDIT"]
CategoryType = Literal["INCOME", "EXPENSE"]
TransactionType = Literal["INCOME", "EXPENSE", "TRANSFER"]


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    account_type: AccountType
    institution: str | None = Field(default=None, max_length=120)
    currency_code: str = Field(..., min_length=3, max_length=3)
    opening_balance: Decimal = Field(default=Decimal("0"), max_digits=24, decimal_places=8)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Account name cannot be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("opening_balance")
    @classmethod
    def finite_opening_balance(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value.as_tuple().exponent < -8:
            raise ValueError("Opening balance must be finite with at most eight decimal places")
        return value


class AccountOut(BaseModel):
    id: int
    name: str
    account_type: str
    institution: str | None
    currency_code: str
    opening_balance: Decimal
    current_balance: Decimal
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    category_type: CategoryType

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category name cannot be blank")
        return value


class CategoryOut(BaseModel):
    id: int
    name: str
    category_type: CategoryType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=120)
    account_id: int = Field(..., gt=0)
    transfer_account_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    transaction_type: TransactionType
    amount: Decimal = Field(..., gt=0, max_digits=24, decimal_places=8)
    currency_code: str = Field(..., min_length=3, max_length=3)
    description: str = Field(..., min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=2000)
    transaction_date: datetime

    @field_validator("idempotency_key", "description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("amount")
    @classmethod
    def finite_positive_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -8:
            raise ValueError("Amount must be positive, finite, and have at most eight decimal places")
        return value

    @field_validator("transaction_date")
    @classmethod
    def require_aware_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Transaction date must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_transaction_shape(self):
        if self.transaction_type == "TRANSFER":
            if self.transfer_account_id is None or self.category_id is not None:
                raise ValueError("Transfers require a destination account and cannot have a category")
            if self.transfer_account_id == self.account_id:
                raise ValueError("Transfer source and destination must differ")
        elif self.transfer_account_id is not None or self.category_id is None:
            raise ValueError("Income and expenses require a category and cannot have a transfer destination")
        return self


class TransactionOut(BaseModel):
    id: int
    account_id: int
    transfer_account_id: int | None
    category_id: int | None
    reversal_of_id: int | None
    idempotency_key: str
    transaction_type: TransactionType
    amount: Decimal
    currency_code: str
    description: str
    notes: str | None
    transaction_date: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category_id: int | None = Field(default=None, gt=0)
    amount: Decimal = Field(..., gt=0, max_digits=24, decimal_places=8)
    currency_code: str = Field(..., min_length=3, max_length=3)
    start_date: date
    end_date: date

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Budget name cannot be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("amount")
    @classmethod
    def finite_positive_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -8:
            raise ValueError("Budget amount must be positive, finite, and have at most eight decimal places")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Budget end date must be on or after its start date")
        return self


class BudgetOut(BaseModel):
    id: int
    name: str
    category_id: int | None
    amount: Decimal
    spent: Decimal
    currency_code: str
    start_date: date
    end_date: date
    created_at: datetime


class FinancialRecordCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    record_type: str = Field(..., min_length=1, max_length=32)
    currency_code: str = Field(..., min_length=3, max_length=3)
    amount: Decimal = Field(..., ge=0, max_digits=24, decimal_places=8)
    valued_at: datetime

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("amount")
    @classmethod
    def finite_nonnegative_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value.as_tuple().exponent < -8:
            raise ValueError("Amount must be finite, non-negative, and have at most eight decimal places")
        return value

    @field_validator("valued_at")
    @classmethod
    def require_aware_valuation_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Valuation timestamp must include a timezone")
        return value.astimezone(timezone.utc)


class FinancialRecordOut(BaseModel):
    id: int
    name: str
    currency_code: str
    amount: Decimal
    valued_at: datetime


class CurrencyTotals(BaseModel):
    currency_code: str
    total_income: Decimal
    total_expenses: Decimal
    net_cash_flow: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal


class FinanceSummaryOut(BaseModel):
    start_date: date
    end_date: date
    by_currency: list[CurrencyTotals]


class SyncAccountInput(AccountCreate):
    client_id: UUID
    remote_id: int | None = Field(default=None, gt=0)
    base_version: int = Field(..., ge=0)
    is_deleted: bool = False


class SyncCategoryInput(CategoryCreate):
    client_id: UUID
    remote_id: int | None = Field(default=None, gt=0)
    base_version: int = Field(..., ge=0)
    is_deleted: bool = False


class SyncTransactionInput(BaseModel):
    local_id: str = Field(..., min_length=1, max_length=64)
    idempotency_key: str = Field(..., min_length=1, max_length=120)
    account_client_id: UUID | None = None
    account_remote_id: int | None = Field(default=None, gt=0)
    transfer_account_client_id: UUID | None = None
    transfer_account_remote_id: int | None = Field(default=None, gt=0)
    category_client_id: UUID | None = None
    category_remote_id: int | None = Field(default=None, gt=0)
    transaction_type: TransactionType
    amount: Decimal = Field(..., gt=0, max_digits=24, decimal_places=8)
    currency_code: str = Field(..., min_length=3, max_length=3)
    description: str = Field(..., min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=2000)
    transaction_date: datetime

    @field_validator("idempotency_key", "description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("amount")
    @classmethod
    def finite_positive_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -8:
            raise ValueError("Amount must be positive, finite, and have at most eight decimal places")
        return value

    @field_validator("transaction_date")
    @classmethod
    def require_aware_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Transaction date must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_transaction_shape(self):
        if (self.account_client_id is None) == (self.account_remote_id is None):
            raise ValueError("Provide exactly one source account identifier")
        if self.transaction_type == "TRANSFER":
            has_destination = self.transfer_account_client_id is not None or self.transfer_account_remote_id is not None
            if (
                not has_destination
                or (self.transfer_account_client_id is not None and self.transfer_account_remote_id is not None)
                or self.category_client_id is not None
                or self.category_remote_id is not None
            ):
                raise ValueError("Transfers require a destination account and cannot have a category")
            if (
                self.transfer_account_client_id is not None
                and self.transfer_account_client_id == self.account_client_id
            ) or (
                self.transfer_account_remote_id is not None
                and self.transfer_account_remote_id == self.account_remote_id
            ):
                raise ValueError("Transfer source and destination must differ")
        elif (
            self.transfer_account_client_id is not None
            or self.transfer_account_remote_id is not None
            or (self.category_client_id is None) == (self.category_remote_id is None)
        ):
            raise ValueError("Income and expenses require a category and cannot have a transfer destination")
        return self


class SyncPushInput(BaseModel):
    accounts: list[SyncAccountInput] = Field(default_factory=list, max_length=100)
    categories: list[SyncCategoryInput] = Field(default_factory=list, max_length=100)
    transactions: list[SyncTransactionInput] = Field(default_factory=list, max_length=100)


class SyncItemResult(BaseModel):
    entity_type: Literal["account", "category", "transaction"]
    local_id: str
    status: Literal["APPLIED", "CONFLICT", "REJECTED"]
    remote_id: int | None = None
    server_version: int | None = None
    server_data: dict[str, Any] | None = None
    message: str | None = None


class SyncPushOut(BaseModel):
    results: list[SyncItemResult]


class SyncEventOut(BaseModel):
    version: int
    entity_type: str
    entity_id: str
    operation: str
    payload: dict[str, Any]
    created_at: datetime


class SyncPullOut(BaseModel):
    cursor: int
    events: list[SyncEventOut]
