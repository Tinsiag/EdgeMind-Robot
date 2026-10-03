"""Render the latest native schematic PDF and inventory visible schematic text."""
from pathlib import Path
import json, re
import pypdfium2 as pdfium
from kicad_tools import parse, children, child, prop
from schematic_chinese import NETS

root=Path(__file__).resolve().parents[1]
out=root/'review'/'redesign-render'
out.mkdir(exist_ok=True)
pdf=pdfium.PdfDocument(str(root/'review'/'电源板原理图_R2.pdf'))
for i in range(len(pdf)):
    page=pdf[i]
    page.render(scale=1.6).to_pil().save(out/f'page-{i+1}.png')
    page.close()
pdf.close()
visible=[]
electrical=[]
for f in [root/'ProPrj_power_2026-10-02.kicad_sch',*sorted(root.glob('0[1-9]_*.kicad_sch'))]:
    if f.name=='05_at8236_motors.kicad_sch':continue
    text=f.read_text(encoding='utf-8');sch=parse(text)
    assert '(face ' not in text
    for n in children(sch,'text'):
        note=str(n[1])
        for name in [*NETS,'BAT_POS']:
            assert not re.search(r'(?<![A-Za-z0-9_+])'+re.escape(name)+r'(?![A-Za-z0-9_])',note),(f.name,'Network identifier in ordinary note',name)
        visible.append({'file':f.name,'kind':'text','text':note})
    for kind in ['label','global_label','hierarchical_label']:
        for n in children(sch,kind):
            assert str(n[1]).isascii() and '?' not in str(n[1])
            electrical.append({'file':f.name,'kind':kind,'name':str(n[1])})
    for sh in children(sch,'sheet'):
        for n in children(sh,'pin'):
            assert str(n[1]).isascii() and '?' not in str(n[1])
            electrical.append({'file':f.name,'kind':'sheet_pin','name':str(n[1])})
    for n in children(sch,'symbol'):
        if not prop(n,'Reference').startswith('#'):
            visible.append({'file':f.name,'kind':'value','text':prop(n,'Value')})
english=[v for v in visible if re.search(r'[A-Za-z]{4,}',v['text']) and not re.search(r'[\u4e00-\u9fff]',v['text'])]
(root/'review'/'visible-text-audit.json').write_text(json.dumps({'visible':visible,'latin_only_candidates':english,'electrical_identifiers_excluded_from_translation':electrical},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pages':10,'latin_only_component_values':len(english),'ASCII_electrical_labels':len(electrical),'ordinary_notes_exclude_net_identifiers':True},ensure_ascii=False))
