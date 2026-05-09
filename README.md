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
pip install git+https://github.com/koo5/robust_sdk
# or, working from a clone:
git clone https://github.com/koo5/robust_sdk && pip install -e robust_sdk
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

## Adapting your own data

The recommended way to use the SDK is to write a small adapter that reads
your input (CSV, YAML, a database query, …) and populates the typed domain
objects. The reference adapter — for the legacy `balanceSheetRequest` XML
shape — ships as `robust_sdk2.parse_balance_sheet_xml`:

```python
from robust_sdk2 import parse_balance_sheet_xml, default_action_verbs

req = parse_balance_sheet_xml(
    Path("request.xml"),
    fallback_action_verbs=default_action_verbs(),
)
```

The source lives at `src/robust_sdk2/balance_sheet_xml.py`. Read it and
the per-section helpers (`_bank_statements`, `_transactions`,
`_unit_values`, `_action_verbs`) for the pattern; copy and adapt the
shape for whatever your input format looks like.

`robust_sdk2.default_action_verbs()` returns the canonical LodgeIT verb
taxonomy as a starter set:

```python
from robust_sdk2 import default_action_verbs

req = LedgerRequest(..., action_verbs=default_action_verbs())
```

Bank-statement transactions resolve their action verb by matching the
transaction's `description` against `ActionVerb.name`; the calculator
throws on an unmatched description, so ship a taxonomy that covers the
descriptions in your transactions.

## End-to-end demo

`examples/xml_client.py` ties the pieces together: parse a request file, submit,
poll until the job finishes, print the result. Configuration is environment-
driven so the same script targets a local stack and a remote deployment:

```bash
# local (no auth, defaults to http://localhost:8877)
python examples/xml_client.py path/to/request.xml

# remote with HTTP Basic
ROBUST_URL=https://robust.example.com \
ROBUST_AUTH=username:secret \
    python examples/xml_client.py path/to/request.xml
```

## Advanced

- [`docs/uri_hatch.md`](docs/uri_hatch.md) — attaching arbitrary RDF triples
  to the request graph after building (custom provenance, classifier
  confidence, source-file annotations, …).

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
