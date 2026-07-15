from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proseforge")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)
    if args.version:
        print("1.0.0.dev0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
