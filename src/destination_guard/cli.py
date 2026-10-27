"""Command line interface for demos, preflight checks, and scheduled audits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import DestinationGuardError
from .guard import DestinationGuard


def _demo_registry() -> Path:
    return Path(__file__).resolve().parent / "data" / "destination-pins.demo.json"


def _print_audit(guard: DestinationGuard, as_json: bool) -> int:
    results = guard.audit()
    if as_json:
        print(json.dumps([result.__dict__ for result in results], indent=2))
    else:
        for result in results:
            if result.ok:
                name = result.resolved_name or "unnamed"
                print(
                    f'AUDIT OK pin={result.pin} destination="{name}" id={result.resolved_id}'
                )
            else:
                print(f"AUDIT {result.status} pin={result.pin} detail={result.detail}")
    return 0 if all(result.ok for result in results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="destination-guard",
        description="Fail closed unless an outbound integration proves its destination.",
    )
    parser.add_argument("--registry", help="path to a destination pin registry")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo", help="run an offline fictional send")
    check = subparsers.add_parser("check", help="preflight one pin without sending")
    check.add_argument("pin")
    audit = subparsers.add_parser("audit", help="resolve every pin without sending")
    audit.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry_path = Path(args.registry).expanduser() if args.registry else _demo_registry()
    try:
        guard = DestinationGuard.from_file(str(registry_path))
        if args.command == "demo":
            def fictional_upload() -> dict[str, object]:
                return {
                    "upload": {"id": "video_demo_001"},
                    "destination": {
                        "id": "channel_demo_2048",
                        "name": "Northwind Dental Video",
                    },
                }

            guard.execute("northwind_video", fictional_upload)
            print("DEMO COMPLETE sent=1 verified=1")
            return 0
        if args.command == "check":
            guard.preflight(args.pin)
            return 0
        return _print_audit(guard, args.as_json)
    except DestinationGuardError as exc:
        print(f"REFUSED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
