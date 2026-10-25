"""Generate an offline viewer and GLB from the exact assembly tessellation."""
from pathlib import Path
import json,struct,shutil
import numpy as np
HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'preview-meshes.json').read_text(encoding='utf-8'))
html=(HERE.parent/'viewer_template.html').read_text(encoding='utf-8')
html=html.replace('EdgeMind 四轮外壳 · 3D 模型','EdgeMind V5 · 4.3寸RGB触摸屏')
html=html.replace('EdgeMind · 四轮外壳模型','EdgeMind V5 · 屏幕与板卡试摆')
html=html.replace('后轮驱动 · 前轮轴承从动','4.3寸竖屏平放 · 洞洞板右移纵向放置')
html=html.replace('按最新版双层底盘概念建模。四轮直径均为 80 mm，前轮固定朝前，无驱动电机。','屏幕放在红框区域，正面朝上，长边沿车身前后方向。洞洞板右移并在板面内旋转90°。屏幕用四个12mm参考隔柱架起，背面留过线窗。共11处过线孔。')
html=html.replace('显示板卡、电机与电池','显示屏幕、板卡与传感器').replace('显示车轮与轴承','显示轮组').replace('显示上层托盘','显示第二层总成')
html=html.replace('<label for="explode">上层展开','<label><input type="checkbox" id="third" checked>显示第三层总成</label><label for="explode">分层展开')
html=html.replace('双层板厚　3 mm','第三层板厚　5 mm').replace('上层托盘底面　Z = 64 mm','屏幕模块　116 × 67.2 mm参考').replace('后轮轴　Y = +80 mm','裸屏含触摸层厚　4.05 mm').replace('前轮轴　Y = −95 mm','洞洞板　纵向90.23 × 横向69.97 mm')
html=html.replace('前后轮固定时，差速转弯存在横向拖擦。板卡参考位置与轮毂适配仍需实物确认。','屏幕完整模块的孔距、PCB厚度和背面接口高度未提供机械尺寸，当前为安装参考。第三层开4×8mm可调槽；加工前复核实物。MPU孔距仍为图片估算。')
html=html.replace('href="../README.md"','href="README.md"')
html=html.replace('四轮装配 · CAD 实体几何','V5 · 屏幕在红框侧平放为竖屏 / 洞洞板右移纵向')
html=html.replace('<button id="reset">重置</button>','<button id="reset">重置</button><button id="sensor-focus">屏幕与板卡特写</button><button id="third-only">仅第三层</button>')
html=html.replace('<a class="download" href="EdgeMind_Shell.step" download>外壳与支架 STEP</a>','<a class="download" href="ThirdDeck.step" download>第三层板 STEP</a><a class="download" href="ThirdDeck.stl" download>第三层板 STL（试摆孔位）</a><a class="download" href="EdgeMind_ThirdAssembly.step" download>第三层总成 STEP</a><a class="download" href="EdgeMind_ScreenAssembly.step" download>屏幕安装参考 STEP</a><a class="download" href="ThirdDeck-drawing.svg" target="_blank">第三层孔位图</a>')
html=html.replace('let theta=-.95,phi=1.05,distance=620,target=new THREE.Vector3(0,0,45),drag=null;','let theta=-2.15,phi=1.02,distance=720,target=new THREE.Vector3(0,-5,100),drag=null,thirdOnly=false;')
html=html.replace('theta=-.95;phi=1.05;target.set(0,0,45);distance=620','theta=-2.15;phi=1.02;target.set(0,-5,100);distance=720')
html=html.replace('function draw(){camera.position.set','function draw(){grid.visible=phi<=Math.PI/2&&!thirdOnly;camera.position.set')
html=html.replace("roughness:.64", "roughness:.64,flatShading:item.name==='ThirdDeck'||item.name==='CameraBracket'")
start=html.index('function lifts(i)')
end=html.index("canvas.onpointerdown=",start)
html=html[:start]+'''
function update(){const amount=Number(document.getElementById('explode').value);document.getElementById('explode-label').textContent=amount;
for(const m of meshes){const i=m.userData;m.visible=true;
if(i.category==='Hardware')m.visible=document.getElementById('electronics').checked;
if(i.category==='Wheels')m.visible=document.getElementById('wheels').checked;
if(i.category==='Fasteners')m.visible=document.getElementById('fasteners').checked;
if(i.layer===2&&!document.getElementById('upper').checked)m.visible=false;
if(i.layer===3&&!document.getElementById('third').checked)m.visible=false;
if(thirdOnly&&i.layer!==3)m.visible=false;
m.position.z=i.layer===3?amount*2:(i.layer===2?amount:0);}draw();}
for(const id of ['electronics','wheels','upper','third','fasteners','explode'])document.getElementById(id).oninput=update;
function normal(){thirdOnly=false;document.getElementById('third-only').classList.remove('active');document.getElementById('third').checked=true;update();reset();}
document.getElementById('reset').onclick=normal;document.getElementById('iso').onclick=normal;
document.getElementById('top').onclick=()=>{phi=.001;theta=-Math.PI/2;draw();};
document.getElementById('front').onclick=()=>{phi=Math.PI/2;theta=-Math.PI/2;draw();};
window.setChassisView=(t,p,d=720,at)=>{theta=t;phi=p;distance=d;if(at)target.set(...at);draw();};
document.getElementById('sensor-focus').onclick=()=>{thirdOnly=false;document.getElementById('third-only').classList.remove('active');document.getElementById('third').checked=true;document.getElementById('electronics').checked=true;document.getElementById('explode').value=0;update();window.setChassisView(-1.75,.43,410,[0,-42,168]);};
document.getElementById('third-only').onclick=()=>{thirdOnly=!thirdOnly;document.getElementById('third-only').classList.toggle('active',thirdOnly);document.getElementById('third').checked=true;document.getElementById('explode').value=0;update();window.setChassisView(-2.15,.65,540,[0,-5,162]);};
''' +html[end:]
html=html.replace('window.chassisViewerState={rendered:true,parts:meshes.length','window.chassisViewerState={rendered:true,thirdOnly,layer_parts:meshes.map(m=>({name:m.name,layer:m.userData.layer,lift:m.position.z,visible:m.visible})),parts:meshes.length')
(HERE/'查看模型.html').write_text(html.replace('@@MODEL_DATA@@',json.dumps(data,ensure_ascii=False,separators=(',',':'))),encoding='utf-8')
(HERE/'vendor').mkdir(exist_ok=True)
for n in ('three.min.js','three.LICENSE.txt'):shutil.copyfile(HERE.parent/'v1-fixed-front-wheels/vendor'/n,HERE/'vendor'/n)
scene={'asset':{'version':'2.0','generator':'EdgeMind V5 FreeCAD geometry and documented screen installation reference'},'scene':0,'scenes':[{'nodes':[]}],
       'nodes':[],'meshes':[],'materials':[],'buffers':[{}],'bufferViews':[],'accessors':[]}
blob=bytearray()
def view(raw,target):
    while len(blob)%4:blob.append(0)
    start=len(blob);blob.extend(raw);idx=len(scene['bufferViews'])
    scene['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(raw),'target':target});return idx
for p in data:
    v=np.asarray(p['vertices'],dtype=np.float32);v=np.column_stack((v[:,0],v[:,2],-v[:,1])).astype('<f4')*.001
    f=np.asarray(p['indices'],dtype='<u4').ravel();pv=view(v.tobytes(),34962);iv=view(f.tobytes(),34963)
    pa=len(scene['accessors']);scene['accessors'].append({'bufferView':pv,'componentType':5126,'count':len(v),'type':'VEC3','min':v.min(0).tolist(),'max':v.max(0).tolist()})
    ia=len(scene['accessors']);scene['accessors'].append({'bufferView':iv,'componentType':5125,'count':len(f),'type':'SCALAR'})
    ma=len(scene['materials']);scene['materials'].append({'name':p['name'],'pbrMetallicRoughness':{'baseColorFactor':[*p['color'],1],'metallicFactor':.35 if p['category']=='Mounts' else .15,'roughnessFactor':.68}})
    mi=len(scene['meshes']);scene['meshes'].append({'name':p['label'],'primitives':[{'attributes':{'POSITION':pa},'indices':ia,'material':ma}]})
    ni=len(scene['nodes']);scene['nodes'].append({'name':p['label'],'mesh':mi,'extras':{'native_part':p['name'],'layer':p['layer']}});scene['scenes'][0]['nodes'].append(ni)
while len(blob)%4:blob.append(0)
scene['buffers'][0]['byteLength']=len(blob);j=json.dumps(scene,ensure_ascii=False,separators=(',',':')).encode('utf-8')
while len(j)%4:j+=b' '
total=12+8+len(j)+8+len(blob)
(HERE/'EdgeMind_Assembly.glb').write_bytes(struct.pack('<III',0x46546c67,2,total)+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(blob),0x004e4942)+blob)
print(json.dumps({'parts':len(data),'GLB_bytes':total}),flush=True)
