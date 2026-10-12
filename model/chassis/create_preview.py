"""Render the generated CAD meshes and write a self-contained offline viewer and GLB."""
from pathlib import Path
import json
import struct
import shutil
import math
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'v1-fixed-front-wheels'
data=json.loads((OUT/'preview-meshes.json').read_text(encoding='utf-8'))

def moves_up(item):
    return item['name']=='UpperDeck' or item['name'].startswith(('BoardPost','FPGA','LPi4A','UpperScrew'))

def render(filename, exploded=False, shell_only=False, top=False):
    triangles=[]
    colors=[]
    bounds=[]
    light=np.array([-.35,-.55,.9]);light/=np.linalg.norm(light)
    for item in data:
        if shell_only and item['category'] in ('Hardware','Fasteners'):continue
        v=np.asarray(item['vertices'],dtype=float)
        f=np.asarray(item['indices'],dtype=int)
        if not len(f):continue
        if exploded and moves_up(item):v[:,2]+=65
        t=v[f]
        n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
        lengths=np.linalg.norm(n,axis=1)
        n/=np.maximum(lengths[:,None],1e-10)
        shade=.52+.48*np.maximum(n@light,0)
        color=np.clip(np.asarray(item['color'])[None,:]*shade[:,None]+.065,0,1)
        triangles.extend(t)
        colors.extend(color)
        bounds.extend(v)
    fig=plt.figure(figsize=(13.5,9),dpi=160,facecolor='#edf1f5')
    ax=fig.add_subplot(111,projection='3d',computed_zorder=False)
    ax.set_facecolor('#edf1f5')
    coll=Poly3DCollection(np.asarray(triangles),facecolors=np.asarray(colors),
                          edgecolors='none',linewidths=0,zsort='average')
    ax.add_collection3d(coll)
    b=np.asarray(bounds)
    lo,hi=b.min(0),b.max(0)
    center=(lo+hi)/2
    # Static render includes a ground contact plane, never guessed image geometry.
    plane=np.array([[[-160,-165,-.5],[160,-165,-.5],[160,155,-.5],[-160,155,-.5]]])
    ax.add_collection3d(Poly3DCollection(plane,facecolor='#dce2e9',edgecolor='none',alpha=.45))
    pad=16
    ax.set_xlim(lo[0]-pad,hi[0]+pad);ax.set_ylim(lo[1]-pad,hi[1]+pad)
    ax.set_zlim(-2,max(hi[2]+8,120))
    ax.set_box_aspect((hi[0]-lo[0]+2*pad,hi[1]-lo[1]+2*pad,max(hi[2]+10,122)))
    ax.set_proj_type('ortho')
    ax.view_init(elev=90 if top else 28,azim=-90 if top else -53)
    ax.set_axis_off()
    fig.subplots_adjust(left=0,right=1,bottom=.025,top=.91)
    label='TOP VIEW' if top else ('EXPLODED ASSEMBLY' if exploded else ('SHELL AND RUNNING GEAR' if shell_only else 'ASSEMBLED MODEL'))
    fig.text(.055,.94,'EdgeMind  /  FOUR-WHEEL CHASSIS',fontweight='bold',fontsize=19,color='#203348')
    fig.text(.055,.91,label+'  ·  80 mm wheels  ·  2 rear motors / 2 passive front wheels',fontsize=10,color='#647689')
    fig.text(.055,.035,'CAD geometry preview  |  millimetres  |  front = -Y  |  fit reference, not a production release',fontsize=9,color='#617286')
    fig.savefig(OUT/filename,dpi=160,facecolor=fig.get_facecolor())
    plt.close(fig)

def glb_export():
    scene={'asset':{'version':'2.0','generator':'EdgeMind FreeCAD concept chassis'},
           'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],
           'materials':[],'buffers':[{}],'bufferViews':[],'accessors':[]}
    blob=bytearray()
    def view(raw,target):
        while len(blob)%4:blob.append(0)
        start=len(blob);blob.extend(raw)
        idx=len(scene['bufferViews'])
        scene['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(raw),'target':target})
        return idx
    for item in data:
        v=np.asarray(item['vertices'],dtype=np.float32)
        if len(v)==0:continue
        # glTF uses metres and +Y up. Native STEP/STL use mm and +Z up.
        v=np.column_stack((v[:,0],v[:,2],-v[:,1])).astype('<f4')*.001
        idx=np.asarray(item['indices'],dtype='<u4').ravel()
        pv=view(v.tobytes(),34962);iv=view(idx.tobytes(),34963)
        pa=len(scene['accessors']);scene['accessors'].append({'bufferView':pv,'componentType':5126,'count':len(v),'type':'VEC3','min':v.min(0).tolist(),'max':v.max(0).tolist()})
        ia=len(scene['accessors']);scene['accessors'].append({'bufferView':iv,'componentType':5125,'count':len(idx),'type':'SCALAR'})
        material=len(scene['materials'])
        scene['materials'].append({'name':item['name'],'pbrMetallicRoughness':{'baseColorFactor':[*item['color'],1],'metallicFactor':.35 if item['category']=='Mounts' else .15,'roughnessFactor':.68},'doubleSided':False})
        mesh=len(scene['meshes']);scene['meshes'].append({'name':item['label'],'primitives':[{'attributes':{'POSITION':pa},'indices':ia,'material':material}]})
        node=len(scene['nodes']);scene['nodes'].append({'name':item['label'],'mesh':mesh,'extras':{'category':item['category'],'native_part':item['name']}})
        scene['scenes'][0]['nodes'].append(node)
    while len(blob)%4:blob.append(0)
    scene['buffers'][0]['byteLength']=len(blob)
    js=json.dumps(scene,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    js+=b' '*((-len(js))%4)
    body=struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(blob),0x004e4942)+blob
    (OUT/'EdgeMind_Assembly.glb').write_bytes(struct.pack('<III',0x46546c67,2,12+len(body))+body)

template=(HERE/'viewer_template.html').read_text(encoding='utf-8')
html=template.replace('@@MODEL_DATA@@',json.dumps(data,ensure_ascii=False,separators=(',',':')))
(OUT/'查看模型.html').write_text(html,encoding='utf-8')
(OUT/'vendor').mkdir(exist_ok=True)
vendor=ROOT/'model/hardware/ACX720-V3机械文件/converted/vendor'
for name in ('three.min.js','three.LICENSE.txt'):
    shutil.copyfile(vendor/name,OUT/'vendor'/name)
if '--matplotlib' in sys.argv:
    print('Render optional matplotlib views',flush=True)
    for filename,options in [('preview-assembled.png',{}),('preview-shell.png',{'shell_only':True}),
                             ('preview-exploded.png',{'exploded':True}),('preview-top.png',{'top':True})]:
        render(filename,**options)
glb_export()
print(json.dumps({'viewer':str(OUT/'查看模型.html'),'glb':str(OUT/'EdgeMind_Assembly.glb'),'mesh_count':len(data)},ensure_ascii=False),flush=True)
