"""Add explicit T junctions and restore the two dump-divider ground wires.

Preserve native file formatting, component placement and all unrelated edits.
Run with --apply only after backing up the six affected native sheets.
"""
from pathlib import Path
import argparse
import json
import uuid
from kicad_tools import parse, child, children, prop, apply_edits

ROOT = Path(__file__).resolve().parents[1]
FILES = ['01_power_input.kicad_sch', '03_aux_3v3.kicad_sch',
         '05_motor_left.kicad_sch', '06_motor_right.kicad_sch',
         '07_motor_dump.kicad_sch', '08_rail_protection.kicad_sch']


def inside(p, a, b):
    return (a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1])
            or a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    report = []
    for filename in FILES:
        path = ROOT / filename
        original = path.read_bytes()
        text = original.decode('utf-8')
        sch = parse(text)
        reroutes = []
        if filename == '07_motor_dump.kicad_sch':
            # Keep hysteresis feedback away from the divider body and ground.
            # A vertical wire through the resistor can be merged on native save.
            edits = []
            for top, bottom in [(71.12, 96.52), (175.26, 200.66)]:
                vertical = []
                for wire in children(sch, 'wire'):
                    ps = children(child(wire, 'pts'), 'xy')
                    if all(float(p[1]) == 224.79 for p in ps) and {float(p[2]) for p in ps} == {top, bottom}:
                        vertical.append(wire)
                if not vertical:
                    continue
                assert len(vertical) == 1
                for wire in children(sch, 'wire'):
                    ps = children(child(wire, 'pts'), 'xy')
                    for point in ps:
                        if (float(point[1]), float(point[2])) == (224.79, bottom) or wire is vertical[0] and float(point[1]) == 224.79:
                            edits.append((point[1].start, point[1].end, '212.09'))
                reroutes.append((top, bottom))
                for junction in children(sch, 'junction'):
                    location = tuple(map(float, child(junction, 'at')[1:3]))
                    own_id = str(uuid.uuid5(uuid.NAMESPACE_URL, filename + ':explicit-junction:' + str(location)))
                    if location in [(224.79, round(top+7.62, 2)), (224.79, round(top+11.43, 2))] and str(child(junction, 'uuid')[1]) == own_id:
                        edits.append((junction.start, junction.end, ''))
                edits.append((sch.end - 1, sch.end - 1,
                              f'(wire (pts (xy 212.09 {top:g}) (xy 224.79 {top:g})) '
                              f'(stroke (width 0) (type default)) '
                              f'(uuid "{uuid.uuid5(uuid.NAMESPACE_URL, filename + ":feedback-route:" + str(top))}"))\n'))
            text = apply_edits(text, edits)
            sch = parse(text)
        lines = [tuple(tuple(map(float, p[1:3])) for p in children(child(w, 'pts'), 'xy'))
                 for w in children(sch, 'wire')]
        dots = {tuple(map(float, child(j, 'at')[1:3])) for j in children(sch, 'junction')}
        missing = {p for a, b in lines for p in (a, b)
                   if any(inside(p, c, d) for c, d in lines)} - dots
        additions = [f'(junction (at {x:g} {y:g}) (diameter 0) (color 0 0 0 0) '
                     f'(uuid "{uuid.uuid5(uuid.NAMESPACE_URL, filename + ":explicit-junction:" + str((x, y)))}"))'
                     for x, y in sorted(missing)]
        grounds = []
        if filename == '07_motor_dump.kicad_sch':
            symbols = {prop(c, 'Reference'): c for c in children(sch, 'symbol')}
            for resistor, ground in [('R77', '#PWR165'), ('R81', '#PWR168')]:
                c, g = symbols[resistor], symbols[ground]
                assert child(c, 'lib_id')[1] == 'Device:R'
                x, y, angle = map(float, child(c, 'at')[1:4])
                assert angle == 0
                pin = (x, round(y + 3.81, 2))
                endpoint = tuple(map(float, child(g, 'at')[1:3]))
                assert prop(g, 'Value') == '地' and endpoint == (x, round(pin[1] + 3.81, 2))
                if (pin, endpoint) not in lines and (endpoint, pin) not in lines:
                    additions.append(f'(wire (pts (xy {pin[0]:g} {pin[1]:g}) '
                                     f'(xy {endpoint[0]:g} {endpoint[1]:g})) '
                                     f'(stroke (width 0) (type default)) '
                                     f'(uuid "{uuid.uuid5(uuid.NAMESPACE_URL, filename + ":restore-ground:" + resistor)}"))')
                    grounds.append(resistor)
        report.append({'文件': filename, '补齐T形连接点': sorted(missing), '恢复接地线': grounds, '反馈线绕开分压电阻': reroutes})
        if args.apply and (additions or reroutes):
            newline = '\r\n' if '\r\n' in text else '\n'
            updated = apply_edits(text, [(sch.end - 1, sch.end - 1, newline.join(additions) + newline)])
            assert path.read_bytes() == original, 'File changed during repair preparation'
            path.write_bytes(updated.encode('utf-8'))
    if args.apply:
        (ROOT / 'review' / 'junction-repair.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
