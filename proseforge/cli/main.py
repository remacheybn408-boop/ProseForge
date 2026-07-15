from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
from proseforge.infrastructure.legacy_import.importer import LegacyImporter
from proseforge.operations.backup import BackupService


def _database_dump(database_url: str | None = None) -> bytes:
    url = database_url or os.getenv("PROSEFORGE_SYNC_DATABASE_URL") or os.getenv("PROSEFORGE_DATABASE_URL")
    if not url:
        raise RuntimeError("database URL is required for automatic database backup")
    normalized = url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")
    result = subprocess.run(["pg_dump", "--format=plain", "--no-owner", normalized], check=False, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "pg_dump failed")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proseforge")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    migrate = subparsers.add_parser("migrate")
    migrate_subparsers = migrate.add_subparsers(dest="migration")
    legacy = migrate_subparsers.add_parser("legacy")
    legacy.add_argument("--workspace", required=True)
    legacy.add_argument("--archive-root", default="/data/backups/legacy-import")
    legacy.add_argument("--owner-id", help="Web user ID that will own imported projects")
    backup = subparsers.add_parser("backup")
    backup.add_argument("action", choices=("create", "list", "verify", "restore"))
    backup.add_argument("archive", nargs="?")
    backup.add_argument("--source", default="/data")
    backup.add_argument("--root", default="/data/backups")
    backup.add_argument("--destination")
    backup.add_argument("--database-dump")
    backup.add_argument("--include-database", action="store_true")
    backup.add_argument("--database-url")
    backup.add_argument("--restore-database-url")
    args = parser.parse_args(argv)
    if args.version:
        print("1.0.0.dev0")
    elif args.command == "migrate" and args.migration == "legacy":
        session_factory = None
        if args.owner_id:
            from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
            from proseforge.settings import get_settings
            _, session_factory = create_engine_and_sessionmaker(get_settings())
        report = asyncio.run(LegacyImporter(args.archive_root, session_factory, args.owner_id).import_workspace(args.workspace))
        print(report)
        return 0 if report.status == "COMPLETED" else 1
    elif args.command == "backup":
        service = BackupService(args.root)
        if args.action == "create":
            if args.database_dump:
                with open(args.database_dump, "rb") as dump_file:
                    dump = dump_file.read()
            elif args.include_database:
                dump = _database_dump(args.database_url)
            else:
                dump = None
            print(service.create(args.source, database_dump=dump))
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
            if args.restore_database_url:
                print(service.restore_database(args.archive, args.restore_database_url))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
