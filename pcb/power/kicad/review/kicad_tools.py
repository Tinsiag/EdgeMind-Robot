"""Small lossless S-expression reader for this KiCad import's audit/repair."""
import re
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
STEM = 'ProPrj_power_2026-10-02'

class Atom(str):
    def __new__(cls, value, start, end):
        obj = str.__new__(cls, value)
        obj.start, obj.end = start, end
        return obj

class Node(list):
    pass

def parse(text):
    stack, root = [], None
    for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text):
        t = m.group()
        if t == '(':
            n = Node()
            n.start = m.start()
            if stack:
                stack[-1].append(n)
            else:
                root = n
            stack.append(n)
        elif t == ')':
            stack.pop().end = m.end()
        else:
            value = json.loads(t) if t.startswith('"') else t
            stack[-1].append(Atom(value, m.start(), m.end()))
    assert not stack
    return root

def children(n, key):
    return [x for x in n if isinstance(x, Node) and x and x[0] == key]

def child(n, key):
    return next((x for x in children(n, key)), None)

def val(n, key, default=''):
    c = child(n, key)
    return str(c[1]) if c and len(c)>1 else default

def prop_node(n, key):
    return next((x for x in children(n, 'property') if x[1] == key), None)

def prop(n, key):
    p = prop_node(n, key)
    return str(p[2]) if p else ''

def load(ext):
    text = (ROOT / (STEM + ext)).read_text(encoding='utf-8')
    return text, parse(text)

def apply_edits(text, edits):
    ordered = sorted(edits, reverse=True)
    for i, (start, end, replacement) in enumerate(ordered):
        if i:
            assert end <= ordered[i-1][0], 'Overlapping edits'
        text = text[:start] + replacement + text[end:]
    return text

if __name__ == '__main__':
    st, sch = load('.kicad_sch')
    bt, pcb = load('.kicad_pcb')
    lib = child(sch,'lib_symbols')
    symbols = {str(s[1]): s for s in children(lib,'symbol')}
    print('SCHEMATIC COMPONENTS')
    for s in children(sch, 'symbol'):
        ref = prop(s, 'Reference')
        if ref.startswith('#'):
            continue
        pins = [p for u in children(symbols[val(s,'lib_id')], 'symbol') for p in children(u,'pin')]
        print(ref, prop(s,'Value'), prop(s,'Footprint'), 'at', child(s,'at')[1:], 'pins', [(val(p,'number'),val(p,'name'),str(p[1])) for p in pins])
    print('PCB', Counter(str(n[0]) for n in pcb if isinstance(n,Node)))
    for fp in children(pcb, 'footprint'):
        print('FP',prop(fp,'Reference'),prop(fp,'Value'),fp[1], 'at',child(fp,'at')[1:], 'path',val(fp,'path'),'pads',[(str(p[1]),val(p,'net')) for p in children(fp,'pad')])
    for f in ['before-erc.json','before-drc.json']:
        p = ROOT / 'review' / f
        if p.exists():
            d = json.loads(p.read_text(encoding='utf-8'))
            print(f,'keys',d.keys())
            sections = d.get('sheets', []) if 'erc' in f else [d]
            for section in sections:
                for key in ['violations','unconnected_items','schematic_parity']:
                    if key in section:
                        print(key, Counter((v.get('type'), v.get('severity')) for v in section[key]))
                        print(json.dumps(section[key][:5],ensure_ascii=False,indent=2))
