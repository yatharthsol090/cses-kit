#!/usr/bin/env bash
# Run a CSES solution against every test case in its tests/ dir.
#
# Usage:
#   scripts/run.sh <problem-dir>        # compile (C++) or interpret (Python) + test
#   scripts/run.sh <problem-dir> -i     # then read from stdin (interactive)
#   scripts/run.sh <dir>/sol.py         # force Python even if sol.cpp exists
#
# Picks sol.py when sol.cpp is missing or still the empty template; otherwise C++.
set -euo pipefail

# Resolve repo root (this script lives in <root>/scripts).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/run.sh <problem-dir-or-source> [-i]" >&2
  exit 1
fi

ARG="$1"
MODE="${2:-test}"

if [[ -f "$ARG" ]]; then
  SRC="$ARG"
  PROB="$(cd "$(dirname "$ARG")" && pwd)"
else
  PROB="$ARG"
  if [[ -f "$PROB/sol.py" ]] && { [[ ! -f "$PROB/sol.cpp" ]] || grep -q 'your solution goes here' "$PROB/sol.cpp"; }; then
    SRC="$PROB/sol.py"
  else
    SRC="$PROB/sol.cpp"
  fi
fi

if [[ ! -f "$SRC" ]]; then
  echo "error: $SRC not found" >&2
  exit 1
fi

BIN="$PROB/sol"
RUN=()
ext="${SRC##*.}"
if [[ "$ext" == "py" ]]; then
  RUN=(python3 "$SRC")
elif [[ "$ext" == "cpp" || "$ext" == "cc" || "$ext" == "cxx" ]]; then
  RUN=("$BIN")
else
  echo "error: unsupported solution: $SRC" >&2
  exit 1
fi

# Colors (fall back to empty strings if not a TTY).
if [[ -t 1 ]]; then
  RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; DIM=$'\033[2m'; RST=$'\033[0m'
else
  RED=""; GRN=""; YEL=""; DIM=""; RST=""
fi

if [[ "$ext" == "py" ]]; then
  echo "${DIM}python3 $SRC ...${RST}"
else
  echo "${DIM}compiling $SRC ...${RST}"
  g++ -std=gnu++17 -O2 -Wall -Wextra -Wshadow \
      -D_GLIBCXX_ASSERTIONS -fsanitize=address,undefined \
      -I "$ROOT/include" "$SRC" -o "$BIN"
fi

# Interactive mode: just run with your keyboard as input.
if [[ "$MODE" == "-i" ]]; then
  echo "${DIM}running (type input, Ctrl-D to end):${RST}"
  "${RUN[@]}"
  exit $?
fi

shopt -s nullglob
INPUTS=("$PROB"/tests/*.in)
if [[ ${#INPUTS[@]} -eq 0 ]]; then
  echo "${YEL}no test cases in $PROB/tests/ — running once with no input:${RST}"
  "${RUN[@]}" || true
  exit 0
fi

pass=0; fail=0
for in in "${INPUTS[@]}"; do
  name="$(basename "$in" .in)"
  exp="$PROB/tests/$name.out"

  # Time the run (seconds, portable).
  start=$(python3 -c 'import time; print(time.perf_counter())')
  got="$("${RUN[@]}" < "$in" 2>/tmp/cses_stderr || true)"
  end=$(python3 -c 'import time; print(time.perf_counter())')
  ms=$(python3 -c "print(round(($end - $start) * 1000))")

  if [[ ! -f "$exp" ]]; then
    echo "${YEL}? $name${RST}  (no expected output; got, ${ms}ms):"
    echo "$got" | sed 's/^/    /'
    continue
  fi

  # Compare ignoring trailing whitespace / trailing blank lines.
  if diff -q <(printf '%s' "$got" | sed -e 's/[[:space:]]*$//') \
             <(printf '%s' "$(cat "$exp")" | sed -e 's/[[:space:]]*$//') >/dev/null; then
    echo "${GRN}✓ $name${RST}  ${DIM}(${ms}ms)${RST}"
    ((pass++)) || true
  else
    echo "${RED}================================================${RST}"
    echo "${RED}Test ${name}  FAIL  (${ms}ms)${RST}"
    echo "${RED}================================================${RST}"
    echo "  expected"
    sed 's/^/    /' "$exp"
    echo "  got"
    echo "$got" | sed 's/^/    /'
    if [[ -s /tmp/cses_stderr ]]; then
      echo "  stderr"
      sed 's/^/    /' /tmp/cses_stderr
    fi
    ((fail++)) || true
  fi
done

echo
echo "${GRN}$pass passed${RST}, ${RED}$fail failed${RST}"
[[ $fail -eq 0 ]]
