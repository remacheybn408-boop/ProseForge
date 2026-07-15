from __future__ import annotations

import argparse
import asyncio

from proseforge.infrastructure.legacy_import.importer import LegacyImporter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proseforge")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    migrate = subparsers.add_parser("migrate")
    migrate_subparsers = migrate.add_subparsers(dest="migration")
    legacy = migrate_subparsers.add_parser("legacy")
    legacy.add_argument("--workspace", required=True)
    legacy.add_argument("--archive-root", default="/data/backups/legacy-import")
    args = parser.parse_args(argv)
    if args.version:
        print("1.0.0.dev0")
    elif args.command == "migrate" and args.migration == "legacy":
        report = asyncio.run(LegacyImporter(args.archive_root).import_workspace(args.workspace))
        print(report)
        return 0 if report.status == "COMPLETED" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
