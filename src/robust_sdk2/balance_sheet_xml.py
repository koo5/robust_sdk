"""Adapter: legacy `balanceSheetRequest` XML → `LedgerRequest`.

This is the reference adapter shipped with the SDK. It's both directly usable
(import and call) and intended as a starter template for adapting other input
formats — the per-section helpers (`_bank_statements`, `_transactions`,
`_unit_values`, `_action_verbs`) show how to map an external structure onto
the typed domain.

Usage:

    from pathlib import Path
    from robust_sdk2 import (
        parse_balance_sheet_xml, build_request_rdf, default_action_verbs, submit,
    )

    req = parse_balance_sheet_xml(
        Path("request.xml"),
        fallback_action_verbs=default_action_verbs(),
    )
    g = build_request_rdf(req)        # inspect the RDF
    job = submit(req, base_url, auth=("user", "pass"))   # …or submit and wait
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from .domain import (
    ActionVerb,
    BankStatement,
    LedgerRequest,
    ReportDetails,
    Transaction,
    UnitValue,
)


def parse_balance_sheet_xml(
    xml_path: Path,
    *,
    fallback_action_verbs: Optional[list[ActionVerb]] = None,
) -> Optional[LedgerRequest]:
    """Translate a balance-sheet-request XML into a `LedgerRequest`.

    Returns `None` if the input is not a balance-sheet request.

    `fallback_action_verbs` is used when the input has no `<actionTaxonomy>`.
    Bank-statement transactions reference verbs by name (their `transdesc`
    field is matched against `ActionVerb.name`); the calculator throws if a
    referenced verb isn't present, so any input whose transactions use named
    verbs needs a non-empty action-verb set. Pass
    `robust_sdk2.default_action_verbs()` for the standard LodgeIT taxonomy,
    or your own list.

    GST fields on `<action>` elements (`gstRatePercent`,
    `gstReceivableAccount`, `gstPayableAccount`) are translated to the
    corresponding `ActionVerb` fields (`gst_rate_percent`,
    `gst_receivable_account`, `gst_payable_account`); the calculator picks
    them up per-verb to drive the GST split.
    """
    root = ET.parse(xml_path).getroot()
    req_el = root.find("balanceSheetRequest")
    if req_el is None:
        return None

    start_date = _parse_date(req_el.findtext("startDate"))
    end_date = _parse_date(req_el.findtext("endDate"))
    report_currency = (req_el.findtext("reportCurrency/unitType") or "").strip()

    action_verbs = _action_verbs(req_el)
    if not action_verbs and fallback_action_verbs is not None:
        action_verbs = fallback_action_verbs

    return LedgerRequest(
        report_details=ReportDetails(
            start_date=start_date,
            end_date=end_date,
            report_currency=report_currency,
        ),
        bank_statements=_bank_statements(req_el, default_currency=report_currency),
        unit_values=_unit_values(
            req_el,
            start_date=start_date,
            end_date=end_date,
            default_currency=report_currency,
        ),
        action_verbs=action_verbs,
    )


# --- per-section adapters ------------------------------------------------

def _bank_statements(req_el: ET.Element, *, default_currency: str) -> list[BankStatement]:
    bst = req_el.find("bankStatement")
    if bst is None:
        return []
    out = []
    for accd in bst.findall("accountDetails"):
        out.append(
            BankStatement(
                account_number=accd.findtext("accountNo") or "",
                account_name=accd.findtext("accountName") or "",
                bank_id=accd.findtext("bankID") or "",
                account_currency=accd.findtext("currency") or default_currency,
                transactions=_transactions(accd.find("transactions")),
            )
        )
    return out


def _transactions(txs_el: Optional[ET.Element]) -> list[Transaction]:
    if txs_el is None:
        return []
    out = []
    for t in txs_el:
        tx = Transaction(
            description=t.findtext("transdesc") or "",
            date=_parse_date(t.findtext("transdate")),
            debit=_decimal_or_none(t.findtext("debit")),
            credit=_decimal_or_none(t.findtext("credit")),
        )
        # Unit references — set both fields together or neither.
        unit = t.findtext("unit")
        unit_type = t.findtext("unitType")
        if unit and unit_type:
            tx.units_type = unit_type
            tx.units_count = Decimal(unit)
        out.append(tx)
    return out


def _unit_values(
    req_el: ET.Element,
    *,
    start_date: date,
    end_date: date,
    default_currency: str,
) -> list[UnitValue]:
    uv_root = req_el.find("unitValues")
    if uv_root is None:
        return []
    out = []
    for uv_el in uv_root.findall("unitValue"):
        # The legacy format uses "opening" and "closing" as date keywords.
        d_str = (uv_el.findtext("unitValueDate") or "").strip()
        if d_str == "opening":
            d = start_date
        elif d_str == "closing" or d_str == "":
            d = end_date
        else:
            d = _parse_date(d_str)

        out.append(
            UnitValue(
                unit_type=uv_el.findtext("unitType") or "",
                value=Decimal(uv_el.findtext("unitValue") or "0"),
                date=d,
                currency=uv_el.findtext("unitValueCurrency") or default_currency,
            )
        )
    return out


def _action_verbs(req_el: ET.Element) -> list[ActionVerb]:
    at_root = req_el.find("actionTaxonomy")
    if at_root is None:
        return []
    out = []
    for av_el in at_root.findall("action"):
        ex = av_el.findtext("exchangeAccount")
        if not ex:
            continue
        out.append(
            ActionVerb(
                name=av_el.findtext("id") or "",
                exchanged_account=ex,
                description=av_el.findtext("description") or None,
                trading_account=av_el.findtext("tradingAccount") or None,
                gst_rate_percent=_decimal_or_none(av_el.findtext("gstRatePercent")),
                gst_receivable_account=av_el.findtext("gstReceivableAccount") or None,
                gst_payable_account=av_el.findtext("gstPayableAccount") or None,
            )
        )
    return out


# --- small helpers --------------------------------------------------------

def _parse_date(s: Optional[str]) -> date:
    if not s:
        raise ValueError("missing date")
    # Tolerate ISO datetime-with-time (e.g. "2014-08-28T10:58:40.000165Z").
    return date.fromisoformat(s.split("T", 1)[0])


def _decimal_or_none(s: Optional[str]) -> Optional[Decimal]:
    return Decimal(s) if s not in (None, "") else None
