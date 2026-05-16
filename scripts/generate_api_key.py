#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets
import sys


def generate_api_key(token_bytes: int = 32, prefix: str = "llm") -> str:
    token = secrets.token_urlsafe(token_bytes)
    if not prefix:
        return token
    return f"{prefix}_{token}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate strong URL-safe API keys for Llama Manager agent/controller config."
    )
    parser.add_argument(
        "--bytes",
        type=int,
        default=32,
        help="Number of random bytes before URL-safe encoding. Default: 32.",
    )
    parser.add_argument(
        "--prefix",
        default="llm",
        help="Prefix before the generated token. Use an empty string for no prefix. Default: llm.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of keys to print. Default: 1.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.bytes < 16:
        raise SystemExit("--bytes must be at least 16")
    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    for _ in range(args.count):
        print(generate_api_key(token_bytes=args.bytes, prefix=args.prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
