"""Audit the exported native netlist against functional intent and package pin sets."""
from pathlib import Path
import xml.etree.ElementTree as ET
import hashlib,json,csv,re,argparse
from collections import Counter,defaultdict
from kicad_tools import parse,children,child,prop
from schematic_chinese import NETS,translated

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'review'
STOCK=Path('D:/KiCad/10.0/share/kicad')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state-baseline',type=Path,help='本轮修改前保存的PCB与项目配置哈希；用于保留用户在先前轮次后的编辑')
args=parser.parse_args()
baseline=json.loads(args.state_baseline.read_text(encoding='utf-8-sig')) if args.state_baseline else None
BOARD_HASH=baseline['PCB_SHA256'] if baseline else 'b1f0ae58f0c056b78fcf4b2b0c4fc0f67e39ae8b1f3ccb8ed98e1bcf4ab4488d'
export=ET.parse(REVIEW/'redesign.net.xml').getroot()
comps={c.get('ref'):c for c in export.findall('components/comp')}
pn={(p.get('ref'),p.get('pin')):n.get('name') for n in export.findall('nets/net') for p in n.findall('node')}
checks=[]
def net(ref,pin):return pn[ref,str(pin)]
def want(ref,pin,name):
    assert net(ref,pin)==NETS.get(name,name),(ref,pin,net(ref,pin),name)
    checks.append(f'{ref}.{pin}={name}')
def same(*pins):
    nets=[net(ref,pin) for ref,pin in pins]
    assert len(set(nets))==1,(pins,nets)
    checks.append('='.join(f'{r}.{p}' for r,p in pins))
def different(*pins):
    nets=[net(r,p) for r,p in pins]
    assert len(set(nets))==len(nets),(pins,nets)
    checks.append('互相隔离：'+','.join(f'{r}.{p}' for r,p in pins))

# Independent sources: no hard paralleling; power routing through protection.
for r,p,n in [('CN1',1,'GND'),('Q1',3,'VBAT_SYS'),('Q3',3,'VBAT_SYS'),('Q3',2,'VLOGIC_IN'),
              ('Q2',3,'VBAT_SYS'),('Q2',2,'VM_SWITCHED'),('JP1',1,'+3V3_ONBOARD'),
              ('JP1',2,'+3V3'),('JP1',3,'3V3_FPGA_IN'),('J1',6,'3V3_FPGA_IN'),
              ('J2',3,'3V3_FPGA_IN'),('J9',1,'3V3_FPGA_IN'),('U3',1,'+3V3_RAW'),
              ('Q12',2,'+3V3_RAW'),('Q12',3,'+3V3_ONBOARD')]:want(r,p,n)
assert not ({'F2','F3'} & set(comps)), 'Motor branch fuses must remain removed'
assert 'F1' in comps
f1_on_board=comps['F1'].find("property[@name='exclude_from_board']") is None
if f1_on_board:
    assert comps['F1'].findtext('footprint')=='Fuse:Fuseholder_Blade_Mini_Keystone_3568'
    checks.append('F1为板载MINI总保险；F2/F3保持取消')
    same(('CN1',2),('F1',1));same(('F1',2),('Q1',2))
    different(('CN1',2),('Q1',2))
else:
    assert not comps['F1'].findtext('footprint')
    checks.append('F1为板外总保险；板上无F1/F2/F3保险丝')
    same(('CN1',2),('Q1',2));same(('F1',2),('CN1',2))
same(('Q1',1),('D2',2));different(('F1',1),('F1',2))
different(('JP1',1),('JP1',2),('JP1',3),('Q8',5),('Q10',5))
for buck,mos,ctrl,usb,rail in [('U5','Q8','U7','USB1','+5V_FPGA'),('U1','Q10','U8','USB2','+5V_AI')]:
    want(buck,2,'VLOGIC_IN');want(buck,6,'BUCK_ENABLE')
    for p in [1,4]:want(buck,p,'GND')
    for p in [1,2,3]:want(mos,p,rail)
    for p in [5,6,7,8]:want(mos,p,rail+'_PROT')
    want(ctrl,1,rail+'_PROT');want(ctrl,2,'GND')
    same((ctrl,8),(usb,'A9'),(usb,'B9'))
    same((ctrl,6),(usb,'A5'));same((ctrl,5),(usb,'B5'))
    for p in ['A12','B12','SH']:want(usb,p,'GND')
    different((ctrl,1),(ctrl,8),(ctrl,6),(ctrl,5))

# Safety combinational chain and asynchronous-clear latch.
for r,p,n in [('U10',1,'ESTOP_OK'),('U10',2,'MOTOR_PERMIT'),('U10',4,'POR_OK'),
              ('U10',5,'EXT_KILL_N'),('U10',13,'MOTOR_POWER_OK'),('U12',2,'+3V3'),
              ('U12',3,'MOTOR_ARM'),('U12',4,'+3V3'),('U12',5,'MOTOR_ARMED')]:want(r,p,n)
for pins in [(('U10',3),('U10',9)),(('U10',6),('U10',10)),(('U10',8),('U10',12)),(('U10',11),('U12',1))]:same(*pins)
for r in ['U10','U11','U12']:want(r,14,'+3V3');want(r,7,'GND')
for p in [11,12,13]:want('U12',p,'GND')
want('U12',10,'+3V3')
for divider in ['R77','R81']:
    want(divider,2,'GND')
    different((divider,1),(divider,2))

# The four PWM gate outputs are distinct from filtered encoder channels.
for module,motor,amp,side,gatepins,encpins,shunt in [
    ('U2','J3','U25','L',[(1,2,3,12),(4,5,6,11)],[(3,7),(4,8)],'R84'),
    ('U4','J4','U26','R',[(9,10,8,12),(12,13,11,11)],[(3,2),(4,1)],'R94')]:
    for k in [3,4,7,8]:want(module,k,'GND')
    for k in [6,9]:want(module,k,'VM_'+side)
    for k in [5,10]:want(module,k,'VREF_'+side)
    same((module,1),(motor,1));same((module,2),(motor,6))
    want(motor,2,'+3V3');want(motor,5,'GND')
    for i,(a,b,o,k) in enumerate(gatepins):
        want('U11',a,side+'_PWM_'+('FWD_RAW' if i==0 else 'REV_RAW'))
        want('U11',b,'MOTOR_ARMED');same(('U11',o),(module,k))
    want(amp,2,'GND');want(amp,5,'+3V3');want(amp,4,'VM_'+side)
    same((amp,3),(shunt,1));same((amp,4),(shunt,2))
    want(shunt,1,'VM_SWITCHED')
    for k,ctrlpin in encpins:
        ch='A' if k==3 else 'B';want(motor,k,'ENC_'+side+'_'+ch)
        want('J1' if side=='L' else 'J2',ctrlpin,'ENC_'+side+'_'+ch+'_FPGA')
    different((module,11),(module,12),(motor,3),(motor,4),('J1' if side=='L' else 'J2',encpins[0][1]),('J1' if side=='L' else 'J2',encpins[1][1]))
    for p in [13,14]:assert net(module,p).startswith('unconnected-')

# For this migration, compare the entire native connectivity against the
# pre-edit netlist, permitting only removal and bridging of F1/F2/F3.
if baseline and baseline.get('操作','').startswith(('删除板上F1','F1改为板载')):
    before=ET.parse(REVIEW/'before-fuse-removal.net.xml').getroot()
    removed={'F2','F3'} if f1_on_board else {'F1','F2','F3'}
    previous_comps={c.get('ref'):c for c in before.findall('components/comp')}
    assert set(comps)-{'F1'}==set(previous_comps)-{'F1','F2','F3'}
    for ref,c in comps.items():
        if ref=='F1':continue
        assert ET.tostring(c)==ET.tostring(previous_comps[ref]),(ref,'Retained component changed')
    old_nets=before.findall('nets/net')
    parent=list(range(len(old_nets)))
    old_pin_net={(p.get('ref'),p.get('pin')):i for i,n in enumerate(old_nets) for p in n.findall('node')}
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for ref in removed:
        parent[find(old_pin_net[ref,'1'])]=find(old_pin_net[ref,'2'])
    expected=defaultdict(set)
    for i,n in enumerate(old_nets):
        expected[find(i)].update((p.get('ref'),p.get('pin')) for p in n.findall('node') if p.get('ref') not in removed)
    expected_sets={frozenset(pins) for pins in expected.values() if pins}
    actual_sets={frozenset((p.get('ref'),p.get('pin')) for p in n.findall('node') if p.get('ref') not in removed) for n in export.findall('nets/net')}
    actual_sets.discard(frozenset())
    assert expected_sets==actual_sets,{'missing':expected_sets-actual_sets,'unexpected':actual_sets-expected_sets}
    checks.append('全网表比对：F1在XT60之后串联，F2/F3移除并合并网络；其余元件和连接不变' if f1_on_board else
                  '全网表比对：移除板上三只保险丝；F1改至板外XT60之前，其余元件和连接不变')

# Files, stock package pin sets and existing model paths.
audit=[]
for ref,c in comps.items():
    if c.find("property[@name='exclude_from_board']") is not None:
        assert ref=='F1' and not c.findtext('footprint')
        audit.append({'位号':ref,'封装':'板外元件，无PCB封装','来源':'电池正极外置MINI总保险',
                      '焊盘与符号引脚一致':'不适用，已排除在PCB之外','模型':[],
                      '采购料号':'0297010.J / C55117678','安装位置':'电池正极，XT60之前'})
        continue
    fp=c.findtext('footprint');lib,name=fp.split(':',1)
    path=(ROOT/(lib+'.pretty') if lib=='EdgeMind_Module' else STOCK/'footprints'/(lib+'.pretty'))/(name+'.kicad_mod')
    assert path.is_file(),(ref,path)
    parsed=parse(path.read_text(encoding='utf-8'))
    pads={str(p[1]) for p in children(parsed,'pad') if str(p[1])}
    pins={p.get('num') for p in c.findall('units/unit/pins/pin')}
    assert pads==pins,(ref,pads,pins)
    models=[]
    for model in children(parsed,'model'):
        s=str(model[1]).replace('${KICAD10_3DMODEL_DIR}',str(STOCK/'3dmodels')).replace('${KIPRJMOD}',str(ROOT))
        resolved=Path(s)
        assert resolved.is_file(),(ref,s)
        models.append(str(resolved))
    assert models or ref=='TP1',(ref,'missing 3D')
    if lib=='EdgeMind_Module':
        row=23.0005 if ref=='U2' else 23.1275
        positions={str(p[1]):tuple(map(float,child(p,'at')[1:3])) for p in children(parsed,'pad')}
        for i in range(7):
            assert positions[str(i+1)]==(0,round(i*2.54,2))
            assert positions[str(i+8)]==(row,round(i*2.54,2))
    audit.append({'位号':ref,'封装':fp,'来源':'项目自建双排排母' if lib=='EdgeMind_Module' else 'KiCad自带库','焊盘与符号引脚一致':True,'模型':models})
sha=hashlib.sha256((ROOT/'ProPrj_power_2026-10-02.kicad_pcb').read_bytes()).hexdigest()
board_matches_baseline=sha==BOARD_HASH
if not baseline:
    assert board_matches_baseline
erc=json.loads((REVIEW/'redesign-erc.json').read_text(encoding='utf-8'))
violations=[v for s in erc['sheets'] for v in s['violations']]
assert not violations
fontfiles=[ROOT/'ProPrj_power_2026-10-02.kicad_sch',*sorted(ROOT.glob('0[1-9]_*.kicad_sch'))]
for p in fontfiles:
    if p.name=='05_at8236_motors.kicad_sch':continue
    assert '(face ' not in p.read_text(encoding='utf-8')
main=parse((ROOT/'ProPrj_power_2026-10-02.kicad_sch').read_text(encoding='utf-8'))
sheets=children(main,'sheet');assert len(sheets)==9
port_count=0
for sheet in sheets:
    file=prop(sheet,'Sheetfile');pins=children(sheet,'pin')
    assert pins,'Overview sheet missing actual hierarchy pins'
    sub=parse((ROOT/file).read_text(encoding='utf-8'))
    aliases={str(n[1]) for n in children(sub,'hierarchical_label')}
    assert {str(n[1]) for n in pins}==aliases,(file,'Hierarchy port mismatch')
    port_count+=len(pins)
if baseline:
    assert hashlib.sha256((ROOT/'ProPrj_power_2026-10-02.kicad_pro').read_bytes()).hexdigest()==baseline['PROJECT_SHA256'],'Project configuration differs from this turn baseline'
else:
    previous=json.loads((REVIEW/'schematic-backups/2026-10-03-before-chinese-page-layout/ProPrj_power_2026-10-02.kicad_pro').read_text(encoding='utf-8'))
    current=json.loads((ROOT/'ProPrj_power_2026-10-02.kicad_pro').read_text(encoding='utf-8'))
    previous['schematic']['page_layout_descr_file']='原理图中文图框.kicad_wks'
    assert previous==current,'Unintended project configuration edit'
external_count=sum(c.find("property[@name='exclude_from_board']") is not None for c in comps.values())
result={'日期':erc['date'],'KiCad版本':erc['kicad_version'],'电气规则违规数':len(violations),
        '元件总数':len(comps),'板上元件数':len(comps)-external_count,'板外元件数':external_count,
        '原生原理图页数':len(erc['sheets']),'功能网络断言数量':len(checks),
        '检查结果':'通过','PCB_SHA256':sha,
        'PCB基线_SHA256':BOARD_HASH,'PCB相对修改前基线一致':board_matches_baseline,
        'PCB检查方式':'只读取哈希；本核验脚本不写入或回滚PCB',
        '工作区变化说明':'PCB在基线记录之后发生变化；保留当前内容，不能声称整个工作区逐字节不变' if not board_matches_baseline else 'PCB与本轮基线一致',
        '修改基线':str(args.state_baseline) if baseline else '第二版原理图修改前的工作区',
        **({'本轮项目配置未修改':True} if baseline else {'项目配置仅修改原理图中文图框路径':True}),
        '默认字体':True,'主页层级模块数':len(sheets),'主页真实层级引脚数':port_count,'功能网络检查':checks,
        '3D说明':('F1为板载MINI保险座，使用自带保险座模型。' if f1_on_board else 'F1为板外元件，无PCB封装和模型。')+
                 '板上TP1为裸铜测试焊盘；其余全部有存在的模型。XT60使用完整七实体补充模型。',
        '模型/实物边界':'模型文件存在、焊盘编号对应不等于机械公差或实物模块已验收。'}
(REVIEW/'redesign-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(REVIEW/'footprint-model-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')

# Chinese procurement worksheet: technical part numbers and package identifiers stay exact.
groups=defaultdict(list)
for ref,c in comps.items():
    fields={f.get('name'):f.text or '' for f in c.findall('fields/field')}
    spec=fields.get('Specification',c.findtext('value'))
    for a,b in [('low-ESR','低等效串联电阻'),('slow','慢断'),('(initial)','（初始值，须实测确认）'),('dual module / vendor-specific','双路模块，供应商版本待核对')]:spec=spec.replace(a,b)
    groups[(translated(spec),fields.get('MPN',''),c.findtext('footprint'))].append(ref)
def refkey(ref):
    m=re.match(r'([A-Z]+)(\d+)',ref);return (m.group(1),int(m.group(2))) if m else (ref,0)
with (REVIEW/'电源板物料清单_R2.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['位号','数量','规格与用途','型号','KiCad封装','采购核对事项','安装位置','采购链接','保险座参考链接'])
    for (spec,mpn,fp),refs in sorted(groups.items(),key=lambda item:refkey(sorted(item[1],key=refkey)[0])):
        note='核对实际外形、焊盘、额定值及温升；无完整采购料号的物料尚未定型'
        if refs==['F1']:
            note=('板载MINI总保险；保险片为集电通0297010.J/C55117678，10A初值待实测；保险座为3568四孔式，孔距9.92×3.40mm、钻孔1.78mm，保险片与座分别采购；国产同孔位兼容座待核对；01530008.J未确认兼容，勿直接套用' if f1_on_board else
                  '板外总保险，集电通0297010.J/C55117678；10A为初值，按启动峰值和线束承载定型；保险座链接为焊板式座参考，外置组件需固定绝缘；使用带线座须核对MINI尺寸、接触与纯铜线承载；不绑定电源PCB封装')
        elif 'AT8236' in fp:note='双路AT8236模块；测采样电阻并校准；排距沿用旧PCB，仍须试插'
        elif fp.startswith('Fuse:'):
            kind='MINI汽车插片式，额定32VDC' if 'Blade_Mini' in fp else '5×20mm慢断保险丝管，核对直流使用条件'
            note=kind+'；保险丝与保险座分别采购；优先国产通用件，不强制采购封装名中的品牌；保险座孔距及机械尺寸须逐项匹配；额定电流与直流分断能力须核对'
        elif mpn=='HUSB305-02':note='必须为-02版、TSOT-23-8；不可误购DFN版本；准确采购代码与单价待确认'
        elif mpn=='FXL0630-4R7-M':note='4.7µH±20%；最大直流电阻33mΩ；额定温升电流6A；核对具体温升/饱和定义'
        elif mpn=='USB4125-GF-A':note='普通1.0mm定位柱版六针供电口；不可混用-0190加长定位柱版'
        fields={x.get('name'):x.text or '' for x in comps[refs[0]].findall('fields/field')}
        w.writerow([','.join(sorted(refs,key=refkey)),len(refs),spec,mpn,fp,note,
                    fields.get('安装位置','板上'),fields.get('购买链接',''),fields.get('保险座参考链接','')])
with (REVIEW/'电源板接口线序_R2.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['接口位号','用途','引脚编号','网络或功能'])
    for ref,c in sorted(comps.items(),key=lambda item:refkey(item[0])):
        if ref.startswith(('J','CN','USB')) or ref in ['U2','U4']:
            for (r,p),n in sorted(pn.items()):
                if r==ref:w.writerow([ref,c.findtext('value'),p,n])
print(json.dumps({k:v for k,v in result.items() if k!='功能网络检查'},ensure_ascii=False,indent=2))
