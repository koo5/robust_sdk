"""Pydantic models for a Robust ledger calculator request.

Construct a `LedgerRequest` from the leaf pieces (transactions, action verbs,
unit values, …) and hand it to `robust_sdk2.client.submit` to run a calculation,
or to `robust_sdk2.builder.build_request_rdf` to obtain the rdflib graph
directly.

URI hatches
-----------
Every model carries two URI-hatch fields, both write-back-after-build:

- `uri`: identifier of the row entity (the subject of the type-asserting
  triple). Pre-populate to pin a stable URI of your choice; leave None to
  let the builder mint a blank node and write its identifier here.

- `cells`: dict from Python field name to the cell-wrapper URI for that
  field's value. Build-output only — populated by the builder, with one
  entry per field that was actually emitted (optional fields appear only
  if set). Sheet-data list-cells (e.g. the list of transactions inside a
  bank statement) appear here too under the corresponding field name.

Use the URIs to attach extra triples to the same graph after building.
The cell layer is the natural place to hang per-value provenance — the
spreadsheet pipeline uses it for sheet-name + col/row origin annotations
that surface in error messages and the report explorer; you can attach
whatever shape fits your input (yaml file:line, source-system query id,
LLM confidence score, …):

    g = build_request_rdf(req)
    txn = req.bank_statements[0].transactions[0]
    g.add((txn.uri, MY_NS.note, Literal("…")))                  # row-level
    g.add((txn.cells["description"], MY_NS.line, Literal(42)))  # cell-level

`uri` / `cells` values are real `rdflib.term.Identifier` instances (URIRef
or BNode), so they slot into rdflib triples directly. When you pre-populate
`uri` with a string, the model coerces it to `URIRef` on assignment.
"""
import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from rdflib import URIRef
from rdflib.term import Identifier


class _AddressableModel(BaseModel):
    """Common base for models whose RDF identity is exposed via `uri` and `cells`."""
    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,  # so post-build .uri = "..." runs the coercer
    )

    uri: Optional[Identifier] = None
    """Identifier of the RDF node representing this object (subject of the
    type-asserting triple). Pre-populate (with a `URIRef`/`BNode` or a plain
    string — strings are coerced to `URIRef`) to pin a stable identity of your
    choice; leave `None` to let the builder mint a blank node and write the
    `BNode` instance here after building."""

    cells: dict[str, Identifier] = Field(default_factory=dict)
    """Per-property cell-wrapper identifiers, keyed by the Python field name.
    Populated by the builder. Optional fields appear only if they were emitted.
    List-typed fields appear as a single entry whose identifier wraps the RDF
    Collection.

    The builder emits no extra triples on these cell wrappers itself — they
    are a clean attachment point for per-value provenance the caller wants to
    add (spreadsheet col/row + sheet name, source file/line, etc.)."""

    @field_validator("uri", mode="before")
    @classmethod
    def _coerce_uri(cls, v):
        if v is None or isinstance(v, Identifier):
            return v
        if isinstance(v, str):
            return URIRef(v)
        raise TypeError(f"uri must be str, URIRef, BNode, or None — got {type(v).__name__}")


class Transaction(_AddressableModel):
    """A single bank-statement transaction row."""
    description: str
    date: datetime.date
    debit: Optional[Decimal] = None
    """Amount debited from the account on this date (in the account's currency)."""
    credit: Optional[Decimal] = None
    """Amount credited to the account on this date (in the account's currency)."""
    units_type: Optional[str] = None
    """For non-cash transactions (e.g. share purchases): the unit type id.
    Must match the `unit_type` of some `UnitValue` for valuation to work."""
    units_count: Optional[Decimal] = None
    """Number of units transacted; required when `units_type` is set."""


class BankStatement(_AddressableModel):
    """One bank-account statement: account metadata + a list of transactions."""
    account_number: str
    account_name: str
    bank_id: str
    account_currency: str
    """ISO 4217 code (or any string the calculator's unit-type set recognises)."""
    transactions: list[Transaction] = []


class ActionVerb(_AddressableModel):
    """An entry in the action-verb taxonomy.

    Action verbs map a transaction's intent (e.g. "Invest_In", "Bank_Charges")
    to the GL account where the offsetting entry goes, and optionally to a
    trading account for gain/loss tracking.
    """
    name: str
    """The action-verb id, e.g. "Invest_In", "Bank_Charges"."""
    exchanged_account: str
    """GL account that receives the corresponding/opposite entry for transactions
    classified under this verb."""
    description: Optional[str] = None
    trading_account: Optional[str] = None
    """GL account where realised gains/losses for this verb are tracked
    (typically only meaningful for investment-related verbs)."""
    gst_rate_percent: Optional[Decimal] = None
    """If set, transactions classified under this verb are split into a base
    amount and a GST component at this rate (e.g. Decimal("10") for 10%).
    The calculator pairs this with `gst_payable_account` (for sales-side
    verbs) or `gst_receivable_account` (for purchases-side verbs) to post
    the GST component to the right GL account."""
    gst_receivable_account: Optional[str] = None
    """GL account for the GST receivable component (purchases). Set together
    with `gst_rate_percent` for input-tax verbs."""
    gst_payable_account: Optional[str] = None
    """GL account for the GST payable component (sales). Set together with
    `gst_rate_percent` for output-tax verbs."""


class UnitValue(_AddressableModel):
    """A market-value observation for a non-cash unit at a date."""
    unit_type: str
    """Unit type id; matches `Transaction.units_type`."""
    value: Decimal
    date: Optional[datetime.date] = None
    """Defaults to `LedgerRequest.report_details.end_date` when omitted."""
    currency: Optional[str] = None
    """Defaults to `LedgerRequest.report_details.report_currency` when omitted."""


class UnitType(_AddressableModel):
    """A unit-type declaration row.

    If `LedgerRequest.unit_types` is left as None, the builder synthesises one
    `UnitType` per distinct `UnitValue.unit_type` with the default category.
    Provide explicit instances to override the category or to declare types
    not referenced by any `UnitValue`.
    """
    name: str
    category: str = "Financial_Investments"


class JournalLine(_AddressableModel):
    """One leg of a journal entry: a debit or credit on a single account.

    Belongs to a `JournalEntry` and inherits its date. Each line posts to
    one GL account; combine multiple lines under one `JournalEntry` to
    represent a balanced multi-leg posting (e.g. dr Bank / cr Sales).
    """
    account: str
    """GL account identifier. Either a name from the taxonomy
    (e.g. `"Bank"`) or a parametrised role expression like
    `"!Investment_Income!<currency>!"`. Parametrised forms consume entries
    from `params` left-to-right to fill `<slot>` placeholders."""
    debit: Optional[str] = None
    """Amount string parsed by the calculator's currency-vector grammar
    (e.g. `"100.00"` to use the parent `GlInput`'s `default_currency`, or
    `"100.00 USD"` for an explicit currency). Mutually optional with
    `credit`."""
    credit: Optional[str] = None
    description: Optional[str] = None
    """Per-leg description. Falls back to the parent `JournalEntry.description`
    when omitted, then to `"unknown"` if neither is set."""
    params: list[str] = []
    """Up to 5 parameter strings for parametrised account specifiers."""


class JournalEntry(_AddressableModel):
    """A balanced journal posting: one date, one or more debit/credit lines.

    Maps onto N rows in the calculator's GL-input sheet (one per `JournalLine`),
    all sharing this `date`. The SDK handles that flattening; callers think
    in terms of journal entries.
    """
    date: datetime.date
    description: Optional[str] = None
    """Default description applied to lines that don't set their own."""
    lines: list[JournalLine]


class GlInput(_AddressableModel):
    """A batch of journal entries posted to the general ledger.

    A request may carry multiple `GlInput` batches — one per phase, or
    grouped by source system. The calculator concatenates their entries.
    """
    default_currency: str
    """Currency used for line debit/credit amounts that omit a currency
    code (e.g. just `"100.00"` rather than `"100.00 USD"`)."""
    phase: Literal["main", "opening_balance"] = "main"
    """Reporting phase: `"opening_balance"` seeds carry-forward state at the
    start of the period; `"main"` is the reporting period itself."""
    entries: list[JournalEntry] = []


class ReportDetails(_AddressableModel):
    """Top-level report metadata (currency, date range, taxonomies)."""
    start_date: datetime.date
    end_date: datetime.date
    report_currency: str
    """ISO 4217 code (or any unit-type id the calculator recognises) used as
    the report's reference currency. Determines the default for `UnitValue.currency`."""
    cost_or_market: str = "market"
    """One of "market", "cost". Selects the asset valuation basis."""
    pricing_method: str = "lifo"
    """One of "lifo", "fifo". Inventory accounting method."""
    account_taxonomies: list[str] = [
        "https://rdf.lodgeit.net.au/v1/account_taxonomies#legacy",
        "https://rdf.lodgeit.net.au/v1/account_taxonomies#investments__legacy2",
    ]
    """URIs of the GL-account taxonomies the calculator should resolve account
    names against. The defaults give standard chart-of-accounts coverage."""


class LedgerRequest(_AddressableModel):
    """A complete ledger-calculator request.

    Pass to `robust_sdk2.client.submit` to run, or to
    `robust_sdk2.builder.build_request_rdf` to get the rdflib graph.
    """
    report_details: ReportDetails
    bank_statements: list[BankStatement] = []
    gl_inputs: list[GlInput] = []
    """Direct general-ledger journal-entry batches. Use these to feed
    pre-classified transactions (debit/credit pairs against named GL
    accounts) without going through bank-statement + action-verb
    classification."""
    action_verbs: list[ActionVerb] = []
    unit_values: list[UnitValue] = []
    unit_types: Optional[list[UnitType]] = None
    """When None, the builder synthesises one `UnitType` per distinct
    `UnitValue.unit_type` with the default category."""
