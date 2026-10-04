"""Read-only validation of the layout atlas against the current design."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import pcbnew

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
atlas = json.loads((ROOT / 'review/all-layout-current.json').read_text(encoding='utf-8'))
xml = ET.parse(OUT / 'current.net.xml').getroot()
components = {c.get('ref'): c for c in xml.findall('components/comp')}
pins = {(n.get('ref'), n.get('pin')): net.get('name')
        for net in xml.findall('nets/net') for n in net.findall('node')}
board = pcbnew.LoadBoard(str(ROOT / 'ProPrj_power_2026-10-02.kicad_pcb'))
footprints = {f.GetReference(): f for f in board.GetFootprints()}
assert set(components) == set(atlas['parts']) == set(footprints)
pad_count = 0
for ref, old in atlas['parts'].items():
    comp = components[ref]
    assert comp.findtext('value') == old['value'], ref
    assert comp.findtext('footprint') == old['footprint'], ref
    for pin, net in old['pins'].items():
        assert pins[ref, pin] == net, (ref, pin)
    for pad in footprints[ref].Pads():
        if pad.GetNumber():
            assert pad.GetNetname() == pins[ref, pad.GetNumber()], (ref, pad.GetNumber())
            pad_count += 1
hashes = {str(Path(p)): hashlib.sha256(Path(p).read_bytes()).hexdigest()
          for p in atlas['hashes']}
assert hashes == atlas['hashes'], 'Design changed since the atlas was generated'
erc = json.loads((OUT / 'erc.json').read_text(encoding='utf-8'))
violations = [v for s in erc.get('sheets', []) for v in s.get('violations', [])]
reference = 2.495
results = {
    'components': len(components),
    'nets': len(xml.findall('nets/net')),
    'numbered_pads_checked': pad_count,
    'atlas_values_footprints_and_pin_nets_match': True,
    'design_hashes_match_atlas': True,
    'erc_violations_under_project_settings': len(violations),
    'copper_layers': board.GetCopperLayerCount(),
    'track_and_via_objects': len(list(board.GetTracks())),
    'zones': len(list(board.Zones())),
    'edge_cut_objects': sum(d.GetLayer() == pcbnew.Edge_Cuts for d in board.GetDrawings()),
    'nominal_thresholds_V': {
        'logic_uv': reference * (1 + 26.1 / 10),
        'motor_uv': reference * (1 + 28.7 / 10),
        'logic_and_motor_ov': reference * (1 + 46.4 / 10),
        'battery_warning': reference * (1 + 30.9 / 10),
        'dump_on_assuming_comparator_low_0p2V': reference * (1 + 51.1 / 10 + 51.1 / 1000) - 0.2 * 51.1 / 1000,
        'dump_off_assuming_gate_high_12V': reference * (1 + 51.1 / 10 + 51.1 / 1000) - 12 * 51.1 / 1000,
    },
    'hashes': hashes,
}
(OUT / 'evidence.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in results.items() if k != 'hashes'}, ensure_ascii=False, indent=2))
