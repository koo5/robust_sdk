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
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, field_validator
from rdflib import URIRef
from rdflib.term import Identifier

# rdflib's Identifier (URIRef/BNode) has no native JSON schema mapping.
# Render it as a string in generated schemas — that matches the URI hatch's
# behaviour, which coerces strings to URIRef on assignment.
_IdentifierJsonSchema = WithJsonSchema({
    "type": "string",
    "description": "An RDF identifier — pre-populate with a URI string to pin a stable URI; coerced to URIRef on assignment.",
})


class _AddressableModel(BaseModel):
    """Common base for models whose RDF identity is exposed via `uri` and `cells`."""
    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,  # so post-build .uri = "..." runs the coercer
        use_attribute_docstrings=True,  # promote PEP 257 attr docstrings to Pydantic Field.description
    )

    uri: Annotated[Optional[Identifier], _IdentifierJsonSchema] = None
    """Identifier of the RDF node representing this object (subject of the
    type-asserting triple). Pre-populate (with a `URIRef`/`BNode` or a plain
    string — strings are coerced to `URIRef`) to pin a stable identity of your
    choice; leave `None` to let the builder mint a blank node and write the
    `BNode` instance here after building."""

    cells: Annotated[
        dict[str, Identifier],
        WithJsonSchema({
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Build-output: cell-wrapper identifiers per field. Don't pre-populate.",
        }),
    ] = Field(default_factory=dict)
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
    """GL-account taxonomy identifiers. The calculator unions the resulting
    account trees and looks up every `account` string in transactions, bank
    statements, action verbs etc. against the union.

    **Bundled identifiers.** Each `https://rdf.lodgeit.net.au/v1/account_taxonomies#<name>`
    URI is an opaque identifier that the calculator resolves to a bundled XML
    file at `<deployment_base>/static/default_account_hierarchies/<name>.xml`.
    The mapping is by trailing fragment — the URI's host/path are conventional
    and not fetched. Available `<name>` values shipped with the deployment:

    - `legacy` — base hierarchy: Accounts → Net_Assets → {Assets, Liabilities},
      Comprehensive_Income → {Income, Expenses}, etc. The standard chart of
      accounts. Most callers want this.
    - `base` — minimal subset of `legacy`.
    - `investments`, `investments2`, `investments_simple`, `investments_simple2`,
      `investments__legacy`, `investments__legacy2` — overlays adding
      Financial_Investments, Trading_Accounts, etc. The defaults pair `legacy`
      with `investments__legacy2`. Pick a different overlay (or omit) when
      the report doesn't involve investment activity.
    - `livestock` — overlay for the livestock calculator.
    - `smsf` — overlay for self-managed-super-fund accounting (Member_Equity,
      distributions, etc.).

    Fetch any of them with a plain HTTP GET to inspect the structure; the
    schema is `<account name=".." role=".." normal_side="debit|credit">`
    nested arbitrarily under a single `<accountHierarchy>` root.

    **Custom taxonomies (advanced).** Any entry that isn't a bundled-identifier
    URI is treated as a URL or local path. The calculator tries to load it as
    `<accountHierarchy>` XML first; if no such root element is found, it
    hands the URL to `arelle` and tries to reconstruct an account tree from
    an XBRL taxonomy schema. Both paths are real and supported but not
    further surfaced in this SDK yet — open a discussion if you need them.

    **Auto-minted accounts.** The base taxonomies are *not* the whole story.
    During request processing, `ensure_system_accounts_exist` adds child
    accounts driven by request data and unit types:

    - **Bank statements**: each `BankStatement.account_name` becomes a child
      of `Banks` (role `Banks/<account_name>`), plus a paired
      `Currency_Movement/<account_name>` under `Currency_Movement`. So
      posting transactions to `Banks` directly works, but the *natural*
      target is the per-statement child — supplying a `BankStatement` with
      `account_name="ANZ_Cheque"` creates `Banks/ANZ_Cheque`, and you can
      post against that name.
    - **Livestock units**: per `units_type` of livestock, four accounts are
      added (`<Type>Cogs`, `<Type>Sales`, `<Type>Count`, and a Rations
      sub-account under Cogs).
    - **Traded financial units**: per unit appearing in `Transaction.units_type`
      (and its corresponding `UnitValue`), accounts are added under
      `Financial_Investments/<exchanged_account>/<unit>` and under each
      Trading_Accounts realization branch (realized/unrealized ×
      withCurrencyMovement/onlyCurrencyMovement × unit).
    - **SMSF distributions**: per distribution unit, sub-accounts for
      Distribution_Cash, Resolved_Accrual, Foreign_Credit, Franking_Credit,
      TFN/ABN_Withholding_Tax are added under `Distribution_Revenue/<unit>`.
    - **Subcategorize_by_bank**: any taxonomy account marked with
      `accounts:subcategorize_by_bank` gets one child per bank account.

    Action verbs' `exchanged_account` and `trading_account` are *not*
    auto-minted — they must resolve to an existing account name (or role
    expression), or transaction processing will error out.

    To see the effective hierarchy a given request produced (taxonomy ∪
    auto-minted), submit any request and read the `accounts0_json` /
    `accounts1_json` / `accounts2_json` reports — they list every account
    with its `name`, `role`, `parent`, and `normal_side`."""


class LedgerRequest(_AddressableModel):
    """A complete ledger-calculator request.

    Pass to `robust_sdk2.client.submit` to run, or to
    `robust_sdk2.builder.build_request_rdf` to get the rdflib graph.

    Discovering valid account names: every `account` string elsewhere in this
    request (bank-statement-transaction debits, journal-line postings, action
    verbs' `exchanged_account`, etc.) must resolve against the GL-account tree
    formed by `report_details.account_taxonomies` plus runtime-minted accounts.
    See the docstring on `ReportDetails.account_taxonomies` for the rules,
    bundled identifiers, and which accounts get auto-minted from request data.
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
