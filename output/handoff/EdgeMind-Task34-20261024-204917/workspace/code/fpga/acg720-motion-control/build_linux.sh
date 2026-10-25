#!/usr/bin/env bash
# Build only. Never invokes a programmer or changes hardware power settings.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GOWIN_GW_SH="${GOWIN_GW_SH:-$HOME/.local/opt/Gowin/V1.9.12.04/IDE/bin/gw_sh}"
if [[ ! -x "$GOWIN_GW_SH" ]]; then
    echo "Gowin not found. Set GOWIN_GW_SH to your installed IDE/bin/gw_sh." >&2
    exit 1
fi
# This installation's bundled FreeType is incompatible with system fontconfig.
# Override for this process and children only; do not replace any installed libs.
if [[ -f /usr/lib/libfreetype.so.6 ]]; then
    export LD_PRELOAD="/usr/lib/libfreetype.so.6${LD_PRELOAD:+:$LD_PRELOAD}"
fi
# minimal avoids display/GLX initialization for the Tcl batch build.
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-minimal}"
cd "$ROOT"
mkdir -p .local
LOG=".local/build-wiring-$(date +%Y%m%d-%H%M%S).log"
"$GOWIN_GW_SH" "$ROOT/build.tcl" 2>&1 | tee "$LOG"
python -B "$ROOT/tests/audit_build.py"
echo "Build and report audit complete. No FPGA programming was performed. Log: $ROOT/$LOG"
