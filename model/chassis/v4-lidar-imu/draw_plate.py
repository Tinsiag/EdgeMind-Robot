"""Dimensioned plan of the real third-deck features (all dimensions in mm)."""
from pathlib import Path
import json,html
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'verification.json').read_text(encoding='utf-8'));p=r['parameters']
s=['''<svg xmlns="http://www.w3.org/2000/svg" width="1260" height="1140" viewBox="-125 -190 420 380">
<defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto-start-reverse"><path d="M0 0L6 3L0 6" fill="none" stroke="#38536a"/></marker></defs>
<rect x="-125" y="-190" width="420" height="380" fill="#f8fafc"/>
<g font-family="Microsoft YaHei,Arial,sans-serif" fill="#203348"><text x="-105" y="-176" font-size="8" font-weight="700">EdgeMind V4 · 第三层传感器板</text>
<text x="-105" y="-164" font-size="4.5">单位 mm　·　板厚 5　·　俯视　·　车头朝上　·　2026-10-20</text>
<path d="M0 -139V-153" stroke="#38536a" stroke-width=".7" marker-end="url(#arrow)"/><text x="6" y="-145" font-size="5">车头</text>
<polygon points="-70,-130 70,-130 90,-110 90,118 78,130 -78,130 -90,118 -90,-110" fill="#e2e9ee" stroke="#263e52" stroke-width=".7"/>
''']
def circle(x,y,rad,stroke='#263e52',fill='white'):
    s.append(f'<circle cx="{x}" cy="{y}" r="{rad}" fill="{fill}" stroke="{stroke}" stroke-width=".35"/>')
def rect(x,y,w,l,rad,stroke='#8192a0',fill='white',extra=''):
    s.append(f'<rect x="{x-w/2}" y="{y-l/2}" width="{w}" height="{l}" rx="{rad}" fill="{fill}" stroke="{stroke}" stroke-width=".35" {extra}/>')
for v in r['vent_slots']:rect(*v)
for v in r['wire_slots']:rect(*v,stroke='#ad6c23')
for x,y in p['third_support_holes_xy']:circle(x,y,1.7)
for x,y in r['lidar']['mount_holes_xy']:circle(x,y,1.15,'#267b77')
for x,y in r['perfboard']['mount_holes_xy']:circle(x,y,1.4,'#8a5b98')
for x,y in r['imu']['mount_holes_xy_reference']:rect(x,y,3,4.5,1.5,stroke='#2868a5')
rect(*p['lidar_center_xy'],38.59,38.59,5,stroke='#267b77',fill='none',extra='stroke-dasharray="1.5 1"')
circle(*p['lidar_center_xy'],17.645,stroke='#267b77',fill='none')
rect(*p['imu_center_xy'],*p['imu_board_size_xy'],0,stroke='#2868a5',fill='none',extra='stroke-dasharray="1.2 1"')
hx=r['imu']['header_x'];iy=p['imu_center_xy'][1]
rect(hx,iy,2.54,20.32,.3,stroke='#2868a5',fill='#90b5d7')
rect(*p['perfboard_center_xy'],*r['perfboard']['source_size_mm'][:2],3,stroke='#8a5b98',fill='none',extra='stroke-dasharray="1.5 1"')
s.append('<text x="0" y="-35" text-anchor="middle" font-size="5" fill="#8a5b98">洞洞板 90.23 × 69.97</text>')
s.append('''<path d="M73 -107L86 -100" stroke="#2868a5" marker-end="url(#arrow)"/><text x="55" y="-109" font-size="4.5" fill="#2868a5">孔朝外</text>
<path d="M-90 138V151M90 138V151M-90 146H90" fill="none" stroke="#38536a" stroke-width=".35"/>
<path d="M-89 146H89" stroke="#38536a" stroke-width=".35" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="0" y="144" text-anchor="middle" font-size="4.5">180</text>
<path d="M96 -130H108M96 130H108M103 -130V130" fill="none" stroke="#38536a" stroke-width=".35"/>
<path d="M103 -129V129" stroke="#38536a" stroke-width=".35" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="101" y="0" transform="rotate(-90 101 0)" text-anchor="middle" font-size="4.5">260</text>
<path d="M-5 0H5M0 -5V5" stroke="#7a8c9c" stroke-width=".3"/><text x="6" y="4" font-size="3.5">原点</text>
''')
lines=[('布置',''),('LD06','中心 (0, -104)，正前中央'),('MPU6050','+X侧边距2，双孔朝外、排针朝内'),('洞洞板','中心 (0, -37)，位于雷达后方'),('支撑与开孔',''),('4 × M3支柱孔','φ3.4；沿用原四角支撑轴线'),('2 × 雷达隔柱孔','φ2.3；对角横纵间距 28.20'),('2 × MPU安装槽','3.0 × 4.5；名义孔距 15.24'),('4 × 洞洞板安装孔','φ2.8；位置取自用户 STEP'),('10 × 过线孔','原2处 + 两侧6处10×24 + 后部2处16×8'),('装配高度',''),('第三层支柱','45；下端 M3 螺柱另长 8'),('第三层底 / 顶','Z = 153.781 / 158.781'),('摄像头支架净空','3.00'),('洞洞板隔柱','8；与雷达外壳间隙约 12.72'),('资料边界',''),('MPU 孔距未标注','15.24 孔距与 2.54 边距为估算'),('加工前复核','MPU 实物孔位、隔柱与螺钉长度')]
y=-126
for title,body in lines:
    if not body:
        s.append(f'<text x="121" y="{y}" font-size="5.3" font-weight="700">{html.escape(title)}</text>');y+=10
    else:
        s.append(f'<text x="121" y="{y}" font-size="4.2" font-weight="600">{html.escape(title)}</text>')
        s.append(f'<text x="121" y="{y+6}" font-size="3.8" fill="#5d7182">{html.escape(body)}</text>');y+=17
s.append('<text x="-105" y="174" font-size="4" fill="#5d7182">虚线为器件安装轮廓。STEP 为精确几何；MPU 参考孔距须实物确认后加工。</text></g></svg>')
(HERE/'ThirdDeck-drawing.svg').write_text(''.join(s),encoding='utf-8')
print('ThirdDeck-drawing.svg written')
