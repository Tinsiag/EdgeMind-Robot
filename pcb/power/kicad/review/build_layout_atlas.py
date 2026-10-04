"""Package the checked SVG/PNG illustrations as a browsable, offline reference atlas."""
from pathlib import Path
from html import escape
import json, hashlib, xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]; O=R/'review/all-layout'
D=json.loads((O/'绘图核验.json').read_text(encoding='utf-8'))
A=json.loads((R/'review/all-layout-current.json').read_text(encoding='utf-8'))
X=ET.parse(R/'review/all-layout-current.net.xml').getroot()
CC={c.get('ref'):c for c in X.findall('components/comp')}
NN={(n.get('ref'),n.get('pin')):v.get('name') for v in X.findall('nets/net') for n in v.findall('node')}
checks=[]
for number,file in [('01','input-layout-current.net.xml'),('02','lm393-layout-current.net.xml'),('03','usb-schematic-current.net.xml')]:
 page=next(p for p in D['pages'] if p['name'].startswith(number+'_'))
 old=ET.parse(R/'review'/file).getroot()
 oc={c.get('ref'):c for c in old.findall('components/comp')}
 on={(n.get('ref'),n.get('pin')):v.get('name') for v in old.findall('nets/net') for n in v.findall('node')}
 for ref in page['refs']:
  for key in ['value','footprint']:assert CC[ref].findtext(key)==oc[ref].findtext(key),(ref,key)
  assert {p:v for (r,p),v in NN.items() if r==ref}=={p:v for (r,p),v in on.items() if r==ref},ref
 checks.append(dict(figure=number,existing_netlist=file,refs_checked=len(page['refs']),values_footprints_pin_nets_unchanged=True))
D['reused_figures_verification']=checks
(O/'绘图核验.json').write_text(json.dumps(D,ensure_ascii=False,indent=2),encoding='utf-8')
SOURCES=[
 ('MPS MP2236，Rev.1.1，第 17 页，图 6', 'https://www.monolithicpower.com/en/documentview/productdocument/index/version/2/document_type/Datasheet/lang/EN/sku/MP2236/document_id/4411/', '图 03/04：输入回路短而宽、反馈与开关区域分开；原厂布局的相对关系按本项目封装调整。'),
 ('Diodes AP63200/01/03/05，DS41326 Rev.3-2，第 15 页，图 25', 'https://www.diodes.com/datasheet/download/AP63200-AP63201-AP63203-AP63205.pdf', '图 05：输入电容近放、底层地与散热过孔、反馈绕开开关。固定 3.3V 型号的反馈直接取输出；不照搬可调版分压。原厂建议双面 2oz 铜，本项目的实际铜厚仍待板厂确认。'),
 ('TI INA180，Rev.H，第 27–28 页，9.4 节', 'https://www.ti.com/lit/ds/symlink/ina180.pdf', '图 07/08：采样电阻开尔文连接，两根检测线接近等长，供电去耦贴近 5 脚；功率通路与检测线分开。'),
 ('TI LM393B/LM2903B，Rev.AH，第 20 页，7.2.5 节', 'https://www.ti.com/lit/ds/symlink/lm2903.pdf', '图 02/09/10/11：去耦贴近电源引脚，输入电阻靠近比较器，敏感输入远离功率和输出干扰。本次官网 LM393 链接超时，使用同系列完整原厂手册的 LM2903 链接。'),
 ('TI TL431/TL432，Rev.S，第 4、27、31 页', 'https://www.ti.com/lit/ds/symlink/tl431.pdf', '图 01/02：U21 使用 TL431 的 DBZ 引脚，不照抄 TL432 的 1/2 脚。基准沿安静区分配；任何新增并联电容须另查稳定区，本次没有加电容。'),
 ('Hynetek HUSB305，13 页完整版，第 3、9 页', 'https://www.hynetek.com/uploadfiles/site/219/news/2a2293ad-5b62-48ab-b902-a09e7bf50a18.pdf', '图 03：按 TSOT-23-8 的引脚和典型电路确定输入、输出电容与接口的位置。资料没有独立布局章节，具体方向和间距为工程建议。'),
 ('Nexperia 74HC08/74HCT08，第 2 页引脚', 'https://assets.nexperia.com/documents/data-sheet/74HC_HCT08.pdf', '图 06：核对 14 脚供电、7 脚地和四组与门。资料未给本项目的整板布局；去耦和控制链顺序为工程安排。'),
 ('Nexperia 74HC74/74HCT74，引脚与逻辑表', 'https://assets.nexperia.com/documents/data-sheet/74HC_HCT74.pdf', '图 06：核对锁存器的时钟、清零和供电引脚；不改逻辑电路。'),
 ('Microchip MCP100 产品与官方资料入口', 'https://www.microchip.com/en-us/product/MCP100', 'U13 为上电复位。官方旧 PDF 文本提取存在乱码，因此未从它推导额外布局规则；引脚与当前原理图及封装逐项对应，C120 近放属于工程建议。'),
 ('Infineon IRF4905 原厂手册', 'https://www.infineon.com/assets/row/public/documents/24/49/infineon-irf4905-datasheet-en.pdf', '图 01/09：栅、漏、源与漏极金属背板的身份；开关具体摆放按现有拓扑安排。'),
 ('Infineon IRLZ44N 原厂手册', 'https://www.infineon.com/assets/row/public/documents/24/49/infineon-irlz44n-datasheet-en.pdf', '图 09：泄放管的引脚和散热器件边界。没有把晶体管额定电流当作整板连续承载能力。'),
 ('AOS AO4409 原厂手册', 'https://www.aosmd.com/sites/default/files/res/datasheets/AO4409.pdf', '图 10：1–3 脚为源极、4 脚栅极、5–8 脚漏极；串联保护管输入输出分开铺铜。'),
 ('AOS AO3401A 原厂手册', 'https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf', '图 11：按现有 1 栅、2 源、3 漏摆放辅助电源开关。')]

intro='''# 全板 PCB 布局示意图册

2026-10-04。覆盖当前九个原理图子页的 **211 个实际元件**，共 **13 张图**。先看图 00 确定整板分区，再看图 04 理顺跨页的电源链，最后按局部图移动元件组。

这是根据当前电路、真实封装和手册制作的**推荐摆放示意**。没有保存或修改主原理图、PCB、已有走线与铜区。当前 PCB 为双层板，快照有 95 段走线/过孔对象、3 个铜区对象，没有板框；因此图 00 不给定板尺寸，未声称完成整板装配、布线或散热验证。局部图的 5 mm 标尺和索引中的坐标属于各自小组，不是统一的整板绝对坐标。

## 推荐的整体摆放

1. 电池、总保险、防反接在入口处成组。入口后就近分出动力和降压两条路径，不能让大电流供电穿越基准和控制区。
2. 两块电机模块沿动力侧布置，电机接口靠模块输出。采样电阻串在供电路径，INA180 紧靠电阻；储能和陶瓷电容贴模块电源端。两路泄放靠各自母线，外置功率电阻放到板外可散热处。
3. 两条 5V 各按“降压 → 过压保护 → USB 控制器 → 插座”排成完整支路。第 08 页中的两路保护分别跟随各自输出，不集中堆在一个远端保护区。
4. 独立 3.3V 按“降压 → 过压保护 → 跳帽选择 → 辅助与传感器”摆放。默认跳帽接 1—2；可选输入不能与板载输出硬并联。磁珠和滤波位于传感器分支入口，各插座再各放去耦。
5. 电池比较、公共基准、安全逻辑和控制排针放在安静侧。U11 只有一颗，靠安全锁存并朝两轮分出控制线；编码器滤波靠对应控制排针。U30 放在两路放大电流信号的汇合处，原始差分检测线留在电阻附近。

整板区域位置、接口出线方向和各组的具体旋转是本项目的工程建议；手册通常只规定芯片周围的关键关系。连接器可随机箱约束整组旋转，不能把芯片和关键外围拆散。安装孔、线束弯曲半径、跳帽和电位器操作空间、散热片高度应在板框确定后一起校验。

## 图册目录

| 图 | 内容 | 图中实际元件数 | 打开 |
|---|---|---:|---|
'''
md=intro
for p in D['pages']:
 n=p['name'];num,title=n.split('_',1)
 md+=f'| {num} | {title} | {len(p["refs"]) or "关系图"} | [PNG]({n}.png) · [SVG]({n}.svg) |\n'
md+='''
图 01/02 中 U21、R52 是同一组共享基准，故重复显示；其余实体元件各有对应局部图。图 06 收纳了跨左右电机页的 U11 和 C127，不应另外复制。图 00/04 仅展示组合关系，不计入元件覆盖数量。

## 从原理图页定位到布局图

| 原理图 | 去看哪些图 | 摆放重点 |
|---|---|---|
| 01 输入 | 01、02、00 | 入口功率链、降压开关、共享基准、U22/U23 |
| 02 两路 5V | 03、04、10 | 每路降压与 USB 之间接入对应保护组 |
| 03 辅助 3.3V | 05、04、11 | 独立降压、保护、跳帽与传感器分配 |
| 04 安全逻辑 | 06 | 急停、复位、锁存靠近；输出朝动力侧 |
| 05 左电机 | 07、06、09、12 | U11/C127 见图 06；编码器滤波向 J1 移 |
| 06 右电机 | 08、06、09、12 | 与左路同样布局原则，保留实际针序和排距 |
| 07 回生泄放 | 09 | Q2 靠入口，Q6/Q7 各靠对应模块，U24 靠安静边界 |
| 08 电源保护 | 10、11、04 | 拆成两组 5V、一组 3.3V/预警、一组过流比较 |
| 09 控制接口 | 12、00 | 线束侧集中，采样滤波靠 J18 |

## 细化时必须保留的关系

- 降压输入陶瓷电容与芯片输入、地构成小回路；不要为了排齐元件把它们拉开。自举电容靠对应两脚；开关节点铜面积只覆盖必要连接，反馈绕开它。
- 采样电阻的载流铜与两根检测线分别引出。检测线从焊盘靠电阻体的内侧取样，避免把载流铜的压降算入电流。图里的连线用于指示端点，不是可直接照抄的最终铜线。
- 地网保持连续。动力回流局限在动力区，去耦就近下地，模拟参考避免与电机共享狭长回流路径；不要靠割裂地面制造“安静地”。
- U2/U4 使用现有自建双排排母，中心距分别为 23.0005 mm / 23.1275 mm；图中保留实际焊盘次序。它们沿用用户指定的原 PCB 间距，**并非实物尺寸认证**。模块投影下避免高元件，安装前仍需对孔。
- Q1、Q2、Q3 的 TO-220 金属背板连漏极，所在电位不同；若机械上共用导电散热片，要做电气绝缘。Q6/Q7、外置泄放电阻也要安排热路径，不靠近比较器分压和基准。
- 当前图仍保留原有 F1 保险座及所有原选型，没有替换器件，也没有增加物料。此图册不重新评定保险座采购、限流设定、过压阈值或整板可投产性。

## 核验范围

读取当前主工程网表，核对全部 211 个实体位号、封装标识及有编号焊盘的网络一致性。新增 22 个局部组使用 KiCad 原生封装几何绘图，逐条验证 140 条示意连接的两端确属同一网络，并检查各局部组封装占位包围盒无重叠。图 01/02/03 纳入此前已生成的详细图；本次对照旧网表逐项复核图中元件的数值、封装标识和每个引脚的网络与当前一致。

这项检查不等于整板 DRC、布线完成、铜宽设计、三维装配或热验证。彩线交叉不表示连接，省略的地与其余连接仍以网表为准。主文件生成前后 SHA-256 一致。

- [211 个元件的布局索引](元件布局索引.csv)：可按位号搜索，含所属原理图、推荐局部图、封装和局部组坐标。
- [机器可读绘图核验](绘图核验.json)：覆盖情况、关键连线核对、局部坐标、封装占位和源文件哈希。
- [图册总览](图册总览.png)：快速查看所有图。

## 手册依据与本项目推导

'''
for label,url,explain in SOURCES:md+=f'- [{label}]({url})：{explain}\n'
md+='\nAT8236 用的是成品双路模块，模块两排顺序依据项目内[模块资料核对](../../../../../doc/电机/AT8236模块资料核对.md)与[用户资料图](../../../../../doc/电机/合并长图_1-9.png)。该核对文档含历史问题描述，当前封装和连接以这次导出的网表与原生 PCB 为准；不把裸芯片参考板布局照搬为模块插座尺寸。\n'
(O/'布局说明.md').write_text(md,encoding='utf-8')

nav=''.join(f'<a href="#p{p["name"][:2]}">{escape(p["name"].replace("_"," · "))}</a>' for p in D['pages'])
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>电源板完整布局图册</title><style>
:root{font-family:"Microsoft YaHei",sans-serif;color:#172d45;background:#f2f6fa}*{box-sizing:border-box}body{margin:0}aside{position:fixed;width:290px;inset:0 auto 0 0;padding:25px 20px;overflow:auto;background:#172d45;color:white}aside a{display:block;color:#d6e6f4;padding:9px 3px;text-decoration:none;font-size:14px}aside a:hover{color:white;background:#294760}main{margin-left:290px;padding:32px;max-width:1840px}h1{font-size:30px}p{line-height:1.8}article,section{background:white;border:1px solid #d5e2ed;border-radius:12px;padding:22px;margin:25px 0}article img{width:100%;height:auto;display:block;border:1px solid #edf2f6}a{color:#226b9b}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left;overflow-wrap:anywhere}article{scroll-margin-top:20px}.meta{color:#61778c;font-size:14px}.links a{margin-right:20px}summary{cursor:pointer;font-size:20px} @media(max-width:900px){aside{position:static;width:auto}aside a{display:inline-block;margin-right:10px}main{margin:0;padding:14px}}@media print{aside{display:none}main{margin:0}article{break-before:page}article img{max-height:85vh;object-fit:contain}}
</style><aside><h2>电源板布局图册</h2><p>211 个实际元件<br>9 个子页 · 13 张图</p>'''+nav+'''<hr><a href="#index">按位号查找</a><a href="#sources">手册来源</a><a href="布局说明.md">完整布局说明</a><a href="元件布局索引.csv">下载元件索引</a></aside><main><h1>从整板分区到每个局部电路</h1><p>先看 00 总图和 04 跨页组合，再逐组参照真实封装图摆放。点击图片打开可放大的 SVG。原理图与 PCB 未修改；当前无板框，整板图只表达相对位置。</p><p class="meta">2026-10-04 · 顶层俯视 · 原生焊盘与脚号 · 中文说明 · 局部坐标不等于整板坐标</p>'''
for p in D['pages']:
 n=p['name'];html+=f'<article id="p{n[:2]}"><h2>{escape(n.replace("_"," · "))}</h2><p>{escape(p["summary"])}</p><p class="links"><a href="{n}.png">PNG 图片</a><a href="{n}.svg">SVG 放大查看</a></p><a href="{n}.svg"><img loading="lazy" src="{n}.png" alt="{escape(n)}"></a>'
 if p['refs']:html+=f'<p class="meta">本图位号：{escape(" · ".join(p["refs"]))}</p>'
 html+='</article>'
html+='<section id="index"><details><summary>按位号查找：211 个元件（展开后 Ctrl+F 搜索）</summary><table><tr><th>位号</th><th>型号 / 值</th><th>原理图页</th><th>布局图</th></tr>'
for r in sorted(D['coverage']):
 links='、'.join(f'<a href="#p{n[:2]}">{n[:2]}</a>' for n in D['coverage'][r]);sh='/'.join(s[:2] for s,rs in A['sheets'].items() if r in rs)
 html+=f'<tr><td>{escape(r)}</td><td>{escape(A["parts"][r]["value"])}</td><td>{sh}</td><td>{links}</td></tr>'
html+='</table></details></section><section id="sources"><h2>手册来源与推导边界</h2><p>芯片周围的关键布局先按原厂手册，整板分区与具体方向按本项目连接关系安排；完整边界见布局说明。</p><ul>'
for label,url,explain in SOURCES:html+=f'<li><p><a href="{escape(url)}">{escape(label)}</a><br>{escape(explain)}</p></li>'
html+='</ul></section></main></html>'
(O/'图册索引.html').write_text(html,encoding='utf-8')
for p in D['pages']:
 for ext in ['svg','png']:assert (O/(p['name']+'.'+ext)).is_file()
for file,digest in D['source_hashes_before'].items():assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==digest,file
print('Atlas ready: 13 diagrams, 211 unique refs, all image links exist, source hashes unchanged.')
