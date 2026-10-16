"""Generate an offline viewer and a metre/Y-up GLB from actual CAD tessellation."""
from pathlib import Path
import json,struct,shutil
import numpy as np

HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'preview-meshes.json').read_text(encoding='utf-8'))
template=(HERE.parent/'viewer_template.html').read_text(encoding='utf-8')
template=template.replace('EdgeMind 四轮外壳 · 3D 模型','EdgeMind V3 · 摄像头与闭合围栏')
template=template.replace('EdgeMind · 四轮外壳模型','EdgeMind V3 · 摄像头底盘')
template=template.replace('后轮驱动 · 前轮轴承从动','5 mm 双层底板 · 前置摄像头 · R3X 轮组')
template=template.replace('按最新版双层底盘概念建模。四轮直径均为 80 mm，前轮固定朝前，无驱动电机。','上下底板均为 5 mm。去掉两侧上护栏，前、左、右通风围栏连接为一体。前沿增加摄像头立板，电机接口上方各开一个 12 × 24 mm 圆角过线孔。')
template=template.replace('显示板卡、电机与电池','显示板卡与电机').replace('显示车轮与轴承','显示轮组与万向轮').replace('显示上层托盘','显示上层总成')
template=template.replace('双层板厚　3 mm','下层 / 上层板厚　5 / 5 mm').replace('上层托盘底面　Z = 64 mm','摄像头板　30 × 30 · 孔距24 mm').replace('后轮轴　Y = +80 mm','电机过线孔　12 × 24 mm × 2').replace('前轮轴　Y = −95 mm','电池围栏　内87 × 49 · 高3 mm')
template=template.replace('前后轮固定时，差速转弯存在横向拖擦。板卡参考位置与轮毂适配仍需实物确认。','电池不设厚度限制，使用两条尼龙扎带固定。FPGA 与 LPi4A 仍为尺寸参考；电源板仍为旧版 100 × 50 mm STEP。')
template=template.replace('href="../README.md"','href="README.md"')
template=template.replace('四轮装配 · CAD 实体几何','V3 装配 · 摄像头 / 5 mm 双层底板')
template=template.replace('target.set(0,0,45)','target.set(0,-10,78)').replace('target=new THREE.Vector3(0,0,45)','target=new THREE.Vector3(0,-10,78)')
template=template.replace("function lifts(i){return i.name==='UpperDeck'||/^(BoardPost|FPGA|LPi4A|UpperScrew)/.test(i.name);}","function lifts(i){return i.upper_assembly===true;}")
template=template.replace("if(i.name==='UpperDeck')m.visible=document.getElementById('upper').checked;","if(i.upper_assembly&&!document.getElementById('upper').checked)m.visible=false;")
template=template.replace("const amount=Number(document.getElementById('explode').value);", "const amount=Number(document.getElementById('explode').value);")
template=template.replace("window.chassisViewerState={rendered:true,parts:meshes.length", "window.chassisViewerState={rendered:true,upper_parts:meshes.filter(m=>m.userData.upper_assembly).map(m=>({name:m.name,lift:m.position.z,visible:m.visible})),parts:meshes.length")
template=template.replace("function resize(){", "window.setChassisView=function(t,p,d=620,at){theta=t;phi=p;distance=d;if(at)target.set(...at);draw();};function resize(){")
template=template.replace('function draw(){camera.position.set','function draw(){grid.visible=phi<=Math.PI/2;camera.position.set')
template=template.replace('roughness:.64','roughness:.64,flatShading:item.category===\'Shell\'||item.name===\'CameraBracket\'')
template=template.replace('<button id="reset">重置</button>','<button id="reset">重置</button><button id="camera-focus">摄像头特写</button>')
template=template.replace("new ResizeObserver(resize).observe(stage);", "document.getElementById('camera-focus').onclick=()=>{document.getElementById('upper').checked=true;document.getElementById('electronics').checked=true;document.getElementById('explode').value=0;update();window.setChassisView(-1.05,1.15,190,[0,-127,129]);};new ResizeObserver(resize).observe(stage);")
template=template.replace('<a class="download" href="EdgeMind_Assembly.glb" download>轻量 GLB</a>','<a class="download" href="EdgeMind_Assembly.glb" download>轻量 GLB</a><a class="download" href="EdgeMind_CameraAssembly.step" download>摄像头与立板 STEP</a>')
(HERE/'查看模型.html').write_text(template.replace('@@MODEL_DATA@@',json.dumps(data,ensure_ascii=False,separators=(',',':'))),encoding='utf-8')
(HERE/'vendor').mkdir(exist_ok=True)
for n in ('three.min.js','three.LICENSE.txt'):shutil.copyfile(HERE.parent/'v1-fixed-front-wheels/vendor'/n,HERE/'vendor'/n)

scene={'asset':{'version':'2.0','generator':'EdgeMind V3 direct FreeCAD geometry'},'scene':0,'scenes':[{'nodes':[]}],
       'nodes':[],'meshes':[],'materials':[],'buffers':[{}],'bufferViews':[],'accessors':[]}
blob=bytearray()
def view(raw,target):
    while len(blob)%4:blob.append(0)
    start=len(blob);blob.extend(raw);idx=len(scene['bufferViews'])
    scene['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(raw),'target':target});return idx
for item in data:
    v=np.asarray(item['vertices'],dtype=np.float32)
    v=np.column_stack((v[:,0],v[:,2],-v[:,1])).astype('<f4')*.001
    f=np.asarray(item['indices'],dtype='<u4').ravel()
    pv=view(v.tobytes(),34962);iv=view(f.tobytes(),34963)
    pa=len(scene['accessors']);scene['accessors'].append({'bufferView':pv,'componentType':5126,'count':len(v),'type':'VEC3','min':v.min(0).tolist(),'max':v.max(0).tolist()})
    ia=len(scene['accessors']);scene['accessors'].append({'bufferView':iv,'componentType':5125,'count':len(f),'type':'SCALAR'})
    ma=len(scene['materials']);scene['materials'].append({'name':item['name'],'pbrMetallicRoughness':{'baseColorFactor':[*item['color'],1],'metallicFactor':.4 if item['category']=='Mounts' else .15,'roughnessFactor':.68}})
    mi=len(scene['meshes']);scene['meshes'].append({'name':item['label'],'primitives':[{'attributes':{'POSITION':pa},'indices':ia,'material':ma}]})
    ni=len(scene['nodes']);scene['nodes'].append({'name':item['label'],'mesh':mi,'extras':{'category':item['category'],'native_part':item['name'],'upper_assembly':item['upper_assembly']}})
    scene['scenes'][0]['nodes'].append(ni)
while len(blob)%4:blob.append(0)
scene['buffers'][0]['byteLength']=len(blob)
j=json.dumps(scene,ensure_ascii=False,separators=(',',':')).encode('utf-8')
while len(j)%4:j+=b' '
total=12+8+len(j)+8+len(blob)
(HERE/'EdgeMind_Assembly.glb').write_bytes(struct.pack('<III',0x46546c67,2,total)+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(blob),0x004e4942)+blob)
print(json.dumps({'parts':len(data),'GLB_bytes':total,'viewer_bytes':(HERE/'查看模型.html').stat().st_size}))
