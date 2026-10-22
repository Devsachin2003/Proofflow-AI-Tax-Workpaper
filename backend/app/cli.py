"""Command line: `python -m app.cli import-packet [--path P]`, `run-validation`, `reset-workpaper`."""

import argparse
import json
import sys

from app.core.config import get_settings
from app.db.session import session_factory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_imp = sub.add_parser("import-packet", help="Idempotently import the packet and seed the workpaper")
    p_imp.add_argument("--path", default=None)
    p_imp.add_argument("--no-validate", action="store_true")
    sub.add_parser("run-validation", help="Run the independent validation engine")
    sub.add_parser("reset-workpaper", help="Delete all human work (keeps the immutable baseline)")
    args = parser.parse_args(argv)

    db = session_factory()()
    try:
        if args.cmd == "import-packet":
            from app.services.importer import import_packet

            result = import_packet(db, args.path or get_settings().packet_path)
            print(json.dumps(result, indent=1, default=str))
            if not args.no_validate:
                from app.services.findings import run_validation

                summary = run_validation(db, actor_id=None)
                print(json.dumps({"validation": summary}, default=str))
        elif args.cmd == "run-validation":
            from app.services.findings import run_validation

            print(json.dumps(run_validation(db, actor_id=None), default=str))
        elif args.cmd == "reset-workpaper":
            from app.services.admin import reset_workpaper

            print(json.dumps(reset_workpaper(db), default=str))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
