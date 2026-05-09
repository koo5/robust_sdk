"""End-to-end demo: parse a balance-sheet-request XML file, submit it, wait for the result.

Configuration via environment:

    ROBUST_URL    base URL of the Robust deployment (default: http://localhost:8877)
    ROBUST_AUTH   "user:password" for HTTP Basic auth (default: no auth)

Usage:

    # local stack
    python examples/client.py path/to/request.xml

    # remote
    ROBUST_URL=https://robust.example.com \\
    ROBUST_AUTH=username:secret \\
        python examples/client.py path/to/request.xml

The XML adapter is `robust_sdk2.parse_balance_sheet_xml`. Replace that one
call with your own input adapter when porting to a different data source —
see `src/robust_sdk2/balance_sheet_xml.py` for the per-section pattern.
"""
import os
import sys
from pathlib import Path

from robust_sdk2 import default_action_verbs, parse_balance_sheet_xml, submit


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: python {argv[0]} <request.xml>", file=sys.stderr)
        return 2

    req = parse_balance_sheet_xml(
        Path(argv[1]),
        fallback_action_verbs=default_action_verbs(),
    )
    if req is None:
        print("input is not a balance-sheet request", file=sys.stderr)
        return 1

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
