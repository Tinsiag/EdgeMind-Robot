"""Preserve per-instance imported footprint geometry as named local variants."""
from kicad_tools import *

st,sch=load('.kicad_sch')
bt,pcb=load('.kicad_pcb')
se,be=[],[]
syms={prop(s,'Reference'):s for s in children(sch,'symbol')}
fps={prop(f,'Reference'):f for f in children(pcb,'footprint')}
drc=json.loads((ROOT/'review'/'after-drc.json').read_text(encoding='utf-8'))
uuid_refs={val(f,'uuid'):prop(f,'Reference') for f in children(pcb,'footprint')}
variants={uuid_refs[v['items'][0]['uuid']] for v in drc['violations'] if v['type']=='lib_footprint_mismatch'}
for ref in variants:
    s,f=syms[ref],fps[ref]
    name=prop(s,'Footprint')+'_'+ref
    p=prop_node(s,'Footprint')[2]
    se.append((p.start,p.end,json.dumps(name,ensure_ascii=False)))
    be.append((f[1].start,f[1].end,json.dumps(name,ensure_ascii=False)))
    p=prop_node(f,'Footprint')
    if p:
        be.append((p[2].start,p[2].end,json.dumps(name,ensure_ascii=False)))
for text,node,edits in [(st,syms['LED1'],se),(bt,fps['LED1'],be)]:
    p=prop_node(node,'Value')[2]
    edits.append((p.start,p.end,'"LED"'))
# The imported title block is drawing-only and must not remain unannotated.
frame=syms['?']
p=prop_node(frame,'Reference')[2]
se.append((p.start,p.end,'"#FRAME01"'))
for n in [x for x in children(child(frame,'instances'),'project')]:
    for path in children(n,'path'):
        c=child(path,'reference')
        se.append((c[1].start,c[1].end,'"#FRAME01"'))
(ROOT/(STEM+'.kicad_sch')).write_text(apply_edits(st,se),encoding='utf-8',newline='\n')
(ROOT/(STEM+'.kicad_pcb')).write_text(apply_edits(bt,be),encoding='utf-8',newline='\n')
rows=json.loads((ROOT/'review'/'component-map.json').read_text(encoding='utf-8'))
for row in rows:
    if row['reference'] in variants:
        row['footprint']+='_'+row['reference']
    if row['reference']=='LED1':
        row['value']='LED'
(ROOT/'review'/'component-map.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Preserved',len(variants),'imported geometry variants; filled LED value and annotated drawing-only title block.')
