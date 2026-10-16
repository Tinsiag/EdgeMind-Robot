"""Extract, measure and retain the supplied R3X hardware without rescaling it."""
from pathlib import Path
import json,hashlib
import FreeCAD as App
import Part

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'model/hardware/R3X-320x240-reference.step'
P=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
V=App.Vector

def exact_bounds(s):
    b=s.optimalBoundingBox(False,False)
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def extract():
    previous={}
    record=HERE/'reference-extraction.json'
    if record.exists():
        old=json.loads(record.read_text(encoding='utf-8'))
        if old['sha256']==hashlib.sha256(SOURCE.read_bytes()).hexdigest():
            previous={p['name']:p for p in old['parts']}
    shapes=Part.read(str(SOURCE)).Solids
    assert len(shapes)==28
    result=[]
    # The reference's +X points rearwards; a 90-degree rotation makes front=-Y.
    for side,idxs in [('L',[1,2,3,14,15,16,17,18,19,20]),('R',[4,5,6,21,22,23,24,25,26,27])]:
        for i in idxs:
            s=shapes[i].copy()
            s.rotate(V(0,0,0),V(0,0,1),90)
            s.translate(V(810,P['rear_axle_y']-660, P['lower_deck_bottom_z']+5))
            if i in (1,4):name,cat='MotorBracket'+side,'Mounts'
            elif i in (2,5):name,cat='Rear'+side+'Wheel','Wheels'
            elif i in (3,6):name,cat='Rear'+side+'Hub','Wheels'
            else:name,cat='Motor'+side+'Part'+str(i),'Hardware'
            result.append((name,cat,s,i))
    for side,cx in [('L',-P['caster_pivot_x']),('R',P['caster_pivot_x'])]:
        for i in (11,12,13):
            s=shapes[i].copy()
            s.rotate(V(0,0,0),V(0,0,1),90)
            s.translate(V(810+cx,P['caster_pivot_y']-455.25,59))
            result.append(('Caster'+side+{11:'Axle',12:'Wheel',13:'Swivel'}[i],'Wheels',s,i))
    holes=[]
    for name,cat,s,i in result:
        if not name.startswith('MotorBracket'):continue
        for f in s.Faces:
            surf=f.Surface
            if isinstance(surf,Part.Cylinder) and abs(surf.Axis.z)>.999 and surf.Radius<3:
                c=surf.Center
                holes.append([round(c.x,6),round(c.y,6),round(surf.Radius,6)])
    holes=sorted(set(tuple(h) for h in holes))
    report={'source':str(SOURCE.relative_to(ROOT)), 'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'source_solids':28,'scale':1,'rear_bracket_mount_holes_xy_radius':holes,
            'parts':[{'name':n,'category':c,'source_solid_index':i,'bounds':exact_bounds(s),
                      'valid':previous[n]['valid'] if n in previous else s.isValid(),
                      'volume_mm3':previous[n]['volume_mm3'] if n in previous else s.Volume,
                      'faces':len(s.Faces)} for n,c,s,i in result]}
    (HERE/'reference-extraction.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    cache=HERE/'hardware-brep'
    cache.mkdir(exist_ok=True)
    for n,c,s,i in result:s.exportBrep(str(cache/(n+'.brep')))
    return result,report

if __name__=='__main__':
    parts,report=extract()
    for n,c,s,i in parts:
        if n.endswith(('Wheel','Swivel')) or n.startswith('MotorBracket'):
            print(n,exact_bounds(s),flush=True)
    print('Mount holes',report['rear_bracket_mount_holes_xy_radius'],flush=True)
