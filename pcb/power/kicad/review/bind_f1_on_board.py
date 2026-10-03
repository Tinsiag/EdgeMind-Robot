"""Make F1 a PCB-mounted MINI fuse holder and synchronize it losslessly."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess,uuid
import xml.etree.ElementTree as ET
import pcbnew
from kicad_tools import parse,children,child,prop,prop_node,apply_edits
from sync_pcb_from_schematic import geometry

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'review'
STEM='ProPrj_power_2026-10-02'
FP='Fuse:Fuseholder_Blade_Mini_Keystone_3568'
BUY='https://www.lcsc.com/pt/product-detail/C55117678.html?is_substitute=1&original_product_code=C315865&original_unit_price=0.3407'
HOLDER='https://www.digikey.cn/zh/products/detail/keystone-electronics/3568/2137306'
DS='https://www.lcsc.com/datasheet/C55117678.pdf'
CLI='D:/KiCad/10.0/bin/kicad-cli.exe'

def q(s):return json.dumps(s,ensure_ascii=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def uid():return str(uuid.uuid4())

def run():
    board_path=ROOT/(STEM+'.kicad_pcb')
    board_before=board_path.read_bytes()
    original_board=pcbnew.LoadBoard(str(board_path))
    assert not original_board.FindFootprintByReference('F1')
    old_geometry={f.GetReference():geometry(f) for f in original_board.GetFootprints()}
    assert len(old_geometry)==210
    backup=REVIEW/'pcb-sync-backups'/datetime.now().strftime('%Y-%m-%d_%H%M%S-before-F1-onboard')
    backup.mkdir(parents=True,exist_ok=False)
    paths=[board_path,ROOT/(STEM+'.kicad_pro'),ROOT/(STEM+'.kicad_sch'),*sorted(ROOT.glob('0[1-9]_*.kicad_sch')),
           ROOT/'README.md',REVIEW/'原理图修改说明_R2.md',REVIEW/'PCB同步说明_R2.md',
           REVIEW/'redesign-components.json',REVIEW/'verify_redesign.py',REVIEW/'redesign_budget.py',
           REVIEW/'schematic_overview.py',REVIEW/'redesign-verification.json',REVIEW/'footprint-model-audit.json',
           REVIEW/'电源板物料清单_R2.csv',REVIEW/'电源板接口线序_R2.csv',REVIEW/'电源板原理图_R2.pdf',
           ROOT.parents[2]/'doc/项目功能需求书.md',ROOT.parents[2]/'doc/文档.md']
    for p in paths:
        if p.is_file():shutil.copy2(p,backup/p.name)
    baseline={'操作':'F1改为板载MINI保险座并同步PCB','PCB_SHA256':sha(board_path),
              'PROJECT_SHA256':sha(ROOT/(STEM+'.kicad_pro')),'备份目录':str(backup)}
    (REVIEW/'f1-board-review-state.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2),encoding='utf-8')

    p=ROOT/'01_power_input.kicad_sch';s=p.read_bytes().decode('utf-8');t=parse(s);edits=[]
    f=next(n for n in children(t,'symbol') if prop(n,'Reference')=='F1')
    fuse_symbol_uuid=str(child(f,'uuid')[1])
    for name in ['on_board','in_pos_files']:
        a=child(f,name)[1];edits.append((a.start,a.end,'yes'))
    a=child(f,'at');edits.append((a.start,a.end,'(at 76.2 52.07 90)'))
    values={'Value':'10A/32V MINI总保险','Footprint':FP,
            'Description':'板载MINI总保险；XT60正极经F1再进入防反接管；保险片与保险座分别采购',
            'Specification':'MINI汽车插片保险丝10A/32VDC；初值须实测；保险座四孔9.92×3.40mm、钻孔1.78mm',
            '保险座参考链接':HOLDER,'安装位置':'板上，XT60正极之后、防反接管之前'}
    for n in children(f,'property'):
        name=str(n[1])
        if name in values:
            a=n[2];edits.append((a.start,a.end,q(values[name])))
        a=child(n,'at')
        new='(at 76.2 46.99 90)' if name=='Reference' else '(at 76.2 44.45 90)' if name=='Value' else '(at 76.2 52.07 0)'
        edits.append((a.start,a.end,new))
    fields={'保险座型号':'3568 / 同四孔尺寸兼容品待核对','保险座数据手册':'https://www.keyelco.com/product-pdf.cfm?p=306',
            '保险座供应商编号':'C5249699（立创查询时缺货，可核对其他渠道）'}
    addition='\n'.join(f'(property {q(k)} {q(v)} (at 76.2 52.07 0) (hide yes) (effects (font (size 1 1))))' for k,v in fields.items())
    edits.append((f.end-1,f.end-1,'\n'+addition+'\n'))
    flag=next(n for n in children(t,'symbol') if prop(n,'Reference')=='#FLG999')
    for a in [child(flag,'at'),*[child(n,'at') for n in children(flag,'property')]]:
        edits.append((a.start,a.end,'(at 50.8 52.07 0)'))
    external={((30.48,35.56),(36.83,35.56)),((44.45,35.56),(50.8,35.56)),
              ((50.8,35.56),(50.8,44.45)),((50.8,44.45),(35.56,44.45)),((35.56,44.45),(35.56,52.07))}
    removed=0;shortened=0
    for n in children(t,'wire'):
        pts=tuple(tuple(map(float,a[1:3])) for a in child(n,'pts')[1:])
        if pts in external:
            edits.append((n.start,n.end,''));removed+=1
        elif pts==((35.56,52.07),(80.01,52.07)):
            a=child(n,'pts')[2];edits.append((a.start,a.end,'(xy 72.39 52.07)'));shortened+=1
    assert removed==5 and shortened==1
    label=next(n for n in children(t,'label') if n[1]=='电池正极')
    a=child(label,'at');edits.append((a.start,a.end,'(at 50.8 52.07 0)'))
    a=child(child(label,'effects'),'justify');edits.append((a.start,a.end,'(justify left top)'))
    dot=next(n for n in children(t,'junction') if tuple(map(float,child(n,'at')[1:3]))==(35.56,52.07))
    a=child(dot,'at');edits.append((a.start,a.end,'(at 50.8 52.07)'))
    for n in children(t,'text'):
        val=str(n[1]);new=None
        if val=='输入：三串11.1V锂聚合物电池 / 外置总保险与防反接':
            new='输入：三串11.1V锂聚合物电池 / 板载总保险与防反接'
        elif val.startswith('电池：11.1V / 3600mAh / 35C；满电12.6V。'):
            new=('电池：11.1V / 3600mAh / 35C；满电12.6V。\nF1板载：XT60正极之后、防反接管之前。\n'
                 '保险片：集电通0297010.J，10A/32V，初值待实测。\n保险座：四孔9.92×3.40mm；与保险片分别采购。\n'
                 '照片不能确认电池保护板；单体电芯保护仍须落实。\n瞬态抑制二极管不能把电压固定在17V以下。')
        if new:edits.append((n[1].start,n[1].end,q(new)))
    p.write_bytes(apply_edits(s,edits).encode('utf-8'))
    replacements={'外置总保险、防反接与电压窗口':'板载总保险、防反接与电压窗口',
        '电池正极先接外置MINI总保险，再接XT60；单体电芯保护仍须落实。PCB封装与网络已同步，布局布线待完成。':
        '电池经XT60接入板载MINI总保险；单体电芯保护仍须落实。PCB封装与网络已同步，布局布线待完成。',
        '入口总保险外置；模块内部限流须校准':'入口总保险板载；模块内部限流须校准',
        '入口总保险外置，电池单体保护和模块限流仍须落实。':'入口总保险板载，电池单体保护和模块限流仍须落实。'}
    for p in [ROOT/(STEM+'.kicad_sch'),ROOT/'05_motor_left.kicad_sch',ROOT/'06_motor_right.kicad_sch',ROOT/'08_rail_protection.kicad_sch']:
        s=p.read_bytes().decode('utf-8');t=parse(s);edits=[]
        for n in children(t,'text'):
            new=str(n[1])
            for old,repl in replacements.items():new=new.replace(old,repl)
            if new!=str(n[1]):edits.append((n[1].start,n[1].end,q(new)))
        assert edits,p
        p.write_bytes(apply_edits(s,edits).encode('utf-8'))
    meta_path=REVIEW/'redesign-components.json';meta=json.loads(meta_path.read_text(encoding='utf-8'))
    item=next(n for n in meta if n.get('reference')=='F1')
    item.update({'value':values['Value'],'footprint':FP,'on_board':True,'保险座参考链接':HOLDER,'安装位置':values['安装位置']})
    meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    netlist=REVIEW/'f1-board-current.net.xml'
    subprocess.run([CLI,'sch','export','netlist','--format','kicadxml','--output',str(netlist),str(ROOT/(STEM+'.kicad_sch'))],cwd=ROOT,check=True)
    xml=ET.parse(netlist).getroot()
    comps={c.get('ref'):c for c in xml.findall('components/comp')}
    assert len(comps)==211 and comps['F1'].find("property[@name='exclude_from_board']") is None
    nets={(n.get('ref'),n.get('pin')):net.get('name') for net in xml.findall('nets/net') for n in net.findall('node')}
    assert nets['CN1','2']==nets['F1','1']
    assert nets['F1','2']==nets['Q1','2']
    assert nets['F1','1']!=nets['F1','2']
    source=(REVIEW/'pcb-sync-backups/2026-10-03_160748'/(STEM+'.kicad_pcb')).read_bytes().decode('utf-8')
    original_fuse=next(n for n in children(parse(source),'footprint') if prop(n,'Reference')=='F1')
    ftext=source[original_fuse.start:original_fuse.end];ft=parse(ftext);edits=[]
    for n in children(ft,'property'):
        if n[1]=='Value':edits.append((n[2].start,n[2].end,q(values['Value'])))
        elif n[1]=='Reference' and child(n,'hide'):
            a=child(n,'hide')[1];edits.append((a.start,a.end,'no'))
        elif str(n[1]) in values:edits.append((n[2].start,n[2].end,q(values[str(n[1])])))
    present={str(n[1]):n for n in children(ft,'property')}
    schematic=parse((ROOT/'01_power_input.kicad_sch').read_bytes().decode('utf-8'))
    fuse=next(n for n in children(schematic,'symbol') if prop(n,'Reference')=='F1')
    for n in children(fuse,'property'):
        name,value=str(n[1]),str(n[2])
        if name in ['Reference','Value','Footprint'] or name in values:continue
        if name in present:
            a=present[name][2]
            edits.append((a.start,a.end,q(value)))
        else:
            field=f'(property {q(name)} {q(value)} (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))'
            edits.append((ft.end-1,ft.end-1,'\n'+field+'\n'))
    for n in children(ft,'pad'):
        a=child(n,'net')[1];edits.append((a.start,a.end,q(nets['F1',str(n[1])])))
    ftext=apply_edits(ftext,edits)
    text=board_before.decode('utf-8');t=parse(text);edits=[];changed=[]
    for fp in children(t,'footprint'):
        ref=prop(fp,'Reference')
        for pad in children(fp,'pad'):
            pin=str(pad[1])
            if not pin:continue
            a=child(pad,'net')[1];new=nets[ref,pin]
            if a!=new:
                edits.append((a.start,a.end,q(new)));changed.append([ref,pin,str(a),new])
    assert len(changed)==2,changed
    edits.append((t.end-1,t.end-1,'\n'+ftext+'\n'))
    after=apply_edits(text,edits).encode('utf-8')
    candidate=backup/(STEM+'-candidate.kicad_pcb');candidate.write_bytes(after)
    b=pcbnew.LoadBoard(str(candidate));fps={f.GetReference():f for f in b.GetFootprints()}
    assert set(fps)==set(comps)
    for ref,g in old_geometry.items():assert geometry(fps[ref])==g,(ref,'Moved existing component')
    for ref,f in fps.items():
        assert str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName())==comps[ref].findtext('footprint')
        for pad in f.Pads():
            if pad.GetNumber():assert pad.GetNetname()==nets[ref,pad.GetNumber()]
    assert board_path.read_bytes()==board_before,'Preserve concurrent PCB changes'
    board_path.write_bytes(after)
    report={'日期':datetime.now().isoformat(timespec='seconds'),'备份目录':str(backup),
        '修改前PCB_SHA256':baseline['PCB_SHA256'],'修改后PCB_SHA256':sha(board_path),
        'F1封装':FP,'F1板载':True,'F1原理图UUID':fuse_symbol_uuid,
        '板上元件数':len(fps),'原有210个元件位置与方向及焊盘几何保留':True,
        'F1位置毫米':list(pcbnew.ToMM(fps['F1'].GetPosition())),
        'F1模型':[m.m_Filename for m in fps['F1'].Models()],
        '输入连接':'CN1.2 -> F1.1; F1.2 -> Q1.2','原有焊盘网络调整':changed,
        '保险片购买链接':BUY,'保险座购买参考':HOLDER,'保险座原厂图纸':'https://www.keyelco.com/product-pdf.cfm?p=306',
        '采购边界':'封装按3568标准四孔；国产同孔位保险座尚未定型，不将01530008.J直接认作兼容。'}
    (REVIEW/'f1-board-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':run()
