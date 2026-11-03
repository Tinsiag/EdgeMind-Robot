"""Independent continuous-footprint samples against generated radial guard ROM."""
import hashlib,json,math,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from generate_path_envelope import render
def main():
 path=ROOT/'rtl/a745_path_envelope.v';text=path.read_text();assert text==render()
 rows=re.findall(r"advance_limit=10'd(\d+);reverse_limit=10'd(\d+);left_exit_limit=10'd(\d+);right_exit_limit=10'd(\d+);spin_limit=10'd(\d+);",text)
 table=[[int(n) for n in r] for r in rows];assert len(table)==72
 geometry=json.loads((ROOT/'config/geometry.json').read_text());lx,ly=geometry['lidar_origin_in_axle_frame_mm'][:2]
 p=geometry['vehicle_outer_footprint_mm'];xs=[q[0] for q in p];ys=[q[1] for q in p]
 corners=[(min(xs)-40,min(ys)-40),(max(xs)+40,min(ys)-40),(max(xs)+40,max(ys)+40),(min(xs)-40,max(ys)+40)]
 points=[]
 for i,(x,y) in enumerate(corners):
  xx,yy=corners[(i+1)%4]
  for k in range(17):points.append((x+(xx-x)*k/16,y+(yy-y)*k/16))
 count=0;minimum=1e9
 def check(x,y,column):
  nonlocal count,minimum
  x-=lx;y-=ly;a=math.degrees(math.atan2(y,x))%360
  margin=table[int(a//5)][column]-math.hypot(x,y)
  assert margin>=0,(x,y,column,margin)
  count+=1;minimum=min(minimum,margin)
 for col,rotation,travel in [(0,0,160),(1,0,-100),(2,90,200),(3,-90,200)]:
  a=math.radians(rotation);c,s=math.cos(a),math.sin(a)
  for k in range(101):
   for x,y in points:
    dx=(travel*k/100 if col in (0,1) else 0);dy=(travel*k/100*(1 if col==2 else -1) if col in (2,3) else 0)
    check(x*c-y*s+dx,x*s+y*c+dy,col)
 for tenth in range(3601):
  a=math.radians(tenth/10);c,s=math.cos(a),math.sin(a)
  for x,y in points:check(x*c-y*s,x*s+y*c,4)
 result=dict(passed=True,points=count,minimum_margin_mm=minimum,physical_tested=False,
  input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [path,ROOT/'config/geometry.json',Path(__file__).resolve(),ROOT/'scripts/generate_path_envelope.py']})
 (ROOT/'.local/tests/path-geometry-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
