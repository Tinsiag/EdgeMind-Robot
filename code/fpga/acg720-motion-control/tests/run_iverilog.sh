#!/usr/bin/env bash
# Digital simulation only; never opens serial devices or a programmer.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IVERILOG="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
EXTRA=()
if [[ -n "${IVL_LIB:-}" ]]; then EXTRA=(-B "$IVL_LIB"); fi
mkdir -p "$ROOT/.local/sim"
for file in "$ROOT"/tests/*_tb.v; do
    tb="$(basename "$file" .v)"
    "$IVERILOG" "${EXTRA[@]}" -g2012 -Wall -s "$tb" -o "$ROOT/.local/sim/$tb.vvp" "$ROOT"/rtl/*.v "$file"
    "$VVP" "$ROOT/.local/sim/$tb.vvp"
done
