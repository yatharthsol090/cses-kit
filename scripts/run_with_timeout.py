#!/usr/bin/env python3
"""Run one solution process with an optional per-test timeout."""

import subprocess
import sys


TIMEOUT_EXIT = 124


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: run_with_timeout.py <timeout> <input_path> [--] <command> [args...]", file=sys.stderr)
        return 2

    timeout = float(sys.argv[1])
    input_path = sys.argv[2]
    command = sys.argv[3:]
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("error: missing command to run", file=sys.stderr)
        return 2

    with open(input_path, "rb") as input_file:
        try:
            completed = subprocess.run(
                command,
                stdin=input_file,
                stdout=sys.stdout.buffer,
                stderr=sys.stderr.buffer,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return TIMEOUT_EXIT
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
