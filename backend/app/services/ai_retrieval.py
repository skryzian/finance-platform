from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.finance import Account, Budget, FinancialAsset, Liability, Transaction
from app.models.valuation import ExchangeRateObservation, MarketPriceHistory
from app.services.ledger import account_balance_deltas, budget_spend, balance_sheet_totals


def build_verified_context(db: Session, user_id: int) -> tuple[dict, list[dict[str, str]]]:
    balances = account_balance_deltas(db, user_id)
    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id, Account.is_active.is_(True))
        .order_by(Account.id)
        .limit(15)
        .all()
    )
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(20)
        .all()
    )
    budgets = (
        db.query(Budget)
        .filter(Budget.user_id == user_id)
        .order_by(Budget.end_date.desc(), Budget.id.desc())
        .limit(10)
        .all()
    )
    assets = (
        db.query(FinancialAsset)
        .filter(FinancialAsset.user_id == user_id)
        .order_by(FinancialAsset.updated_at.desc(), FinancialAsset.id.desc())
        .limit(10)
        .all()
    )
    liabilities = (
        db.query(Liability)
        .filter(Liability.user_id == user_id)
        .order_by(Liability.updated_at.desc(), Liability.id.desc())
        .limit(10)
        .all()
    )
    totals = balance_sheet_totals(db, user_id)

    rates = (
        db.query(ExchangeRateObservation)
        .order_by(ExchangeRateObservation.effective_date.desc(), ExchangeRateObservation.id.desc())
        .limit(10)
        .all()
    )
    prices = (
        db.query(MarketPriceHistory)
        .order_by(MarketPriceHistory.effective_date.desc(), MarketPriceHistory.id.desc())
        .limit(10)
        .all()
    )

    context = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "currency_note": "All balances and totals are grouped by currency; no automatic currency conversion is applied.",
        "accounts": [
            {
                "name": item.name,
                "type": item.account_type,
                "currency": item.currency_code,
                "balance": str(item.opening_balance + balances.get(item.id, Decimal("0"))),
            }
            for item in accounts
        ],
        "recent_transactions": [
            {
                "date": item.transaction_date.isoformat(),
                "type": item.transaction_type,
                "amount": str(item.amount),
                "currency": item.currency_code,
                "description": item.description[:120],
            }
            for item in transactions
        ],
        "budgets": [
            {
                "name": item.name,
                "currency": item.currency_code,
                "limit": str(item.amount),
                "spent": str(budget_spend(db, user_id, item)),
                "period_start": item.start_date.isoformat(),
                "period_end": item.end_date.isoformat(),
            }
            for item in budgets
        ],
        "assets": [
            {"name": item.name, "type": item.asset_type, "value": str(item.current_value), "currency": item.currency_code, "valued_at": item.valued_at.isoformat()}
            for item in assets
        ],
        "liabilities": [
            {"name": item.name, "type": item.liability_type, "balance": str(item.outstanding_balance), "currency": item.currency_code, "valued_at": item.valued_at.isoformat()}
            for item in liabilities
        ],
        "net_worth_by_currency": {
            currency: {key: str(value) for key, value in values.items()}
            for currency, values in totals.items()
        },
        "sourced_fx_observations": [
            {
                "base": item.base_currency,
                "quote": item.quote_currency,
                "rate": str(item.rate),
                "date": item.effective_date.isoformat(),
                "provider": item.provider_key,
                "state": item.data_state,
            }
            for item in rates
        ],
        "sourced_market_prices": [
            {
                "symbol": item.symbol,
                "asset_type": item.asset_type,
                "price": str(item.price),
                "currency": item.currency_code,
                "currency_source": item.currency_source,
                "date": item.effective_date.isoformat(),
                "provider": item.provider_key,
                "state": item.data_state,
            }
            for item in prices
        ],
    }
    references = [
        {"source": "Your accounts and ledger", "path": "/api/finance/accounts and /api/finance/transactions"},
        {"source": "Your budgets and balance sheet", "path": "/api/finance/budgets and /api/finance/reports/summary"},
        {"source": "Sourced dated valuations", "path": "/api/markets/prices and /api/markets/exchange-rates"},
    ]
    return context, references
