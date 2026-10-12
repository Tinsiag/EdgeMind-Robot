"""Build the EdgeMind concept chassis using the installed FreeCAD Python.

Run: D:/FreeCAD 1.1/bin/python.exe model/chassis/build_chassis.py
All dimensions are in mm. Only this directory receives generated files.
"""
from pathlib import Path
import json
import math
import hashlib
import zipfile
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part
import MeshPart

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = json.loads((HERE / 'parameters.json').read_text(encoding='utf-8'))
OUT = HERE / 'v1-fixed-front-wheels'
OUT.mkdir(exist_ok=True)
(OUT / 'parts-stl').mkdir(exist_ok=True)
(OUT / 'parts-step').mkdir(exist_ok=True)
V = App.Vector
doc = App.newDocument('EdgeMindChassis')
groups = {}
items = []
shapes = {}
COLORS = {'shell': (0.10, 0.13, 0.16), 'silver': (0.62, 0.67, 0.72),
          'gold': (0.86, 0.57, 0.13), 'rubber': (0.10, 0.105, 0.115),
          'hub': (0.24, 0.27, 0.30), 'board': (0.04, 0.32, 0.55),
          'blackboard': (0.10, 0.13, 0.14), 'battery': (0.35, 0.37, 0.39)}

def log(message):
    print(message, flush=True)

def group(name, label):
    g = doc.addObject('App::DocumentObjectGroup', name)
    g.Label = label
    groups[name] = g
    return g

group('Shell', '01 外壳与托盘')
group('Mounts', '02 支柱与轮座')
group('Wheels', '03 四轮与轴承')
group('Hardware', '04 硬件装配参考')
group('Fasteners', '05 紧固件参考')

def add(name, label, shape, color='shell', category='Shell', export_part=False, role='designed'):
    if shape.isNull() or not shape.isValid() or not shape.Solids or shape.Volume <= 0:
        raise RuntimeError(f'Invalid solid: {name}')
    obj = doc.addObject('Part::Feature', name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty('App::PropertyString', 'DesignRole', 'Design').DesignRole = role
    obj.addProperty('App::PropertyString', 'DimensionUnit', 'Design').DimensionUnit = 'mm'
    obj.addProperty('App::PropertyString', 'ParameterSource', 'Design').ParameterSource = '../parameters.json'
    groups[category].addObject(obj)
    rgb = COLORS[color] if isinstance(color, str) else color
    if obj.ViewObject:
        obj.ViewObject.ShapeColor = rgb
        obj.ViewObject.LineColor = (0.15, 0.17, 0.20)
    entry = {'name': name, 'label': label, 'object': obj, 'color': rgb,
             'category': category, 'export_part': export_part, 'role': role}
    items.append(entry)
    shapes[name] = shape
    return obj

def polygon(points, z, height):
    vertices = [V(x, y, z) for x, y in points]
    return Part.Face(Part.makePolygon(vertices + [vertices[0]])).extrude(V(0, 0, height))

def box(x, y, z, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x, y, z))

def cyl(radius, length, center, axis=(0, 0, 1)):
    return Part.makeCylinder(radius, length, V(*center), V(*axis))

def combine(parts):
    result = parts[0]
    for part in parts[1:]:
        result = result.fuse(part)
    return result.removeSplitter()

def cuts(shape, tools):
    if tools:
        shape = shape.cut(Part.makeCompound(tools))
    return shape.removeSplitter()

def slot(a, b, radius, z, height):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-8:
        return cyl(radius, height, (a[0], a[1], z))
    nx, ny = -dy / length * radius, dx / length * radius
    mid = polygon([(a[0]+nx, a[1]+ny), (b[0]+nx, b[1]+ny),
                   (b[0]-nx, b[1]-ny), (a[0]-nx, a[1]-ny)], z, height)
    return combine([mid, cyl(radius, height, (*a, z)), cyl(radius, height, (*b, z))])

def ring(outer, inner, length, center, axis=(0, 0, 1)):
    return cyl(outer, length, center, axis).cut(cyl(inner, length, center, axis))

def hex_prism(radius, z, height, x=0, y=0):
    return polygon([(x + radius*math.cos(k*math.pi/3), y + radius*math.sin(k*math.pi/3))
                    for k in range(6)], z, height)

T = P['plate_thickness']
LOW = P['lower_deck_bottom_z']
TOP = P['upper_deck_bottom_z']
BOARD = P['board_datum_z']
W = P['body_width'] / 2
L = P['body_length'] / 2
AXLEZ = P['wheel_diameter'] / 2
post_xy = [(-76, -111), (76, -111), (-76, 114), (76, 114)]
profile = [(-W+20, -L), (W-20, -L), (W, -L+20), (W, L-12),
           (W-12, L), (-W+12, L), (-W, L-12), (-W, -L+20)]

log('Read supplied power PCB and motor STEP geometry')
power_path = ROOT / 'model/hardware/3D_PCB1_2026-10-12.step'
motor_path = ROOT / 'model/hardware/直流电机-MG513X（霍尔编码器）/直流电机-MG513X（霍尔编码器）.stp'
power = Part.read(str(power_path))
motor = Part.read(str(motor_path))
assert power.isValid() and motor.isValid()
pcb_solid = max(power.Solids, key=lambda s: s.BoundBox.XLength*s.BoundBox.YLength
                if s.BoundBox.ZLength < 2 else 0)
power_holes = sorted({(round(f.Surface.Center.x, 4), round(f.Surface.Center.y, 4), round(f.Surface.Radius, 4))
                      for f in pcb_solid.Faces if isinstance(f.Surface, Part.Cylinder)
                      and abs(f.Surface.Axis.z) > .999 and 1.3 <= f.Surface.Radius <= 2.1})
power_translation = V(-49.992, -65.0, 29.0)
power_mount_xy = [(x + power_translation.x, y + power_translation.y)
                  for x, y, r in power_holes]

log('Build lower tray, battery cradle, removable upper deck and vents')
base = polygon(profile, LOW, T)
base_tools = [cyl(1.7, T+2, (x, y, LOW-1)) for x, y in post_xy]
base_tools += [cyl(1.7, T+2, (x, y, LOW-1)) for x, y in power_mount_xy]
base_tools += [cyl(1.7, T+2, (x, y, LOW-1)) for x in (-25, 25) for y in (-35, 35)]
for x in (-60, 60):
    for y in (-20, 8):
        base_tools.append(slot((x-10, y), (x+10, y), 2, LOW-1, T+2))
for side in (-1, 1):
    for yy in (P['front_axle_y']-7, P['front_axle_y']+7, 34.65, 84.65):
        base_tools.append(cyl(1.7, T+2, (side*78, yy, LOW-1)))
base = cuts(base, base_tools)
add('LowerDeck', '下层底板 260×180×3', base, export_part=True)

upper = polygon(profile, TOP, T)
upper_tools = [cyl(1.7, T+2, (x, y, TOP-1)) for x, y in post_xy]
fpga_mounts = [(x, P['fpga_centre_y']+y) for x in (-66.2305, 66.2305) for y in (-42.9895, 42.9895)]
lichee_mounts = [(x, P['lichee_centre_y']+y) for x in (-38.2, 38.2) for y in (-44, 44)]
for x, y in fpga_mounts + lichee_mounts:
    upper_tools.append(slot((x, y-3), (x, y+3), 1.7, TOP-1, T+2))
for side in (-1, 1):
    for yy in (10, 20, 30, 40, 50, 60, 70):
        upper_tools.append(slot((side*60, yy), (side*75, yy), 1.6, TOP-1, T+2))
upper_tools += [slot((-23, -5), (23, -5), 3, TOP-1, T+2)]
upper = cuts(upper, upper_tools)
add('UpperDeck', '上层可拆托盘 Z64 / 板卡 Z76', upper, export_part=True)

# Side panels start after the front chamfer. Slots run along the case, not across wheel hubs.
for side, suffix in [(-1, 'L'), (1, 'R')]:
    panel = box(-90 if side < 0 else 87, -105, LOW+T, 3, 216, 22)
    tools = []
    for yy, length in [(-75, 43), (-15, 42), (37, 22)]:
        for zz in (28, 36):
            tools.append(box(-91, yy, zz, 182, length, 3.2))
    tools += [cyl(4.25, 182, (-91, P['front_axle_y'], AXLEZ), (1,0,0)),
              cyl(6.5, 182, (-91, P['rear_axle_y'], AXLEZ), (1,0,0))]
    panel = cuts(panel, tools)
    add('SidePanel'+suffix, '侧护板'+('左' if side < 0 else '右'), panel, export_part=True)
    rail = box(-92.5 if side < 0 else 90, -107, 44, 2.5, 211, 12)
    rail = cuts(rail, [cyl(6.5, 188, (-94, P['rear_axle_y'], AXLEZ), (1,0,0)),
                       cyl(4.25, 188, (-94, P['front_axle_y'], AXLEZ), (1,0,0))])
    add('SideRail'+suffix, '银色侧护边'+suffix, rail, 'silver', export_part=True)
    accent = box(-93.3 if side < 0 else 92.5, -102, 52, .8, 201, 2)
    add('Accent'+suffix, '侧边琥珀装饰条'+suffix, accent, 'gold', role='decorative')

front = box(-68, -130, 21, 136, 3, 23)
front = cuts(front, [box(-46, -131, z, 92, 5, 3) for z in (27, 34)])
add('FrontBumper', '前通风护板', front, export_part=True)
for side, suffix in [(-1, 'L'), (1, 'R')]:
    cheek = polygon([(side*68, -130), (side*70, -130), (side*90, -110), (side*88, -108)], 21, 23)
    add('FrontCheek'+suffix, '前倒角护板'+suffix, cheek, export_part=True)
rear = cuts(box(-75, 127, 21, 150, 3, 26), [box(-30, 126, 29, 60, 5, 10)])
add('RearBumper', '后护板与线束出口', rear, export_part=True)

cradle = box(-21.5, -58, 21, 43, 116, 11).cut(box(-19, -55.5, 24, 38, 111, 12))
cradle = combine([cradle] + [box(x-6, y-6, 21, 12, 12, 3) for x in (-25, 25) for y in (-35, 35)])
cradle = cuts(cradle, [cyl(1.7, 14, (x, y, 20)) for x in (-25, 25) for y in (-35, 35)])
add('BatteryCradle', '电池托架 内腔38×111', cradle, 'silver', export_part=True)

log('Build standoffs and actual motor flange mounting holes')
for i, (x, y) in enumerate(post_xy, 1):
    stand = ring(4.5, 1.65, TOP-(LOW+T), (x, y, LOW+T))
    add('MainPost'+str(i), '上下层支柱'+str(i), stand, 'gold', 'Mounts')
for i, (x, y) in enumerate(fpga_mounts + lichee_mounts, 1):
    stand = ring(3, 1.65, BOARD-TOP-T, (x, y, TOP+T))
    add('BoardPost'+str(i), '板卡支柱参考'+str(i), stand, 'gold', 'Mounts', role='mount_reference')
for i, (x, y) in enumerate(power_mount_xy, 1):
    add('PowerPost'+str(i), '现板孔位支柱'+str(i), ring(3, 1.6, 8, (x, y, 21)), 'gold', 'Mounts')

for side, suffix in [(-1, 'L'), (1, 'R')]:
    # Stock MG513X output axis: original +Y at X=-19.35, Z=0.
    m = motor.copy()
    if side > 0:
        m.rotate(V(0,0,0), V(0,0,1), -90)
    else:
        m.rotate(V(0,0,0), V(0,0,1), 90)
        m.rotate(V(0,0,0), V(1,0,0), 180)
    m.translate(V(side*86, P['rear_axle_y']-19.35, AXLEZ))
    add('Motor'+suffix, 'MG513X 原STEP '+suffix, m, 'silver', 'Hardware', role='source_geometry')
    plate = box(86 if side > 0 else -89, 26.65, 21, 3, 68, 39)
    foot = box(70 if side > 0 else -89, 26.65, LOW, 19, 68, T)
    bracket = combine([plate, foot])
    for yy in (35.65, 85.65):
        for zz in (AXLEZ-13.25, AXLEZ+13.25):
            bracket = bracket.cut(cyl(1.7, 5, (85 if side > 0 else -90, yy, zz), (1,0,0)))
    bracket = bracket.cut(cyl(6.5, 5, (85 if side > 0 else -90, P['rear_axle_y'], AXLEZ), (1,0,0)))
    for yy in (34.65, 84.65):
        bracket = bracket.cut(cyl(1.7, 5, (side*78, yy, LOW-1)))
    add('MotorBracket'+suffix, '后电机安装座'+suffix, bracket.removeSplitter(), 'silver', 'Mounts', True)

    # A fixed front bearing axle support. The upright retains only the needed wheel-end material.
    fy = P['front_axle_y']
    front_plate = box(86 if side > 0 else -89, fy-11, 21, 3, 22, 29)
    front_foot = box(70 if side > 0 else -89, fy-11, LOW, 19, 22, T)
    axle_bracket = combine([front_plate, front_foot])
    axle_bracket = axle_bracket.cut(cyl(4.25, 5, (85 if side > 0 else -90, fy, AXLEZ), (1,0,0)))
    axle_bracket = cuts(axle_bracket, [cyl(1.7, 5, (side*78, fy+dy, LOW-1)) for dy in (-7,7)])
    add('FrontAxleBracket'+suffix, '前从动轮固定轴座'+suffix, axle_bracket, 'silver', 'Mounts', True)

log('Build four equal 80 mm wheels; two front wheels use independent bearings')
for side, suffix in [(-1, 'L'), (1, 'R')]:
    axis = (side,0,0)
    wheel_x = side*(P['wheel_centre_x']-P['wheel_width']/2)
    for front_wheel, yy in [(True,P['front_axle_y']), (False,P['rear_axle_y'])]:
        prefix = ('Front' if front_wheel else 'Rear')+suffix
        width = P['wheel_width']
        tyre = ring(P['wheel_diameter']/2, 31, width, (wheel_x, yy, AXLEZ), axis)
        # Recessed circumferential channels, modest tread strips.
        for offset in (4.5, 9, 13.5):
            tyre = tyre.cut(ring(41, 39.3, .65, (wheel_x+side*offset, yy, AXLEZ), axis))
        add(prefix+'Tyre', ('前从动轮胎' if front_wheel else '后驱动轮胎')+suffix, tyre, 'rubber', 'Wheels', role='wheel_reference')
        bore = 11 if front_wheel else 3.1
        hub = ring(31, bore, width-2, (wheel_x+side, yy, AXLEZ), axis)
        hub = combine([hub, ring(15, bore, width+4, (wheel_x-side*2, yy, AXLEZ), axis)])
        # Small vent holes in the central disc, independent of bearing seats.
        for k in range(6):
            a = k*math.pi/3
            hub = hub.cut(cyl(3, width+6, (wheel_x-side*3, yy+22*math.cos(a), AXLEZ+22*math.sin(a)), axis))
        add(prefix+'Hub', ('前轴承轮毂' if front_wheel else '后驱轮毂参考')+suffix, hub.removeSplitter(), 'hub', 'Wheels', role='wheel_reference')
        if front_wheel:
            for idx, offset in enumerate((-1, width-6),1):
                bearing = ring(11, 4, 7, (wheel_x+side*offset, yy, AXLEZ), axis)
                add(prefix+'Bearing'+str(idx), '前轮轴承包络'+suffix+str(idx), bearing, 'silver', 'Wheels', role='bearing_reference')
            axle = cyl(4, 32, (side*85, yy, AXLEZ), axis)
            add(prefix+'Axle', '前轮8mm独立轮轴'+suffix, axle, 'silver', 'Wheels', role='axle_reference')
        else:
            coupling = ring(6,3.1,15, (side*87.5, yy, AXLEZ), axis)
            add(prefix+'Coupling', '后轮6mm轴适配包络'+suffix, coupling, 'silver', 'Wheels', role='coupling_reference')

log('Add hardware placement references')
power.translate(power_translation)
for idx, solid in enumerate(power.Solids):
    b = solid.BoundBox
    color = 'board' if b.XLength > 95 and b.YLength > 45 and b.ZLength < 2 else ('hub' if b.ZLength < 2 else 'silver')
    add('PowerComponent'+str(idx), '现有电源板 STEP '+str(idx), solid, color, 'Hardware', role='source_geometry')

bat = box(-P['battery_width']/2, -P['battery_length']/2, 24,
          P['battery_width'], P['battery_length'], P['battery_height'])
add('Battery', '电池105×33×25包络', bat, 'battery', 'Hardware', role='envelope_reference')
for i, yy in enumerate((-29, 29),1):
    strap = combine([box(-19,yy-6,48.8,38,12,1.3), box(-19,yy-6,24,1.4,12,26), box(17.6,yy-6,24,1.4,12,26)])
    add('BatteryStrap'+str(i), '电池绑带包络'+str(i), strap, 'rubber', 'Hardware', role='envelope_reference')

fy = P['fpga_centre_y']
fpga = box(-P['fpga_width']/2, fy-P['fpga_length']/2, BOARD,
           P['fpga_width'], P['fpga_length'], 1.6)
fpga = cuts(fpga, [cyl(1.6,3.6,(x,y,BOARD-1)) for x,y in fpga_mounts])
add('FPGAReference', 'FPGA V3 板面参考138.049×91.567', fpga, 'board', 'Hardware', role='envelope_reference')
for i, (x,y,w,l) in enumerate([(-20,fy,18,20),(6,fy+3,21,18),(49,fy+31,14,12)],1):
    add('FPGAChip'+str(i), 'FPGA器件高度参考'+str(i), box(x,y,BOARD+1.6,w,l,3.2), 'rubber', 'Hardware', role='envelope_reference')
for i, yy in enumerate((fy-32,fy-7),1):
    add('FPGAConnector'+str(i), 'FPGA连接器参考'+str(i),box(-69,yy,BOARD+1.6,17,15,9), 'silver','Hardware',role='envelope_reference')

ly = P['lichee_centre_y']
lp_board = box(-P['lichee_width']/2, ly-P['lichee_length']/2, BOARD, P['lichee_width'],P['lichee_length'],1.6)
lp_board = cuts(lp_board, [cyl(1.6,3.6,(x,y,BOARD-1)) for x,y in lichee_mounts])
add('LPi4AReference', 'LPi4A 包络参考84.455×103.814', lp_board, 'blackboard','Hardware',role='envelope_reference')
add('LPi4ACore', 'LPi4A核心板参考',box(-30,ly-23,BOARD+4,60,57,3.8),'blackboard','Hardware',role='envelope_reference')
for i,xx in enumerate((-39,-19.5,1,21),1):
    add('LPi4AConnector'+str(i), 'LPi4A接口高度参考'+str(i),box(xx,ly+33,BOARD+1.6,18,18.5,P['lichee_height']-1.6), 'silver','Hardware',role='envelope_reference')
for i,(x,y) in enumerate(post_xy,1):
    screw = combine([cyl(1.5,6,(x,y,TOP-3)),cyl(2.8,1.8,(x,y,TOP+T))])
    add('UpperScrew'+str(i), '上盖M3螺钉参考'+str(i),screw,'silver','Fasteners',role='fastener_reference')

doc.recompute()
log('Check solid validity and key clearances')
check = {'units':'mm','parameters':P,'parts':[], 'power_pcb_holes_from_step':power_holes,
         'critical_interferences':[], 'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (power_path,motor_path)}}
for item in items:
    obj = item['object']
    b = obj.Shape.BoundBox
    check['parts'].append({'name':item['name'],'label':item['label'],'category':item['category'],
                           'role':item['role'],'valid':obj.Shape.isValid(),'solids':len(obj.Shape.Solids),
                           'volume_mm3':obj.Shape.Volume,'bounds':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]})

# Intersections of load-bearing shell parts and hardware/wheels must not hide collisions.
designed = [i for i in items if i['category'] in ('Shell','Mounts') and i['role']=='designed']
refs = [i for i in items if i['name'] in ('MotorL','MotorR','Battery','FPGAReference','LPi4AReference')
        or i['name'].endswith(('Tyre','Axle','Coupling'))]
for a in designed:
    for b in refs:
        sa,sb=a['object'].Shape,b['object'].Shape
        if sa.BoundBox.intersect(sb.BoundBox):
            volume=sa.common(sb).Volume
            if volume > .02:
                check['critical_interferences'].append({'a':a['name'],'b':b['name'],'volume_mm3':volume})
all_shape=Part.makeCompound([i['object'].Shape for i in items])
b=all_shape.BoundBox
check['assembly_bounds_mm']=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
check['assembly_size_mm']=[b.XLength,b.YLength,b.ZLength]
check['four_wheel_ground_z']=[shapes[n].BoundBox.ZMin for n in ('FrontLTyre','FrontRTyre','RearLTyre','RearRTyre')]
assert max(abs(z) for z in check['four_wheel_ground_z']) < 1e-6
(OUT/'verification.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
if check['critical_interferences']:
    raise RuntimeError('Resolve collisions before exporting: '+json.dumps(check['critical_interferences']))

log('Export FCStd, shell STEP, assembly STEP and separate STL / STEP parts')
fcstd=OUT/'EdgeMind_Chassis.FCStd'
doc.saveAs(str(fcstd))
shell_objects=[i['object'] for i in items if i['category'] in ('Shell','Mounts') and i['role']=='designed']
Part.export(shell_objects, str(OUT/'EdgeMind_Shell.step'))
Part.export([i['object'] for i in items], str(OUT/'EdgeMind_Assembly.step'))
for item in items:
    if item['export_part']:
        mesh=MeshPart.meshFromShape(Shape=item['object'].Shape,LinearDeflection=.12,AngularDeflection=.20,Relative=False)
        if not mesh.isSolid():
            raise RuntimeError('Non-closed STL mesh: '+item['name'])
        mesh.write(str(OUT/'parts-stl'/f"{item['name']}.stl"))
        Part.export([item['object']], str(OUT/'parts-step'/f"{item['name']}.step"))

# Add standard view provider colors to a headless FreeCAD document.
gui=ET.Element('Document',{'SchemaVersion':'1','HasExpansion':'1'})
providers=ET.SubElement(gui,'ViewProviderData',{'Count':str(len(items))})
for item in items:
    provider=ET.SubElement(providers,'ViewProvider',{'name':item['name'],'expanded':'0'})
    props=ET.SubElement(provider,'Properties',{'Count':'4'})
    for name,typ,val in [('ShapeColor','App::PropertyColor',item['color']),
                         ('LineColor','App::PropertyColor',(.13,.15,.17)),
                         ('Visibility','App::PropertyBool',True),
                         ('DisplayMode','App::PropertyEnumeration','Flat Lines')]:
        prop=ET.SubElement(props,'Property',{'name':name,'type':typ})
        if typ=='App::PropertyColor':
            packed=(round(val[0]*255)<<24)|(round(val[1]*255)<<16)|(round(val[2]*255)<<8)|255
            ET.SubElement(prop,'PropertyColor',{'value':str(packed)})
        elif typ=='App::PropertyBool':
            ET.SubElement(prop,'Bool',{'value':'true'})
        else:
            ET.SubElement(prop,'Integer',{'value':'0'})
gui_data=ET.tostring(gui,encoding='utf-8',xml_declaration=True)
patched=fcstd.with_suffix('.styled.FCStd')
with zipfile.ZipFile(fcstd) as z,zipfile.ZipFile(patched,'w',zipfile.ZIP_DEFLATED) as dest:
    for info in z.infolist():
        if info.filename!='GuiDocument.xml':dest.writestr(info,z.read(info.filename))
    dest.writestr('GuiDocument.xml',gui_data)
patched.replace(fcstd)

log('Create lightweight meshes for offline 3D preview')
mesh_data=[]
for item in items:
    verts,faces=item['object'].Shape.tessellate(.45)
    mesh_data.append({'name':item['name'],'label':item['label'],'category':item['category'],
                      'color':item['color'],'vertices':[[round(v.x,4),round(v.y,4),round(v.z,4)] for v in verts],
                      'indices':[list(f) for f in faces]})
(OUT/'preview-meshes.json').write_text(json.dumps(mesh_data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

log('Re-open exported STEP and native CAD and verify sizes')
for filename,original in [('EdgeMind_Shell.step',Part.makeCompound([o.Shape for o in shell_objects])),
                          ('EdgeMind_Assembly.step',all_shape)]:
    exported=Part.read(str(OUT/filename))
    assert exported.isValid() and len(exported.Solids)==len(original.Solids),filename
    # Use exact B-rep bounds; tessellation can change the default cached bounding box.
    eb,ob=exported.optimalBoundingBox(False,False),original.optimalBoundingBox(False,False)
    assert max(abs(a-b) for a,b in zip([eb.XMin,eb.YMin,eb.ZMin,eb.XMax,eb.YMax,eb.ZMax],
                                      [ob.XMin,ob.YMin,ob.ZMin,ob.XMax,ob.YMax,ob.ZMax])) < .01,filename
    check.setdefault('step_roundtrip',{})[filename]={'valid':True,'solids':len(exported.Solids),'bounds_match':True}
App.closeDocument(doc.Name)
reopened=App.openDocument(str(fcstd))
assert sum(o.TypeId=='Part::Feature' for o in reopened.Objects)==len(items)
check['fcstd_reopened']=True
check['exported_part_count']=sum(i['export_part'] for i in items)
(OUT/'verification.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
log(json.dumps({'parts':len(items),'size_mm':check['assembly_size_mm'],
                'collisions':check['critical_interferences'],'fcstd_reopened':True,'output':str(OUT)},ensure_ascii=False))
