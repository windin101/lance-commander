#!/usr/bin/env bash
# Run the gdUnit4 suite headless. Uses $GODOT_BIN or ~/.local/bin/godot.
# Exits 1 if any suite reports failures or errors.
# grep -q is avoided on purpose: with pipefail it exits on the first match and the echo
# feeding it dies of SIGPIPE, which reads as a failed pipeline on large outputs.
set -uo pipefail
GODOT="${GODOT_BIN:-$HOME/.local/bin/godot}"
cd "$(dirname "$0")/../game"
"$GODOT" --headless --path . --import >/dev/null 2>&1 || true
out=$("$GODOT" --headless --path . -s res://addons/gdUnit4/bin/GdUnitCmdTool.gd --add res://test --ignoreHeadlessMode "$@" 2>&1 </dev/null | sed 's/\x1b\[[0-9;]*m//g')
echo "$out" | grep -E 'PASSED|FAILED|ERROR|Statistics|Expecting|but was|WARNING|SCRIPT ERROR|Parse Error' | sed 's#res://test/##'
if echo "$out" | grep -iE 'script errors were detected|SCRIPT ERROR|Parse Error' >/dev/null; then
  echo "TESTS FAILED (script errors)"; exit 1
fi
if ! echo "$out" | grep -E '^Statistics' >/dev/null; then
  echo "TESTS FAILED (no suites ran)"; exit 1
fi
if echo "$out" | grep -E '^Statistics' | grep -v '0 errors | 0 failures' >/dev/null; then
  echo "TESTS FAILED"; exit 1
fi
echo "ALL TESTS PASSED"
