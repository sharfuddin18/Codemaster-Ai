"""Command-line client for Codemaster code generation.

The CLI deliberately treats the prompt as opaque text.  It accepts a prompt as
one or more command-line arguments, from stdin, or from a file so multiline
Markdown and source code can be passed without the CLI changing their content.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Sequence, TextIO

import requests


DEFAULT_API_URL = "http://localhost:8000/generate-code"
DEFAULT_TIMEOUT_SECONDS = 120


USAGE = """Usage:
  ai "your request here"
  ai --prompt "your request here"
  ai --file prompt.txt
  ai --stdin

Examples:
  ai "Write Python code
- read a CSV
- validate the columns
- calculate the average"

  ai --file prompt.txt
  Get-Content prompt.txt | ai --stdin
"""


def _read_stdin(stream: TextIO) -> str:
    """Read stdin exactly as supplied, including newlines."""
    return stream.read()


def resolve_prompt(
    argv: Sequence[str],
    *,
    stdin: TextIO | None = None,
) -> str:
    """Resolve the prompt without modifying its contents.

    Supported input modes are:
    - a normal positional prompt (including a quoted multiline prompt),
    - ``--prompt`` followed by one prompt argument,
    - ``--file PATH``, and
    - ``--stdin`` (or stdin automatically when no arguments are supplied and
      stdin is piped).

    When a prompt is supplied as multiple unquoted arguments, they are joined
    with single spaces.  A quoted multiline argument is kept byte-for-byte
    (apart from the shell's own quote parsing).
    """
    args = list(argv)

    if not args:
        if stdin is not None and not stdin.isatty():
            return _read_stdin(stdin)
        raise ValueError("No prompt supplied")

    if args[0] in {"-h", "--help"}:
        raise SystemExit(0)

    if args[0] == "--stdin":
        if len(args) != 1:
            raise ValueError("--stdin cannot be combined with other arguments")
        if stdin is None:
            stdin = sys.stdin
        return _read_stdin(stdin)

    if args[0] == "--file":
        if len(args) != 2:
            raise ValueError("--file requires exactly one path")
        return Path(args[1]).read_text(encoding="utf-8")

    if args[0] == "--prompt":
        if len(args) < 2:
            raise ValueError("--prompt requires a prompt")
        return args[1] if len(args) == 2 else " ".join(args[1:])

    if args[0].startswith("-"):
        raise ValueError(f"Unknown option: {args[0]}")

    # Do not strip, collapse, or otherwise normalize the first argument.
    # A shell-quoted multiline prompt arrives here as one argument and retains
    # its newlines, Markdown, source code, quotes, and indentation.
    return args[0] if len(args) == 1 else " ".join(args)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    if argv is None:
        argv = sys.argv[1:]

    try:
        prompt = resolve_prompt(argv, stdin=sys.stdin)
    except SystemExit as exc:
        print(USAGE)
        return int(exc.code or 0)
    except (OSError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    if not prompt.strip():
        print("Input error: prompt is empty", file=sys.stderr)
        return 2

    api_url = os.getenv("CODEMASTER_API_URL", DEFAULT_API_URL)
    try:
        response = requests.post(
            api_url,
            headers={"Content-Type": "application/json"},
            json={"prompt": prompt},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_json = response.json()
    except requests.exceptions.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to decode JSON response: {exc}", file=sys.stderr)
        return 1

    if "code" in response_json:
        print(response_json["code"])
        return 0

    print("No 'code' in response:", response_json, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
