"""Local, hashed SV compatibility adaptation; the pinned MIT source is intact."""
import hashlib
import json
from pathlib import Path


def checksum_source(root):
    source = root.parent / "third_party/verilog-ethernet/rtl/udp_checksum_gen.v"
    output = root / ".local/vendor/udp_checksum_gen.v"
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "")
    # These next-state values are irrelevant while their FFs are in reset.
    # Explicit guards also make rst a sensitivity input on older Icarus builds,
    # which otherwise leave the read-pointer next value X at initial time.
    for name, initial in (("header_fifo_wr_ptr_next", "header_fifo_wr_ptr_reg"),
                          ("header_fifo_rd_ptr_next", "header_fifo_rd_ptr_reg")):
        old = f"{name} = {initial};"
        assert text.count(old) == 1
        text = text.replace(old, old+f"\n    if (rst) {name} = 0;")
    output.write_text(text, encoding="utf-8")
    record = {"source": str(source), "original_sha256": hashlib.sha256(raw).hexdigest(),
              "adapted_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "adaptation": "Explicit reset guards for header FIFO pointer next-state defaults make combinational blocks reset-sensitive on the installed Icarus frontend. Pointer FFs already reset to zero. No active-state protocol or license change."}
    output.with_suffix(".json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return output
