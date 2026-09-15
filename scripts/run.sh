#!/usr/bin/env bash
# Run a CSES solution against every test case in its tests/ dir.
#
# Usage:
#   scripts/run.sh <problem-dir>        # compile (C++) or interpret (Python/Node.js) + test
#   scripts/run.sh <problem-dir> -i     # then read from stdin (interactive)
#   scripts/run.sh <dir>/sol.py         # force Python even if sol.cpp exists
#   scripts/run.sh <dir>/sol.js         # force Node.js even if sol.cpp exists
#
# Keeps a real sol.cpp as the default. When sol.cpp is missing or still the empty
# template, prefers sol.py for backward compatibility and then sol.js.
set -euo pipefail

# Resolve repo root (this script lives in <root>/scripts).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/run.sh <problem-dir-or-source> [-i] [--timeout SEC]" >&2
  exit 1
fi

ARG="$1"
shift
MODE="test"
TIMEOUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -i)
      MODE="-i"
      shift
      ;;
    --timeout)
      if [[ $# -lt 2 ]]; then
        echo "error: --timeout requires a positive number of seconds" >&2
        exit 2
      fi
      TIMEOUT="$2"
      shift 2
      ;;
    *)
      echo "error: unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "$TIMEOUT" ]] && ! python3 - "$TIMEOUT" <<'PY'
import math
import sys

try:
    value = float(sys.argv[1])
except ValueError:
    raise SystemExit(1)
raise SystemExit(0 if math.isfinite(value) and value > 0 else 1)
PY
then
  echo "error: --timeout requires a positive number of seconds" >&2
  exit 2
fi

if [[ -f "$ARG" ]]; then
  SRC="$ARG"
  PROB="$(cd "$(dirname "$ARG")" && pwd)"
else
  PROB="$ARG"
  CPP_TEMPLATE=false
  if [[ -f "$PROB/sol.cpp" ]] && [[ -f "$ROOT/template.cpp" ]] \
      && cmp -s <(tr -d '[:space:]' < "$PROB/sol.cpp") <(tr -d '[:space:]' < "$ROOT/template.cpp"); then
    CPP_TEMPLATE=true
  fi
  if [[ -f "$PROB/sol.cpp" ]] && [[ "$CPP_TEMPLATE" == false ]]; then
    SRC="$PROB/sol.cpp"
  elif [[ -f "$PROB/sol.py" ]]; then
    SRC="$PROB/sol.py"
  elif [[ -f "$PROB/sol.js" ]]; then
    SRC="$PROB/sol.js"
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
elif [[ "$ext" == "js" ]]; then
  RUN=(node "$SRC")
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
elif [[ "$ext" == "js" ]]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "error: node is required to run $SRC" >&2
    exit 1
  fi
  echo "${DIM}node $SRC ...${RST}"
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
  status=0
  if [[ -n "$TIMEOUT" ]]; then
    if got="$(python3 "$ROOT/scripts/run_with_timeout.py" "$TIMEOUT" "$in" -- "${RUN[@]}" 2>/tmp/cses_stderr)"; then
      :
    else
      status=$?
    fi
  else
    if got="$("${RUN[@]}" < "$in" 2>/tmp/cses_stderr)"; then
      :
    else
      status=$?
    fi
  fi
  end=$(python3 -c 'import time; print(time.perf_counter())')
  ms=$(python3 -c "print(round(($end - $start) * 1000))")

  if [[ $status -eq 124 ]]; then
    echo "${RED}================================================${RST}"
    echo "${RED}Test ${name}  TLE  (${ms}ms)${RST}"
    echo "${RED}================================================${RST}"
    echo "  note"
    echo "    timed out after ${TIMEOUT}s"
    echo "  expected"
    sed 's/^/    /' "$exp"
    if [[ -n "$got" ]]; then
      echo "  got"
      echo "$got" | sed 's/^/    /'
    fi
    if [[ -s /tmp/cses_stderr ]]; then
      echo "  stderr"
      sed 's/^/    /' /tmp/cses_stderr
    fi
    ((fail++)) || true
    continue
  fi

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
