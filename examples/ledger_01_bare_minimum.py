"""Ledger example 1: the bare minimum for an investment calculation.

One investment, ACME, in an AUD report, over the 2023-24 financial year:

    2023-08-01  buy  1 ACME for 100 AUD
    2024-02-01  buy  1 ACME for 300 AUD   (the price has risen)
    2024-05-01  sell 1 ACME for 300 AUD   (at that same high price)

What the request has to declare, and why:

- `ReportDetails`: the period and the report currency. Everything else on
  it has defaults (market valuation, fifo, the legacy + investments account
  taxonomies, which provide `FinancialInvestments` and `InvestmentIncome`).
- One `BankStatement`: the calculator takes transactions from bank
  statements (or GL inputs). The account starts at zero and nothing pays
  into it, so it ends 100 AUD overdrawn; the calculator doesn't mind.
  `debit` is money leaving the account (a purchase), `credit` money coming
  in (a sale). `units_count` is positive either way.
- Two `ActionVerb`s, `Invest_In` and `Dispose_Of`: each transaction's
  `description` must name one. They post the units to
  `FinancialInvestments` and the gains to `InvestmentIncome`.
- One `UnitValue`: the price of ACME at the end of the period (`date` and
  `currency` default to the report's end date and currency). Without it the
  calculator can't value the unit still held, and the investment report
  fails with an alert.

The sale has to be matched against one of the two purchases, and which one
is set by `ReportDetails.pricing_method`: "fifo" (the default) sells the
oldest lot, the one bought at 100, so the sale realizes 200; "lifo" sells
the newest, bought at 300, so it realizes 0 and the 100 lot keeps an
unrealized gain of 200. The script prints the investment report's lots so
you can see which purchase was sold.

Configuration via environment (same as the other examples):

    ROBUST_URL    base URL of the Robust deployment (default: http://localhost:8877)
    ROBUST_AUTH   "user:password" for HTTP Basic auth (default: no auth)

Usage:

    python examples/ledger_01_bare_minimum.py
"""
import os
import sys
from datetime import date
from decimal import Decimal

import requests

from robust_sdk2 import (
    ActionVerb,
    BankStatement,
    LedgerRequest,
    ReportDetails,
    Transaction,
    UnitValue,
    submit,
)


def build_request() -> LedgerRequest:
    return LedgerRequest(
        report_details=ReportDetails(
            start_date=date(2023, 7, 1),
            end_date=date(2024, 6, 30),
            report_currency="AUD",
        ),
        bank_statements=[
            BankStatement(
                account_name="Bank",
                account_number="1",
                bank_id="Bank",
                account_currency="AUD",
                transactions=[
                    Transaction(description="Invest_In", date=date(2023, 8, 1),
                                debit=Decimal("100"), units_type="ACME", units_count=Decimal("1")),
                    Transaction(description="Invest_In", date=date(2024, 2, 1),
                                debit=Decimal("300"), units_type="ACME", units_count=Decimal("1")),
                    Transaction(description="Dispose_Of", date=date(2024, 5, 1),
                                credit=Decimal("300"), units_type="ACME", units_count=Decimal("1")),
                ],
            ),
        ],
        action_verbs=[
            ActionVerb(name="Invest_In", exchanged_account="FinancialInvestments",
                       trading_account="InvestmentIncome"),
            ActionVerb(name="Dispose_Of", exchanged_account="FinancialInvestments",
                       trading_account="InvestmentIncome"),
        ],
        unit_values=[
            UnitValue(unit_type="ACME", value=Decimal("300")),
        ],
    )


def _amount(cell) -> str:
    """Investment-report cells are {"amount": .., "unit": ..} (or a list of them for totals)."""
    if isinstance(cell, list):
        return " + ".join(_amount(c) for c in cell) or "-"
    if isinstance(cell, dict) and "amount" in cell:
        return f"{cell['amount']} {cell.get('unit', '')}".strip()
    return "-"


def print_investment_report(report: dict) -> None:
    print(f"\n{report.get('title', 'investment report')}")
    print(f"  {'bought':<10} {'cost':>9}   {'sold':<10} {'for':>9}   {'realized':>9} {'unrealized':>10}")
    for row in report.get("data_rows", []):
        purchase, sale, gains = row.get("purchase", {}), row.get("sale", {}), row.get("gains", {})
        print(f"  {purchase.get('date', '-'):<10} {_amount(purchase.get('unit_cost_foreign')):>9}"
              f"   {sale.get('date', '-'):<10} {_amount(sale.get('unit_cost_foreign')):>9}"
              f"   {_amount(gains.get('rea', {}).get('market_converted')):>9}"
              f" {_amount(gains.get('unr', {}).get('market_converted')):>10}")
    totals = report.get("totals", {}).get("gains", {})
    print(f"  realized total {_amount(totals.get('realized_total'))}, "
          f"unrealized total {_amount(totals.get('unrealized_total'))}, "
          f"total {_amount(totals.get('total'))}")


def main() -> int:
    req = build_request()
    auth = os.environ.get("ROBUST_AUTH") or None
    print(f"pricing_method: {req.report_details.pricing_method}")

    job = submit(req, base_url=os.environ.get("ROBUST_URL", "http://localhost:8877"), auth=auth)
    print(f"submitted: {job.id}\nview:      {job.view_url}")

    final = job.wait(timeout=120)
    result = final.get("result") or {}
    print(f"status:    {final.get('status')}")
    if result.get("alerts"):
        print(f"alerts:    {result['alerts']}")

    urls = {r.get("key"): (r.get("val") or {}).get("url") for r in result.get("reports", [])}
    if urls.get("investment_report_json"):
        r = requests.get(urls["investment_report_json"],
                         auth=tuple(auth.split(":", 1)) if auth else None)
        r.raise_for_status()
        print_investment_report(r.json())
    return 0 if final.get("status") == "Success" and not result.get("alerts") else 1


if __name__ == "__main__":
    sys.exit(main())
