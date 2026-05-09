"""Build the RDF graph for a calculator request from a `LedgerRequest`."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from rdflib import Graph, BNode, URIRef, Literal, RDF
from rdflib.collection import Collection
from rdflib.term import Identifier

from .domain import (
    LedgerRequest,
    ReportDetails,
    BankStatement,
    Transaction,
    ActionVerb,
    UnitValue,
    UnitType,
    GlInput,
    JournalEntry,
    JournalLine,
    _AddressableModel,
)
from .prefixes import V1, R, E, ER, BS, IC, IC_UI, AV, UV, PHASES


def build_request_rdf(req: LedgerRequest) -> Graph:
    """Build and return the rdflib Graph for `req`.

    Side effects on `req`: every addressable model whose `uri` was None gets
    its `uri` populated with the freshly minted blank-node identifier; models
    that already had `uri` set are left unchanged. This is the URI hatch
    documented on `_AddressableModel`.
    """
    return _Builder(req).build()


class _Builder:
    def __init__(self, req: LedgerRequest):
        self.req = req
        self.g = Graph()
        self.sheet_instances: list[Identifier] = []
        if req.unit_types is None:
            seen: dict[str, UnitType] = {}
            for uv in req.unit_values:
                seen.setdefault(uv.unit_type, UnitType(name=uv.unit_type))
            req.unit_types = list(seen.values())

    def build(self) -> Graph:
        self._set_uri(self.req, ER.request)
        self._add_report_details_sheet()
        self._add_bank_statement_sheets()
        self._add_gl_input_sheets()
        self._add_unit_values_sheet()
        self._add_action_verbs_sheet()
        self._add_unit_types_sheet()

        # `:request excel:has_sheet_instances` points DIRECTLY at the RDF list,
        # not via a cell-wrapper. The Prolog calculator iterates that list to
        # find sheet_instances; cell-wrapping it would be invisible to that
        # iteration and the once() inside process_rdf_request would fail.
        sheet_instances_list = BNode()
        Collection(self.g, sheet_instances_list, self.sheet_instances)
        self.req.cells["sheet_instances"] = sheet_instances_list  # still expose for callers
        self.g.add((ER.request, E.has_sheet_instances, sheet_instances_list))
        self.g.add((ER.request, R.client_version, Literal("3")))
        return self.g

    def _set_uri(self, model: _AddressableModel, default: Identifier | None = None) -> Identifier:
        """Resolve the RDF identifier for a model and write it back."""
        if model.uri is not None:
            return model.uri
        node = default if default is not None else BNode()
        model.uri = node
        return node

    def _emit_cell(self, model: _AddressableModel, field: str, value: Any) -> Identifier:
        """Wrap a value as a cell bnode and record the cell node on `model.cells[field]`."""
        cell = BNode()
        if not isinstance(value, Identifier):
            value = Literal(value)
        self.g.add((cell, RDF.value, value))
        model.cells[field] = cell
        return cell

    def _emit_list_cell(self, model: _AddressableModel, field: str, items: list[Identifier]) -> Identifier:
        """Wrap a list of node ids as an RDF Collection in a cell, recorded on `model.cells[field]`."""
        head = BNode()
        Collection(self.g, head, items)
        return self._emit_cell(model, field, head)

    @staticmethod
    def _date_literal(d: date) -> Literal:
        return Literal(datetime.combine(d, datetime.min.time()))

    def _add_sheet(self, sheet_type: URIRef, name: str, record: Identifier) -> None:
        inst = BNode()
        self.g.add((inst, E.sheet_instance_has_sheet_type, sheet_type))
        self.g.add((inst, E.sheet_instance_has_sheet_name, Literal(name)))
        self.g.add((inst, E.sheet_instance_has_sheet_data, record))
        self.sheet_instances.append(inst)

    def _add_report_details_sheet(self) -> None:
        rd = self.req.report_details
        node = self._set_uri(rd)
        self.g.add((node, RDF.type, BS.report_details))
        self.g.add((node, IC.cost_or_market, self._emit_cell(rd, "cost_or_market", IC[rd.cost_or_market])))
        self.g.add((node, IC.currency, self._emit_cell(rd, "report_currency", rd.report_currency)))
        self.g.add((node, IC["from"], self._emit_cell(rd, "start_date", self._date_literal(rd.start_date))))
        self.g.add((node, IC["to"], self._emit_cell(rd, "end_date", self._date_literal(rd.end_date))))
        self.g.add((node, IC.pricing_method, self._emit_cell(rd, "pricing_method", IC[rd.pricing_method])))

        tax_nodes: list[Identifier] = []
        for tax_uri in rd.account_taxonomies:
            t = BNode()
            # Each taxonomy entry is itself a tiny anonymous wrapper. The leaf
            # value (the URL) goes through a cell, but there's no addressable
            # model for the wrapper, so it doesn't get a cells[] entry.
            url_cell = BNode()
            self.g.add((url_cell, RDF.value, URIRef(tax_uri)))
            self.g.add((t, V1["account_taxonomies#url"], url_cell))
            tax_nodes.append(t)
        self.g.add((node, IC_UI.account_taxonomies, self._emit_list_cell(rd, "account_taxonomies", tax_nodes)))

        self._add_sheet(IC_UI.report_details_sheet, "report_details", node)

    def _add_bank_statement_sheets(self) -> None:
        for stmt in self.req.bank_statements:
            tx_nodes: list[Identifier] = []
            for tx in stmt.transactions:
                tx_node = self._set_uri(tx)
                self.g.add((tx_node, BS.transaction_description, self._emit_cell(tx, "description", tx.description)))
                self.g.add((tx_node, BS.bank_transaction_date, self._emit_cell(tx, "date", self._date_literal(tx.date))))
                if tx.debit is not None:
                    self.g.add((tx_node, BS.debit, self._emit_cell(tx, "debit", tx.debit)))
                if tx.credit is not None:
                    self.g.add((tx_node, BS.credit, self._emit_cell(tx, "credit", tx.credit)))
                if tx.units_type is not None:
                    self.g.add((tx_node, BS.units_type, self._emit_cell(tx, "units_type", tx.units_type)))
                    if tx.units_count is None:
                        raise ValueError(
                            f"Transaction {tx_node!r}: units_count must be set when units_type is set"
                        )
                    self.g.add((tx_node, BS.units_count, self._emit_cell(tx, "units_count", tx.units_count)))
                tx_nodes.append(tx_node)

            stmt_node = self._set_uri(stmt)
            self.g.add((stmt_node, RDF.type, BS.bank_statement))
            self.g.add((stmt_node, BS.account_currency, self._emit_cell(stmt, "account_currency", stmt.account_currency)))
            self.g.add((stmt_node, BS.account_name, self._emit_cell(stmt, "account_name", stmt.account_name)))
            self.g.add((stmt_node, BS.account_number, self._emit_cell(stmt, "account_number", stmt.account_number)))
            self.g.add((stmt_node, BS.bank_id, self._emit_cell(stmt, "bank_id", stmt.bank_id)))
            self.g.add((stmt_node, BS.items, self._emit_list_cell(stmt, "transactions", tx_nodes)))

            self._add_sheet(IC.bank_statement, stmt.account_name, stmt_node)

    def _add_gl_input_sheets(self) -> None:
        for idx, gl in enumerate(self.req.gl_inputs):
            line_nodes: list[Identifier] = []
            for entry in gl.entries:
                if not entry.lines:
                    raise ValueError(
                        f"JournalEntry on {entry.date.isoformat()} has no lines"
                    )
                for leg_idx, line in enumerate(entry.lines):
                    if line.debit is None and line.credit is None:
                        raise ValueError(
                            f"JournalLine on {entry.date.isoformat()} for "
                            f"account {line.account!r}: must set debit or credit"
                        )
                    if len(line.params) > 5:
                        raise ValueError(
                            f"JournalLine on {entry.date.isoformat()} for "
                            f"account {line.account!r}: at most 5 params, got "
                            f"{len(line.params)}"
                        )
                    line_node = self._set_uri(line)
                    self.g.add((line_node, RDF.type, IC.gl_entry))
                    # The calculator uses presence of `ic:date` as the
                    # journal-entry boundary (gl_input.pl extract_gl_tx/8):
                    # a dated row mints a fresh statement (St1); undated
                    # rows reuse the running St0 + Date0. We emit `ic:date`
                    # on the first leg of each JournalEntry only, so all
                    # legs end up in the same statement.
                    if leg_idx == 0:
                        self.g.add((line_node, IC.date, self._emit_cell(line, "date", self._date_literal(entry.date))))
                    self.g.add((line_node, IC.account, self._emit_cell(line, "account", line.account)))
                    desc = line.description if line.description is not None else entry.description
                    if desc is not None:
                        self.g.add((line_node, IC.description, self._emit_cell(line, "description", desc)))
                    if line.debit is not None:
                        self.g.add((line_node, IC.debit, self._emit_cell(line, "debit", line.debit)))
                    if line.credit is not None:
                        self.g.add((line_node, IC.credit, self._emit_cell(line, "credit", line.credit)))
                    for i, p in enumerate(line.params, start=1):
                        self.g.add((line_node, IC[f"param{i}"], self._emit_cell(line, f"param{i}", p)))
                    line_nodes.append(line_node)

            gl_node = self._set_uri(gl)
            self.g.add((gl_node, RDF.type, IC.gl))
            self.g.add((gl_node, IC.default_currency, self._emit_cell(gl, "default_currency", gl.default_currency)))
            phase_uri = PHASES[gl.phase]
            self.g.add((gl_node, IC.phase, self._emit_cell(gl, "phase", phase_uri)))
            self.g.add((gl_node, IC["items"], self._emit_list_cell(gl, "entries", line_nodes)))

            # Sheet-type discrepancy: the schema declares `ic_ui:gl_input_sheet`
            # as the sheet_type and real spreadsheet fixtures emit that, but the
            # calculator's `extract_gl_inputs` (gl_input.pl:9) looks up sheets
            # via `get_sheets_data(ic_ui:gl, …)` — the template URI, not the
            # sheet-type URI. So we emit `ic_ui:gl` to actually exercise the
            # extraction. (Bank statements use IC.bank_statement consistently
            # both sides; GL is the odd one out.)
            self._add_sheet(IC_UI.gl, f"GL_input_{idx + 1}", gl_node)

    def _add_unit_values_sheet(self) -> None:
        nodes: list[Identifier] = []
        for uv in self.req.unit_values:
            node = self._set_uri(uv)
            d = uv.date or self.req.report_details.end_date
            c = uv.currency or self.req.report_details.report_currency
            self.g.add((node, RDF.type, IC.unit_value))
            self.g.add((node, UV.name, self._emit_cell(uv, "unit_type", uv.unit_type)))
            self.g.add((node, UV.value, self._emit_cell(uv, "value", uv.value)))
            self.g.add((node, UV.date, self._emit_cell(uv, "date", self._date_literal(d))))
            self.g.add((node, UV.currency, self._emit_cell(uv, "currency", c)))
            nodes.append(node)
        self._add_sheet(IC_UI.unit_values_sheet, "unit_values", self._emit_list_cell(self.req, "unit_values", nodes))

    def _add_action_verbs_sheet(self) -> None:
        nodes: list[Identifier] = []
        for av in self.req.action_verbs:
            node = self._set_uri(av)
            self.g.add((node, RDF.type, IC.action_verb))
            self.g.add((node, AV.name, self._emit_cell(av, "name", av.name)))
            if av.description:
                self.g.add((node, AV.description, self._emit_cell(av, "description", av.description)))
            self.g.add((node, AV.exchanged_account, self._emit_cell(av, "exchanged_account", av.exchanged_account)))
            if av.trading_account:
                self.g.add((node, AV.trading_account, self._emit_cell(av, "trading_account", av.trading_account)))
            if av.gst_rate_percent is not None:
                self.g.add((node, AV.gst_rate_percent, self._emit_cell(av, "gst_rate_percent", av.gst_rate_percent)))
            if av.gst_receivable_account:
                self.g.add((node, AV.gst_receivable_account, self._emit_cell(av, "gst_receivable_account", av.gst_receivable_account)))
            if av.gst_payable_account:
                self.g.add((node, AV.gst_payable_account, self._emit_cell(av, "gst_payable_account", av.gst_payable_account)))
            nodes.append(node)
        self._add_sheet(IC_UI.action_verbs_sheet, "action_verbs", self._emit_list_cell(self.req, "action_verbs", nodes))

    def _add_unit_types_sheet(self) -> None:
        nodes: list[Identifier] = []
        for ut in self.req.unit_types or []:
            node = self._set_uri(ut)
            self.g.add((node, IC.unit_type_name, self._emit_cell(ut, "name", ut.name)))
            self.g.add((node, IC.unit_type_category, self._emit_cell(ut, "category", ut.category)))
            nodes.append(node)
        self._add_sheet(IC_UI.unit_types_sheet, "unit_types", self._emit_list_cell(self.req, "unit_types", nodes))
