"""End-to-end demo: build a GL-input request directly, submit it, wait for the result.

Demonstrates the higher-level journal-entry abstraction over the calculator's
GL-input rows: each `JournalEntry` carries one date and N debit/credit
`JournalLine`s; the SDK flattens to the row format the calculator consumes.

Configuration via environment (same shape as `examples/xml_client.py`):

    ROBUST_URL    base URL of the Robust deployment (default: http://localhost:8877)
    ROBUST_AUTH   "user:password" for HTTP Basic auth (default: no auth)

Usage:

    # local stack
    python examples/gl_input.py

    # remote
    ROBUST_URL=https://robust.example.com \\
    ROBUST_AUTH=username:secret \\
        python examples/gl_input.py

Replace `_build_request()` with your own request builder when porting; the
domain models in `robust_sdk2.domain` are the typed surface area.
"""
import os
import sys
from datetime import date

from robust_sdk2 import (
    GlInput,
    JournalEntry,
    JournalLine,
    LedgerRequest,
    ReportDetails,
    default_action_verbs,
    submit,
)


def _build_request() -> LedgerRequest:
    return LedgerRequest(
        report_details=ReportDetails(
            start_date=date(2023, 7, 1),
            end_date=date(2024, 6, 30),
            report_currency="AUD",
        ),
        action_verbs=default_action_verbs(),
        gl_inputs=[
            GlInput(
                default_currency="AUD",
                entries=[
                    JournalEntry(
                        date=date(2023, 8, 1),
                        description="Cash sale incl. GST",
                        lines=[
                            JournalLine(account="Banks", debit="110.00"),
                            JournalLine(account="Income", credit="100.00"),
                            JournalLine(account="Gst_GstPayableReceivable", credit="10.00"),
                        ],
                    ),
                    JournalEntry(
                        date=date(2023, 8, 15),
                        description="Bank fee",
                        lines=[
                            JournalLine(account="Bank_Charges", debit="5.00"),
                            JournalLine(account="Banks", credit="5.00"),
                        ],
                    ),
                ],
            ),
        ],
    )


def main(argv: list[str]) -> int:
    req = _build_request()

    job = submit(
        req,
        base_url=os.environ.get("ROBUST_URL", "http://localhost:8877"),
        auth=os.environ.get("ROBUST_AUTH") or None,
    )
    print(f"submitted: {job.id}\nview:      {job.view_url}\n")

    final = job.wait(
        timeout=120,
        on_progress=lambda status, elapsed: print(f"  [{elapsed:>5.1f}s] status={status}"),
    )
    result = final.get("result") or {}
    print(f"\nfinal status : {final.get('status')}")
    print(f"duration     : {final.get('duration', '?')}")
    if result.get("alerts"):
        print(f"alerts       : {result['alerts']}")
    if result.get("reports"):
        print(f"reports      : {[r.get('key') for r in result['reports']]}")
    return 0 if final.get("status") == "Success" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
