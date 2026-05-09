"""Smoke tests for robust_sdk2 — graph shape and URI hatch behaviour."""
from datetime import date
from decimal import Decimal

from rdflib import RDF, Literal, URIRef

from robust_sdk2 import (
    ActionVerb,
    BankStatement,
    GlInput,
    JournalEntry,
    JournalLine,
    LedgerRequest,
    ReportDetails,
    Transaction,
    UnitValue,
    build_request_rdf,
)
from robust_sdk2.prefixes import AV, BS, E, ER, IC, IC_UI, PHASES, R, UV


def _minimal_request() -> LedgerRequest:
    return LedgerRequest(
        report_details=ReportDetails(
            start_date=date(2023, 7, 1),
            end_date=date(2024, 6, 30),
            report_currency="AUD",
        ),
        bank_statements=[
            BankStatement(
                account_number="1-1110",
                account_name="MyBank",
                bank_id="ANZ",
                account_currency="AUD",
                transactions=[
                    Transaction(
                        description="Test transaction",
                        date=date(2023, 8, 1),
                        debit=Decimal("100.00"),
                    ),
                ],
            ),
        ],
        action_verbs=[
            ActionVerb(name="Bank_Charges", exchanged_account="Bank_Charges"),
        ],
    )


def test_envelope_triples_present():
    g = build_request_rdf(_minimal_request())
    assert (ER.request, R.client_version, Literal("3")) in g
    assert any(g.triples((ER.request, E.has_sheet_instances, None)))


def test_sheets_advertised_via_sheet_instance():
    g = build_request_rdf(_minimal_request())
    sheet_types = {o for _s, _p, o in g.triples((None, E.sheet_instance_has_sheet_type, None))}
    # the minimal request has report_details + 1 bank_statement + unit_values + action_verbs + unit_types
    assert IC_UI.report_details_sheet in sheet_types
    assert IC.bank_statement in sheet_types
    assert IC_UI.unit_values_sheet in sheet_types
    assert IC_UI.action_verbs_sheet in sheet_types
    assert IC_UI.unit_types_sheet in sheet_types


def test_uri_hatch_populated_after_build():
    req = _minimal_request()
    g = build_request_rdf(req)

    # Top-level: builder uses ER.request
    assert req.uri == ER.request

    # Every addressable child got a URI written back
    assert req.report_details.uri is not None
    assert req.bank_statements[0].uri is not None
    assert req.bank_statements[0].transactions[0].uri is not None
    assert req.action_verbs[0].uri is not None

    # Cells dict carries per-field cell-wrapper URIs
    txn = req.bank_statements[0].transactions[0]
    assert "description" in txn.cells
    assert "date" in txn.cells
    assert "debit" in txn.cells
    assert "credit" not in txn.cells  # was None on the model, so not emitted

    # Each cell node resolves in the graph as a (cell rdf:value <value>) wrapper
    desc_cell = txn.cells["description"]
    values = [o for _s, _p, o in g.triples((desc_cell, RDF.value, None))]
    assert values == [Literal("Test transaction")]


def test_pre_set_uri_is_preserved_and_used_as_subject():
    req = _minimal_request()
    pinned = "https://my.example/txn/1"
    req.bank_statements[0].transactions[0].uri = pinned

    g = build_request_rdf(req)

    # URIRef.__eq__ to plain str returns False (rdflib's intent), so compare via str()
    assert str(req.bank_statements[0].transactions[0].uri) == pinned
    # pinned URI was used as subject of the description triple
    triples = list(g.triples((URIRef(pinned), BS.transaction_description, None)))
    assert len(triples) == 1
    # and the model's stored uri is the URIRef the validator coerced from the str
    assert isinstance(req.bank_statements[0].transactions[0].uri, URIRef)


def test_unit_types_auto_synthesised_when_omitted():
    req = _minimal_request()
    req.unit_values = [
        UnitValue(unit_type="ACME", value=Decimal("110.00")),
        UnitValue(unit_type="WIDGETS", value=Decimal("5.50")),
        UnitValue(unit_type="ACME", value=Decimal("115.00"), date=date(2024, 1, 1)),
    ]

    assert req.unit_types is None
    build_request_rdf(req)

    assert req.unit_types is not None
    names = {ut.name for ut in req.unit_types}
    assert names == {"ACME", "WIDGETS"}


def test_no_dead_excel_sheet_name_triples():
    """sdk2 must not emit the buggy `(cell excel:sheet_name "unknown")` triples
    that legacy xml2rdf produced. The legitimate `excel:sheet_instance_has_sheet_name`
    on sheet_instance entries is fine and remains."""
    g = build_request_rdf(_minimal_request())
    assert list(g.triples((None, E.sheet_name, None))) == []


def test_gl_input_journal_entry_emits_dated_first_leg_only():
    """JournalEntry → N gl_entry rows; first leg carries `ic:date`, the rest
    omit it so the calculator groups them into one statement (St). See
    `gl_input.pl` extract_gl_tx/8: a dated row mints a fresh St; an undated
    row reuses the running St0 + Date0."""
    req = _minimal_request()
    req.gl_inputs = [
        GlInput(
            default_currency="AUD",
            entries=[
                JournalEntry(
                    date=date(2023, 9, 1),
                    description="Sale",
                    lines=[
                        JournalLine(account="Bank", debit="110.00"),
                        JournalLine(account="Sales", credit="100.00"),
                        JournalLine(account="GST_Payable", credit="10.00"),
                    ],
                ),
                JournalEntry(
                    date=date(2023, 9, 2),
                    lines=[JournalLine(account="Bank_Charges", debit="2.50")],
                ),
            ],
        )
    ]
    g = build_request_rdf(req)

    legs = req.gl_inputs[0].entries[0].lines
    # First leg of each entry has its date emitted; subsequent legs do not.
    assert "date" in legs[0].cells
    assert "date" not in legs[1].cells
    assert "date" not in legs[2].cells
    # Single-line entry's only leg has it too.
    assert "date" in req.gl_inputs[0].entries[1].lines[0].cells

    # All legs are typed gl_entry and appear under the gl record's ic:items.
    leg_uris = {l.uri for e in req.gl_inputs[0].entries for l in e.lines}
    assert all((u, RDF.type, IC.gl_entry) in g for u in leg_uris)
    items_cell = req.gl_inputs[0].cells["entries"]
    items_list_head = next(g.objects(items_cell, RDF.value))
    from rdflib.collection import Collection
    listed = list(Collection(g, items_list_head))
    assert listed == [l.uri for e in req.gl_inputs[0].entries for l in e.lines]

    # Phase is emitted as a URIRef (excel:type excel:uri in the schema).
    phase_cell = req.gl_inputs[0].cells["phase"]
    assert (phase_cell, RDF.value, PHASES.main) in g

    # Sheet is advertised under ic_ui:gl_input_sheet, with auto-name "GL_input_1".
    sheet_types = {o for _s, _p, o in g.triples((None, E.sheet_instance_has_sheet_type, None))}
    assert IC_UI.gl_input_sheet in sheet_types

    # Per-leg description falls back to entry description when leg description omitted.
    desc_cell = legs[0].cells["description"]
    assert (desc_cell, RDF.value, Literal("Sale")) in g


def test_gl_input_rejects_leg_without_debit_or_credit():
    import pytest

    req = _minimal_request()
    req.gl_inputs = [
        GlInput(
            default_currency="AUD",
            entries=[
                JournalEntry(
                    date=date(2023, 9, 1),
                    lines=[JournalLine(account="Bank")],
                ),
            ],
        )
    ]
    with pytest.raises(ValueError, match="must set debit or credit"):
        build_request_rdf(req)


def test_units_count_required_when_units_type_set():
    import pytest

    req = _minimal_request()
    req.bank_statements[0].transactions.append(
        Transaction(
            description="Buy ACME",
            date=date(2023, 9, 1),
            debit=Decimal("1000"),
            units_type="ACME",
            # units_count intentionally omitted
        )
    )
    with pytest.raises(ValueError, match="units_count must be set"):
        build_request_rdf(req)
