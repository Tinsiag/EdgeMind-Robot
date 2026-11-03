"""CAD-derived look-ahead translation and full-turn radial guards."""
import json,math
from pathlib import Path
from generate_turn_envelope import hull,geometry_values
ROOT=Path(__file__).resolve().parents[1]
def tables():
 g=json.loads((ROOT/'config/geometry.json').read_text());f,r,w,lx,ly=geometry_values(g)
 # 45mm = retained 40mm base plus conservative numeric/installation reserve.
 p=45; corners=[(x,y) for x in (-r-p,f+p) for y in (-w-p,w+p)]
 shapes=[]
 for theta,travel in [(0,160),(180,100),(90,200),(-90,200)]:
  a=math.radians(theta);c,s=math.cos(a),math.sin(a)
  # Backward motion keeps the body orientation, unlike side exits after a turn.
  orient=0 if theta==180 else a;co,so=math.cos(orient),math.sin(orient)
  shapes.append(hull([(x*co-y*so+t*c-lx,x*so+y*co+t*s-ly) for x,y in corners for t in (0,travel)]))
 def limit(poly,a):
  dx,dy=math.cos(math.radians(a)),math.sin(math.radians(a));out=1e9
  for i,(x,y) in enumerate(poly):
   q=poly[(i+1)%len(poly)];nx,ny=q[1]-y,x-q[0];v=nx*dx+ny*dy
   if v>1e-9:out=min(out,(nx*x+ny*y)/v)
  return out
 result=[];radius=math.hypot(f+p,w+p)
 for low in range(0,360,5):
  vals=[]
  for poly in shapes:
   angles=[low,low+5]+[math.degrees(math.atan2(y,x))%360 for x,y in poly if low<=math.degrees(math.atan2(y,x))%360<=low+5]
   vals.append(math.ceil(max(limit(poly,a) for a in angles))+2)
  # Conservative dense angular maximum plus 2mm: smooth circle derivative
  # bounded by lidar offset; 0.01deg sampling contributes <0.1mm here.
  vals.append(math.ceil(max(-lx*math.cos(math.radians(low+i/100))+math.sqrt(radius**2-lx**2*math.sin(math.radians(low+i/100))**2) for i in range(501)))+2)
  result.append(vals)
 return result
def render():
 names=['advance_limit','reverse_limit','left_exit_limit','right_exit_limit','spin_limit']
 lines=['`timescale 1ns/1ps','`default_nettype none','// Generated CAD path guards; see generate_path_envelope.py.',
 'module a745_path_envelope(input wire [6:0] bin,output reg [9:0] '+','.join(names)+');','always @* begin']
 lines+=[' '+n+'=1023;' for n in names]+[' case(bin)']
 for i,v in enumerate(tables()):lines.append("  7'd%d:begin "%i+''.join("%s=10'd%d;"%(n,k) for n,k in zip(names,v))+'end')
 return '\n'.join(lines+[' default:begin end',' endcase','end','endmodule','`default_nettype wire',''])
if __name__=='__main__':(ROOT/'rtl/a745_path_envelope.v').write_text(render(),encoding='utf-8')
