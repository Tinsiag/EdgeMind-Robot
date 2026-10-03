"""One-time conservative repair of the EasyEDA -> KiCad import, then net sync.

Does not redesign the circuit or move/reroute existing electrical components.
Original editable files are preserved in review/repair-backups before running.
"""
from kicad_tools import *
import xml.etree.ElementTree as ET
import sys
import uuid

RENAME = {'L':'J1','R':'J2','左电机':'J3','右电机':'J4',
          'U2':'J5','U3':'J6','U4':'J7','U6':'J8'}
SMALL_CAPS = {'C6','C7','C11','C14','C15','C16'}
PREFIX = 'ProPrj_pow-easyedapro'

def quote(s):
    return json.dumps(str(s),ensure_ascii=False)

def replace_atom(edits, atom, value):
    if str(atom) != value:
        edits.append((atom.start,atom.end,quote(value)))

def walk(n):
    if isinstance(n,Node):
        yield n
        for c in n:
            yield from walk(c)

def prepare_schematic():
    text = (ROOT/'review'/'repair-backups'/(STEM+'.kicad_sch')).read_text(encoding='utf-8')
    sch = parse(text)
    edits=[]
    pwr=0
    for s in children(sch,'symbol'):
        ref=prop(s,'Reference')
        if ref.startswith('#'):
            pwr+=1
            new_ref=f'#PWR{pwr:03d}'
        else:
            new_ref=RENAME.get(ref,ref)
        if new_ref!=ref:
            replace_atom(edits,prop_node(s,'Reference')[2],new_ref)
            for n in walk(child(s,'instances')):
                if n[0]=='reference':
                    replace_atom(edits,n[1],new_ref)
        if ref in SMALL_CAPS:
            replace_atom(edits,prop_node(s,'Footprint')[2],PREFIX+':C0603')
        if ref.startswith('#') or ref=='?':
            replace_atom(edits,prop_node(s,'Footprint')[2],'')
        if ref=='?':
            for key in ['in_bom','on_board','in_pos_files']:
                c=child(s,key)
                if c:
                    edits.append((c[1].start,c[1].end,'no'))
        id_node=child(s,'lib_id')
        alias=child(s,'lib_name')
        if alias:
            replace_atom(edits,id_node[1],PREFIX+':'+str(alias[1]))
            edits.append((alias.start,alias.end,''))
        elif ':' not in id_node[1]:
            replace_atom(edits,id_node[1],PREFIX+':'+str(id_node[1]))
    for sym in children(child(sch,'lib_symbols'),'symbol'):
        sym_name=str(sym[1]).split(':')[-1]
        if ':' not in sym[1]:
            replace_atom(edits,sym[1],PREFIX+':'+sym_name)
        p=prop_node(sym,'Footprint')
        if p and str(p[2])==PREFIX+':':
            replace_atom(edits,p[2],'')
        for unit in children(sym,'symbol'):
            for pin in children(unit,'pin'):
                pin_type='passive'
                if sym_name=='MP2236GJ-Z':
                    pin_type={'1':'power_in','2':'power_in','3':'power_out',
                              '4':'power_in','5':'passive','6':'input',
                              '7':'power_out','8':'input'}[val(pin,'number')]
                elif child(sym,'power') is not None:
                    continue
                if str(pin[1])!=pin_type:
                    edits.append((pin[1].start,pin[1].end,pin_type))
    updated=apply_edits(text,edits)
    (ROOT/(STEM+'.kicad_sch')).write_text(updated,encoding='utf-8',newline='\n')
    # Build the local symbol library from the exact audited cached definitions.
    cache=child(parse(updated),'lib_symbols')
    lib=['(kicad_symbol_lib (version 20251024) (generator "kicad_symbol_editor")']
    for sym in children(cache,'symbol'):
        local=updated[sym.start:sym.end]
        local=apply_edits(local,[(sym[1].start-sym.start,sym[1].end-sym.start,quote(str(sym[1]).split(':')[-1]))])
        lib.append(local)
    lib.append(')')
    (ROOT/(PREFIX+'.kicad_sym')).write_text('\n'.join(lib)+'\n',encoding='utf-8')
    print('Prepared schematic and exact local symbol library;',pwr,'power symbols annotated.')

def sync_board():
    st,sch=load('.kicad_sch')
    bt,pcb=load('.kicad_pcb')
    symbols={prop(s,'Reference'):s for s in children(sch,'symbol')
             if not prop(s,'Reference').startswith('#') and val(s,'on_board')!='no'}
    xml=ET.parse(ROOT/'review'/'after.net.xml').getroot()
    pin_nets={(n.attrib['ref'],n.attrib['pin']):net.attrib['name']
              for net in xml.findall('./nets/net') for n in net.findall('node')}
    net_map={}
    edits=[]
    holes=[]
    component_rows=[]
    smd_count=0
    for fp in children(pcb,'footprint'):
        old_ref=prop(fp,'Reference')
        ref=RENAME.get(old_ref,old_ref)
        s=symbols.get(ref)
        if s is None:
            assert old_ref=='',f'Unexpected unmatched footprint {old_ref}'
            holes.append(fp)
            continue
        assert set(str(p[1]) for p in children(fp,'pad'))==set(
            n.attrib['pin'] for net in xml.findall('./nets/net') for n in net.findall('node') if n.attrib['ref']==ref
        ),f'Pin/pad set mismatch at {ref}'
        for key in ['Reference','Value','Datasheet','Description']:
            p=prop_node(fp,key)
            if p:
                replace_atom(edits,p[2],prop(s,key))
        assert str(fp[1])==prop(s,'Footprint'),f'Footprint mismatch at {ref}'
        uid=val(s,'uuid')
        root_uid=val(sch,'uuid')
        additions=[f'(path "/{root_uid}/{uid}")','(sheetname "")',f'(sheetfile "{STEM}.kicad_sch")']
        all_smd=True
        for pad in children(fp,'pad'):
            old=val(pad,'net')
            new=pin_nets[(ref,str(pad[1]))]
            if old:
                assert old not in net_map or net_map[old]==new,f'Ambiguous net mapping: {old}'
                net_map[old]=new
            else:
                additions_net=f'(net {quote(new)})'
                edits.append((pad.end-1,pad.end-1,'\n\t\t\t'+additions_net+'\n\t\t'))
            drill=child(pad,'drill')
            if drill and len(drill)==2 and float(drill[1])<=0.001:
                edits.append((pad[2].start,pad[2].end,'smd'))
                edits.append((drill.start,drill.end,''))
                layers=child(pad,'layers')
                edits.append((layers.start,layers.end,'(layers "F.Cu" "F.Paste" "F.Mask")'))
                smd_count+=1
            else:
                all_smd=False
        additions.append('(attr smd)' if all_smd else '(attr through_hole)')
        for p in children(s,'property'):
            name=str(p[1])
            if name in ['Reference','Value','Footprint','Datasheet','Description']:
                continue
            existing=prop_node(fp,name)
            if existing:
                replace_atom(edits,existing[2],str(p[2]))
            else:
                additions.append(f'(property {quote(name)} {quote(p[2])} (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1))))')
        assert not child(fp,'path'),'This repair is intended for the original import only.'
        edits.append((fp.end-1,fp.end-1,'\n\t\t'+'\n\t\t'.join(additions)+'\n\t'))
        component_rows.append({'reference':ref,'original_reference':old_ref,'value':prop(s,'Value'),
                               'footprint':prop(s,'Footprint'),'schematic_uuid':uid,
                               'pcb_uuid':val(fp,'uuid'),'pin_count':len(children(fp,'pad'))})
    assert len(component_rows)==len(symbols)
    # The import's four unnumbered 3mm drilled pads are mechanical holes.
    for i,fp in enumerate(sorted(holes,key=lambda f:(float(child(f,'at')[1]),float(child(f,'at')[2]))),1):
        replace_atom(edits,prop_node(fp,'Reference')[2],f'H{i}')
        replace_atom(edits,prop_node(fp,'Value')[2],'MountingHole_3mm')
        replace_atom(edits,fp[1],PREFIX+':MountingHole_3mm')
        pad=child(fp,'pad')
        assert child(pad,'drill')[1]=='3'
        edits.append((pad[2].start,pad[2].end,'np_thru_hole'))
        edits.append((pad[1].start,pad[1].end,'""'))
        edits.append((fp.end-1,fp.end-1,'\n\t\t(attr board_only exclude_from_pos_files exclude_from_bom)\n\t'))
    # Names are reconciled by identical component/pin connectivity, never geometry.
    for node in walk(pcb):
        if node[0]=='net' and len(node)==2 and str(node[1]) in net_map:
            replace_atom(edits,node[1],net_map[str(node[1])])
    (ROOT/(STEM+'.kicad_pcb')).write_text(apply_edits(bt,edits),encoding='utf-8',newline='\n')
    (ROOT/'fp-lib-table').write_text(
        '(fp_lib_table\n (version 7)\n (lib (name "'+PREFIX+'") (type "KiCad") '
        '(uri "${KIPRJMOD}/'+PREFIX+'.pretty") (options "") (descr "Audited import footprints; physical dimensions require part-specific review"))\n)\n',encoding='utf-8')
    (ROOT/'review'/'component-map.json').write_text(json.dumps(component_rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'review'/'net-map.json').write_text(json.dumps(net_map,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Linked',len(component_rows),'components; repaired',smd_count,'SMD pads;',len(holes),'mechanical holes;',len(net_map),'nets reconciled.')

if __name__=='__main__':
    {'prepare':prepare_schematic,'sync':sync_board}[sys.argv[1]]()
