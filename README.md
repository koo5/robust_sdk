# robust-sdk2

Pythonic SDK for building and submitting requests to a Robust accounting
calculator deployment. Construct typed Pydantic objects, submit, poll for
results.

Currently covers the **ledger calculator request** subset (report details,
bank statements with transactions, unit values, action verbs, unit types).
Other calculators (depreciation, livestock, hire-purchase) are not yet
covered.

## Install

```bash
pip install -e sources/common/libs/sdk2
```

Requires Python ≥ 3.10. Pulls in `pydantic>=2` and `rdflib>=7`.

## Quick start

```python
from datetime import date
from decimal import Decimal

from robust_sdk2 import (
    LedgerRequest, ReportDetails, BankStatement, Transaction,
    ActionVerb, UnitValue, submit,
)

req = LedgerRequest(
    report_details=ReportDetails(
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        report_currency="AUD",
    ),
    bank_statements=[
        BankStatement(
            account_number="12345",
            account_name="Cash at Bank",
            bank_id="ANZ",
            account_currency="AUD",
            transactions=[
                Transaction(
                    description="Coffee", date=date(2023, 8, 1),
                    debit=Decimal("4.50"),
                ),
                Transaction(
                    description="Buy ACME shares", date=date(2023, 9, 15),
                    debit=Decimal("1000.00"),
                    units_type="ACME", units_count=Decimal("10"),
                ),
            ],
        ),
    ],
    action_verbs=[
        ActionVerb(name="Bank_Charges", exchanged_account="Bank_Charges"),
        ActionVerb(name="Invest_In", exchanged_account="Financial_Investments",
                   trading_account="Investment_Income"),
    ],
    unit_values=[
        UnitValue(unit_type="ACME", value=Decimal("110.00")),
    ],
)

job = submit(req, base_url="https://robust.example.com", auth=("user", "pass"))
print(job.view_url)
print(job.poll())
```

## URI hatch

After `submit` (or a direct `build_request_rdf`) returns, every model that
was part of the request has its `uri` field populated with the identifier
the builder used as the subject of the type-asserting triple for that
object. Pre-populate `uri` before submitting to pin a stable URI of your
choice, or read it back afterwards to attach extra metadata to the same
graph.

```python
from rdflib import URIRef, Literal, Namespace
from robust_sdk2 import build_request_rdf

graph = build_request_rdf(req)
MY = Namespace("https://my.example/ns#")
txn = req.bank_statements[0].transactions[1]
graph.add((URIRef(txn.uri), MY.note, Literal("LLM-classified as investment")))
```

## API surface

```
robust_sdk2.LedgerRequest
robust_sdk2.ReportDetails
robust_sdk2.BankStatement
robust_sdk2.Transaction
robust_sdk2.ActionVerb
robust_sdk2.UnitValue
robust_sdk2.UnitType

robust_sdk2.build_request_rdf(req) -> rdflib.Graph
robust_sdk2.submit(req, base_url, auth=None) -> JobHandle
robust_sdk2.JobHandle  # .id .view_url .api_url .tmp_url .alerts .poll()
```
