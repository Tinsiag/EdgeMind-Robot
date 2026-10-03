"""Export audited board footprints with the installed KiCad Python API."""
from kicad_tools import ROOT, STEM
import pcbnew

board = pcbnew.LoadBoard(str(ROOT/(STEM+'.kicad_pcb')))
libdir=ROOT/'ProPrj_pow-easyedapro.pretty'
libdir.mkdir(exist_ok=True)
seen=set()
plugin=pcbnew.PCB_IO_KICAD_SEXPR()
for fp in board.GetFootprints():
    name=str(fp.GetFPID().GetLibItemName())
    if name in seen:
        continue
    seen.add(name)
    copy=pcbnew.FOOTPRINT(fp)
    copy.SetOrientationDegrees(0)
    copy.SetPosition(pcbnew.VECTOR2I(0,0))
    copy.SetPath(pcbnew.KIID_PATH())
    copy.SetSheetname('')
    copy.SetSheetfile('')
    for pad in copy.Pads():
        pad.SetNetCode(0)
    copy.SetReference('REF**')
    copy.SetValue(name)
    plugin.FootprintSave(str(libdir),copy)
print('Exported',len(seen),'project-local footprints:',sorted(seen))
