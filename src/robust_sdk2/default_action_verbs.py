"""The default LodgeIT action-verb taxonomy.

Action verbs map a transaction's intent (e.g. "Invest_In") to the GL account
where the offsetting entry goes. When you don't have your own action-verb set,
this list is a reasonable starting point — it covers the core
investment / borrowing / capital / fees / GST verbs the calculator pipeline
expects.

    from robust_sdk2 import default_action_verbs
    req = LedgerRequest(..., action_verbs=default_action_verbs())
"""
from decimal import Decimal

from .domain import ActionVerb


def default_action_verbs() -> list[ActionVerb]:
    """Return a fresh list of ActionVerb instances representing the default taxonomy."""
    return [
        ActionVerb(name="Transfers",         exchanged_account="Transfers"),
        ActionVerb(name="Invest_In",         exchanged_account="FinancialInvestments",
                   description="Shares", trading_account="InvestmentIncome"),
        ActionVerb(name="Dispose_Of",        exchanged_account="FinancialInvestments",
                   description="Shares", trading_account="InvestmentIncome"),
        ActionVerb(name="Bank_Charges",      exchanged_account="BankCharges"),
        ActionVerb(name="Expenses",          exchanged_account="Other_Expenses"),
        ActionVerb(name="Gain",              exchanged_account="Other_Gain"),
        ActionVerb(name="Loss",              exchanged_account="ShareCapital",
                   description="No Description"),
        ActionVerb(name="Income",            exchanged_account="Income"),
        ActionVerb(name="Interest_Income",   exchanged_account="InterestIncome"),
        ActionVerb(name="Interest_Expenses", exchanged_account="Interest_Expenses"),
        ActionVerb(name="Borrow",            exchanged_account="Non_Current_Loans"),
        ActionVerb(name="Introduce_Capital", exchanged_account="Share_Capital",
                   description="Unit_Investment"),
        ActionVerb(name="Pay_Bank",          exchanged_account="Bank_Charges",
                   description="No Description"),
        ActionVerb(name="Accountancy_Fees",  exchanged_account="AccountancyFees",
                   description="No Description"),
        ActionVerb(name="Purchase_Method_C", exchanged_account="Purchases",
                   description="No Description",
                   gst_rate_percent=Decimal("10"),
                   gst_receivable_account="Gst_Receivable"),
        ActionVerb(name="Sale_Method_C",     exchanged_account="Income",
                   description="No Description",
                   gst_rate_percent=Decimal("10"),
                   gst_payable_account="Gst_Payable"),
    ]
