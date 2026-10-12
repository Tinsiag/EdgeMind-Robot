"""Read imported geometry without changing the imported PCB."""
import json
from pathlib import Path
import pcbnew

out = Path(__file__).resolve().parent
board = pcbnew.LoadBoard(str(out / "acx720_v2.kicad_pcb"))
footprints = []
holes = []
for fp in board.GetFootprints():
    p = fp.GetPosition()
    footprints.append({"reference": fp.GetReference(), "pattern": str(fp.GetFPID().GetLibItemName()),
                       "position_mm": [pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)],
                       "angle_deg": fp.GetOrientationDegrees()})
    for pad in fp.Pads():
        drill = pad.GetDrillSize()
        if drill.x > 0 and drill.y > 0:
            p = pad.GetPosition()
            holes.append({"reference": fp.GetReference(), "position_mm": [pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)],
                          "size_mm": [pcbnew.ToMM(drill.x), pcbnew.ToMM(drill.y)],
                          "angle_deg": pad.GetOrientationDegrees()})
for via in board.GetTracks():
    if isinstance(via, pcbnew.PCB_VIA):
        p = via.GetPosition()
        holes.append({"reference": "via", "position_mm": [pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)],
                      "size_mm": [pcbnew.ToMM(via.GetDrillValue())] * 2, "angle_deg": 0})
data = {"imported_stack_thickness_mm": pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness()),
        "footprints": footprints, "holes": holes}
(out / "kicad_geometry.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
print("Extracted", len(footprints), "footprints and", len(holes), "drilled features")
