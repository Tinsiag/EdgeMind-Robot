#!/usr/bin/env bash
# A719: build and audit only, no programmer or serial port access.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GOWIN_GW_SH="${GOWIN_GW_SH:-$HOME/.local/opt/Gowin/V1.9.12.04/IDE/bin/gw_sh}"
[[ -x "$GOWIN_GW_SH" ]] || { echo "Set GOWIN_GW_SH to an installed gw_sh" >&2; exit 1; }
if [[ -f /usr/lib/libfreetype.so.6 ]]; then
    export LD_PRELOAD="/usr/lib/libfreetype.so.6${LD_PRELOAD:+:$LD_PRELOAD}"
fi
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-minimal}"
cd "$ROOT"
mkdir -p .local
LOG=".local/build-gpio-static-$(date +%Y%m%d-%H%M%S).log"
"$GOWIN_GW_SH" "$ROOT/build_gpio_static.tcl" 2>&1 | tee "$LOG"
python -B "$ROOT/tests/audit_build.py" --variant gpio_static
echo "A719 build/report audit complete; no FPGA programming performed. Log: $ROOT/$LOG"
