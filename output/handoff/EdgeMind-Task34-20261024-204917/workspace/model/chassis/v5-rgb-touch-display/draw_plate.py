"""Portrait screen and shifted board installation plan, real mm coordinates."""
from pathlib import Path
import json,html
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'verification.json').read_text(encoding='utf-8'));p=r['parameters']
s=['''<svg xmlns="http://www.w3.org/2000/svg" width="1380" height="1140" viewBox="-125 -190 460 380"><defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto-start-reverse"><path d="M0 0L6 3L0 6" fill="none" stroke="#38536a"/></marker></defs><rect x="-125" y="-190" width="460" height="380" fill="#f8fafc"/><g font-family="Microsoft YaHei,Arial,sans-serif" fill="#203348"><text x="-105" y="-176" font-size="8" font-weight="700">EdgeMind V5 · 4.3寸RGB触摸屏试摆</text><text x="-105" y="-164" font-size="4.5">单位 mm · 第三层5mm · 俯视 · 车头朝上 · 2026-10-21</text><path d="M0 -139V-153" stroke="#38536a" stroke-width=".7" marker-end="url(#arrow)"/><text x="6" y="-145" font-size="5">车头</text><polygon points="-70,-130 70,-130 90,-110 90,118 78,130 -78,130 -90,118 -90,-110" fill="#e2e9ee" stroke="#263e52" stroke-width=".7"/>''']
def rect(x,y,w,l,rad,fill='white',stroke='#8192a0',extra=''):
    s.append(f'<rect x="{x-w/2}" y="{y-l/2}" width="{w}" height="{l}" rx="{rad}" fill="{fill}" stroke="{stroke}" stroke-width=".35" {extra}/>')
def circle(x,y,rad,stroke='#263e52'):
    s.append(f'<circle cx="{x}" cy="{y}" r="{rad}" fill="white" stroke="{stroke}" stroke-width=".35"/>')
for a in r['vent_slots']:rect(*a)
for a in r['wire_slots']:rect(*a,stroke='#ad6c23')
for x,y in p['third_support_holes_xy']:circle(x,y,1.7)
for x,y in r['lidar']['mount_holes_xy']:circle(x,y,1.15,'#267b77')
for x,y in r['imu']['mount_holes_xy_reference']:rect(x,y,3,4.5,1.5,stroke='#2868a5')
for x,y in r['perfboard']['mount_holes_xy']:circle(x,y,1.4,'#7c5290')
for x,y in r['screen']['module_mount_holes_xy_reference']:rect(x,y,4,8,2,stroke='#b36824')
rect(*p['lidar_center_xy'],38.59,38.59,5,'none','#267b77','stroke-dasharray="1.2 1"')
circle(*p['lidar_center_xy'],17.645,'#267b77')
rect(*p['imu_center_xy'],*p['imu_board_size_xy'],0,'none','#2868a5','stroke-dasharray="1.2 1"')
rect(r['imu']['header_x'],p['imu_center_xy'][1],2.54,20.32,.3,'#8eb4d7','#2868a5')
rect(*p['screen_center_xy'],*p['screen_pcb_size_xy_reference'],1,'#f6e9da','#b36824','fill-opacity=".72" stroke-dasharray="1.5 1"')
rect(*p['screen_center_xy'],*p['screen_lcd_size_xy_from_pdf'],1,'none','#657781')
rect(*p['screen_center_xy'],*p['screen_active_area_xy_from_pdf'],.5,'#d1e4ed','#526c7a','fill-opacity=".85"')
sx,sy=p['screen_center_xy']
s.append(f'<text x="{sx}" y="{sy-3}" text-anchor="middle" font-size="5" fill="#244b60">4.3寸竖屏</text><text x="{sx}" y="{sy+5}" text-anchor="middle" font-size="3.5" fill="#244b60">正面向上 · 平放</text>')
rect(*p['perfboard_center_xy'],*r['perfboard']['assembly_size_xy_mm'],3,'none','#7c5290','stroke-dasharray="1.5 1"')
cx,cy=p['perfboard_center_xy']
s.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" font-size="5" fill="#7c5290">洞洞板</text><text x="{cx}" y="{cy+7}" text-anchor="middle" font-size="3.5" fill="#7c5290">右移 · 平面内90°</text>')
s.append('''<path d="M-90 138V151M90 138V151M-90 146H90" fill="none" stroke="#38536a" stroke-width=".35"/><path d="M-89 146H89" stroke="#38536a" stroke-width=".35" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="0" y="144" text-anchor="middle" font-size="4.5">180</text><path d="M96 -130H108M96 130H108M103 -130V130" fill="none" stroke="#38536a" stroke-width=".35"/><path d="M103 -129V129" stroke="#38536a" stroke-width=".35" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="101" y="0" transform="rotate(-90 101 0)" text-anchor="middle" font-size="4.5">260</text>''')
lines=[('布局',''),('屏幕','中心(-54.4,-50)，图中红框侧竖屏平放'),('洞洞板','中心(+37,-20)，右移且板面内旋转90°'),('模块参考尺寸','116长 × 67.2宽；图示宽67加0.2留量'),('裸屏厂家尺寸','105.5 × 67.2 × 4.05（含触摸层）'),('安装',''),('屏幕参考孔距','112 × 56，整模块孔距未获正式机械图'),('屏幕安装槽','4处 4×8；四只12高M3参考隔柱'),('屏幕后方接口窗','30×12 / R2，位于背面接口下方'),('洞洞板安装孔','按原STEP孔轴作90°刚性变换'),('净空',''),('屏幕 / 雷达','最近约1.71；低于扫描区约9.25'),('屏幕 / 洞洞板','最近约22.94'),('背面接口 / 第三层','预留3，接口高度按9参考'),('资料边界',''),('以下尺寸需实测','整模块四孔距、PCB厚度、背面接口高度'),('加工前复核','当前为试摆模型，屏幕固定孔尚属参考')]
y=-126
for title,body in lines:
    if not body:s.append(f'<text x="121" y="{y}" font-size="5.3" font-weight="700">{html.escape(title)}</text>');y+=10
    else:
        s.append(f'<text x="121" y="{y}" font-size="4.2" font-weight="600">{html.escape(title)}</text><text x="121" y="{y+6}" font-size="3.8" fill="#5d7182">{html.escape(body)}</text>');y+=17
s.append('<text x="-105" y="174" font-size="4" fill="#5d7182">屏幕孔距与背面高度属安装参考。裸屏机械图不能替代完整模块PCB机械图。</text></g></svg>')
(HERE/'ThirdDeck-drawing.svg').write_text(''.join(s),encoding='utf-8')
print('V5 layout drawing generated',flush=True)
