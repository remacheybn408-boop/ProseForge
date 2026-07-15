from __future__ import annotations

import argparse
import asyncio
from proseforge.infrastructure.legacy_import.importer import LegacyImporter
from proseforge.operations.backup import BackupService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proseforge")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    migrate = subparsers.add_parser("migrate")
    migrate_subparsers = migrate.add_subparsers(dest="migration")
    legacy = migrate_subparsers.add_parser("legacy")
    legacy.add_argument("--workspace", required=True)
    legacy.add_argument("--archive-root", default="/data/backups/legacy-import")
    backup = subparsers.add_parser("backup")
    backup.add_argument("action", choices=("create", "list", "verify", "restore"))
    backup.add_argument("archive", nargs="?")
    backup.add_argument("--source", default="/data")
    backup.add_argument("--root", default="/data/backups")
    backup.add_argument("--destination")
    args = parser.parse_args(argv)
    if args.version:
        print("1.0.0.dev0")
    elif args.command == "migrate" and args.migration == "legacy":
        report = asyncio.run(LegacyImporter(args.archive_root).import_workspace(args.workspace))
        print(report)
        return 0 if report.status == "COMPLETED" else 1
    elif args.command == "backup":
        service = BackupService(args.root)
        if args.action == "create":
            print(service.create(args.source))
        elif args.action == "list":
            for archive in service.list():
                print(archive)
        elif args.archive is None:
            parser.error("backup verify/restore requires an archive")
        elif args.action == "verify":
            print(service.verify(args.archive))
        elif args.action == "restore":
            if not args.destination:
                parser.error("backup restore requires --destination staging path")
            print(service.restore(args.archive, args.destination))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
