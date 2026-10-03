"""Show an external, purchasable MINI main fuse ahead of the XT60 input."""
from pathlib import Path
import json,uuid,shutil
from kicad_tools import parse,children,child,prop,prop_node,apply_edits

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'review'
BUY='https://www.lcsc.com/pt/product-detail/C55117678.html?is_substitute=1&original_product_code=C315865&original_unit_price=0.3407'
HOLDER='https://www.lcsc.com/zh-CN/product-detail/C55141810.html?is_substitute=1&original_product_code=C206907&original_unit_price=4.0571'
DS='https://www.lcsc.com/datasheet/C55117678.pdf'

def quoted(s):return json.dumps(s,ensure_ascii=False)
def uid():return str(uuid.uuid4())

def run():
    backup=REVIEW/'schematic-backups/2026-10-03-before-external-main-fuse'
    assert not backup.exists()
    backup.mkdir(parents=True)
    for p in [ROOT/'01_power_input.kicad_sch',ROOT/'ProPrj_power_2026-10-02.kicad_sch',
              REVIEW/'redesign_budget.py',REVIEW/'redesign_schematic.py',REVIEW/'verify_redesign.py',
              REVIEW/'原理图修改说明_R2.md',REVIEW/'redesign-components.json']:
        shutil.copy2(p,backup/p.name)
    old=(REVIEW/'schematic-backups/2026-10-03-before-fuse-removal/01_power_input.kicad_sch').read_bytes().decode('utf-8')
    original=parse(old)
    lib=next(n for n in children(child(original,'lib_symbols'),'symbol') if n[1]=='Device:Fuse')
    fuse=next(n for n in children(original,'symbol') if prop(n,'Reference')=='F1')
    ft=old[fuse.start:fuse.end]
    f=parse(ft);edits=[]
    node=child(f,'at');edits.append((node.start,node.end,'(at 40.64 35.56 90)'))
    for key in ['on_board','in_pos_files']:
        a=child(f,key)[1];edits.append((a.start,a.end,'no'))
    values={'Value':'10A/32V 外置总保险', 'Footprint':'','Datasheet':DS,
            'Description':'外置在电池正极、XT60之前；国产MINI插片保险丝；不安装在电源PCB上',
            'Specification':'MINI汽车插片保险丝10A/32VDC；初值，须按启动电流与线束承载实测定型'}
    for p in children(f,'property'):
        if str(p[1]) in values:
            a=p[2];edits.append((a.start,a.end,quoted(values[str(p[1])])))
        at=child(p,'at')
        pos='(at 40.64 30.48 90)' if p[1]=='Reference' else '(at 40.64 27.94 90)' if p[1]=='Value' else '(at 40.64 35.56 0)'
        edits.append((at.start,at.end,pos))
    ft=apply_edits(ft,edits)
    fields={'MPN':'0297010.J','供应商编号':'C55117678','购买链接':BUY,
            '保险座参考链接':HOLDER,'安装位置':'板外，电池正极，XT60之前'}
    extra='\n'.join(f'(property {quoted(k)} {quoted(v)} (at 40.64 35.56 0) (hide yes) (effects (font (size 1 1))))' for k,v in fields.items())
    ft=ft[:-1]+'\n'+extra+'\n)'
    path=ROOT/'01_power_input.kicad_sch';text=path.read_bytes().decode('utf-8');sch=parse(text)
    assert not any(prop(s,'Reference')=='F1' for s in children(sch,'symbol'))
    cached=child(sch,'lib_symbols')
    edits=[(cached.end-1,cached.end-1,'\n'+old[lib.start:lib.end]+'\n')]
    added=[ft]
    for a,b in [((30.48,35.56),(36.83,35.56)),((44.45,35.56),(50.8,35.56)),
                ((50.8,35.56),(50.8,44.45)),((50.8,44.45),(35.56,44.45)),
                ((35.56,44.45),(35.56,52.07))]:
        added.append(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {quoted(uid())}))')
    added.append(f'(junction (at 35.56 52.07) (diameter 0) (color 0 0 0 0) (uuid {quoted(uid())}))')
    added.append(f'(label "电池正极" (at 30.48 35.56 180) (effects (font (size 0.85 0.85)) (justify right bottom)) (uuid {quoted(uid())}))')
    edits.append((sch.end-1,sch.end-1,'\n'+'\n'.join(added)+'\n'))
    replacements={
      '输入：三串11.1V锂聚合物电池 / 外部保护板与防反接':'输入：三串11.1V锂聚合物电池 / 外置总保险与防反接',
      '电池：11.1V / 3600mAh / 35C；满电12.6V。\n照片不能确认保护板；35C不是短路保护。\n电池端须有过流、短路与单体电芯保护。\n本板不装保险丝；保护电流须匹配线束与铜箔。\nQ1：漏极接电池输入，源极接保护后母线。\n瞬态抑制二极管不能把电压固定在17V以下。':
      '电池：11.1V / 3600mAh / 35C；满电12.6V。\nF1外置在电池正极、XT60之前，使用通用MINI座。\n保险丝：集电通0297010.J，10A/32V，初值待实测。\n照片不能确认电池保护板；单体电芯保护仍须落实。\nQ1保留防反接；35C不是短路保护。\n瞬态抑制二极管不能把电压固定在17V以下。'}
    for n in children(sch,'text'):
        if str(n[1]) in replacements:
            a=n[1];edits.append((a.start,a.end,quoted(replacements[str(a)])))
    path.write_bytes(apply_edits(text,edits).encode('utf-8'))
    path=ROOT/'ProPrj_power_2026-10-02.kicad_sch';text=path.read_bytes().decode('utf-8');sch=parse(text);edits=[]
    for n in children(sch,'text'):
        val=str(n[1]);new={'外部保护板、防反接与电压窗口':'外置总保险、防反接与电压窗口',
            '电池端必须有过流、短路与电芯保护；本板不装保险丝。原电路板未同步，不能直接投板。':
            '电池正极先接外置MINI总保险，再接XT60；单体电芯保护仍须落实。原电路板未同步。'}.get(val)
        if new:edits.append((n[1].start,n[1].end,quoted(new)))
    assert len(edits)==2
    path.write_bytes(apply_edits(text,edits).encode('utf-8'))
    meta_path=REVIEW/'redesign-components.json';meta=json.loads(meta_path.read_text(encoding='utf-8'))
    meta.append({'sheet':'01_power_input.kicad_sch','reference':'F1','unit':1,'value':values['Value'],
                 'footprint':'','lib_id':'Device:Fuse','mpn':'0297010.J','datasheet':DS,'dnp':False,
                 'on_board':False,'采购链接':BUY,'保险座参考链接':HOLDER})
    meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Added external F1 before CN1; excluded from the PCB; F2/F3 remain absent.')

if __name__=='__main__':run()
