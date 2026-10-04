"""Interactive setup helpers for CSES Kit."""
from __future__ import annotations

import os
import sys
import termios
import tty

from cses_lib import repo_root, save_env_values


def arrow_menu(
    title: str,
    options: list[str],
    default: int = 0,
    interactive: bool | None = None,
) -> int:
    """Return an option index using arrow keys in a terminal."""
    if interactive is None:
        interactive = (
            sys.stdin.isatty()
            and sys.stdout.isatty()
            and not os.environ.get("CSES_TESTING")
        )
    if not interactive:
        raw = input(f"{title} [1-{len(options)}]: ").strip()
        try:
            selected = int(raw) - 1
        except ValueError:
            lowered = raw.lower()
            return next(
                (index for index, option in enumerate(options) if option.lower() == lowered),
                default,
            )
        return selected if 0 <= selected < len(options) else default

    selected = max(0, min(default, len(options) - 1))
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            print("\033[2J\033[H", end="")
            print(title)
            for index, option in enumerate(options):
                marker = ">" if index == selected else " "
                print(f" {marker} {option}")
            print("\nUse Up/Down and Enter. Home/End also work.", flush=True)
            key = sys.stdin.read(1)
            if key in ("\n", "\r"):
                return selected
            if key in ("k", "K"):
                selected = max(0, selected - 1)
            elif key in ("j", "J"):
                selected = min(len(options) - 1, selected + 1)
            elif key == "\x1b":
                sequence = sys.stdin.read(2)
                if sequence == "[A":
                    selected = max(0, selected - 1)
                elif sequence == "[B":
                    selected = min(len(options) - 1, selected + 1)
                elif sequence == "[H":
                    selected = 0
                elif sequence == "[F":
                    selected = len(options) - 1
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def choose_editor() -> str:
    choices = ["nvim", "vim", "code", "cursor", "custom"]
    option = choices[arrow_menu("Choose your editor", choices, default=2)]
    if option == "custom":
        custom = input("Custom editor command: ").strip()
        return custom or "code"
    return option


def choose_roadmap() -> str:
    return input("Path to roadmap JSON/TXT: ").strip()


def cmd_setup(args) -> int:
    editor = args.editor or os.environ.get("CSES_EDITOR") or choose_editor()
    repo_path = (
        args.repo_path
        or os.environ.get("CSES_PROBLEMS_DIR")
        or input("Existing problems directory [./problems]: ").strip()
        or os.path.join(repo_root(), "problems")
    )
    roadmap_path = args.roadmap or os.environ.get("CSES_ROADMAP") or choose_roadmap()
    values = {
        "CSES_EDITOR": editor,
        "CSES_PROBLEMS_DIR": repo_path,
        "CSES_ROADMAP": roadmap_path,
    }
    if args.session_mode:
        values["CSES_SESSION_MODE"] = args.session_mode
    save_env_values(values)
    print("saved local CSES setup in .env")
    print("session mode:", values.get("CSES_SESSION_MODE", "cookie"))
    print("editor:", editor)
    print("problems path:", repo_path)
    return 0