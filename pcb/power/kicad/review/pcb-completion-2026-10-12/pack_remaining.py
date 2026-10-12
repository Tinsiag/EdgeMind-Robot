"""Pack remaining courtyards near their functional targets on a 0.25 mm grid."""
import sys,json,math
import numpy as np
D=json.load(open(sys.argv[1]));cfg=json.load(open(sys.argv[2]));fixed=set(cfg['fixed']);P={p['ref']:p for p in D['parts']}
x0,y0,x1,y1=25,36,121,133;step=.25;N=401
mask=np.zeros((N,N),dtype=np.int8)
placed=[]
def mark(bb,margin=.12):
 a,b,c,d=bb
 ix1=max(0,int(math.floor((a-margin-x0)/step)));iy1=max(0,int(math.floor((b-margin-y0)/step)))
 ix2=min(N,int(math.ceil((c+margin-x0)/step))+1);iy2=min(N,int(math.ceil((d+margin-y0)/step))+1)
 mask[iy1:iy2,ix1:ix2]=1
for ref in fixed:
 if ref in ['U2','U4']:
  a,c=P[ref]['box'][0],P[ref]['box'][2];top,bot=P[ref]['box'][1],P[ref]['box'][3]
  mark([a,top,a+3.55,bot]);mark([c-3.55,top,c,bot])
 else:mark(P[ref]['box'])
mask[int((y1-y0)/step):,:]=1
mask[:,int((x1-x0)/step):]=1
through_refs={p['ref'] for p in D['pads'] if p['drill'][0]>0}
# Existing copper may cross a courtyard-free gap; keep new bodies clear of it.
for t in D['tracks']:
 if t['net'] in ['USB1_FAULT_PULSE_N','USB2_FAULT_PULSE_N']:continue
 a,b=t['start'],t['end'];w=t['width']/2+.2
 # Paint a narrow staircase to avoid blocking the full diagonal bounding box.
 for f in np.linspace(0,1,max(2,int(math.dist(a,b)/.2))):
  x=a[0]+(b[0]-a[0])*f;y=a[1]+(b[1]-a[1])*f;mark([x-w,y-w,x+w,y+w],0)
parts=sorted((p for p in D['parts'] if p['ref'] not in fixed),key=lambda p:-(p['box'][2]-p['box'][0])*(p['box'][3]-p['box'][1]))
xs=x0+np.arange(N)*step;ys=y0+np.arange(N)*step;xx,yy=np.meshgrid(xs,ys)
for p in parts:
 tx,ty=p['pos'];bb=np.array(p['box'])-np.array([tx,ty,tx,ty]);best=None
 work=mask.copy()
 if p['ref'] in through_refs:
  for m in ['U2','U4']:
   a,b,c,d=P[m]['box'];work[int((b-y0)/step):int((d-y0)/step)+1,int((a-x0)/step):int((c-x0)/step)+1]=1
 integ=np.pad(work.astype(np.int32).cumsum(0).cumsum(1),((1,0),(1,0)))
 for rot in [0,90]:
  if rot:bbox=np.array([bb[1],-bb[2],bb[3],-bb[0]])
  else:bbox=bb
  a,b,c,d=bbox
  ix1=np.floor((xx+a-x0)/step).astype(int);ix2=np.ceil((xx+c-x0)/step).astype(int)+1
  iy1=np.floor((yy+b-y0)/step).astype(int);iy2=np.ceil((yy+d-y0)/step).astype(int)+1
  valid=(ix1>=1)&(iy1>=1)&(ix2<N-1)&(iy2<N-1)
  xa=ix1.clip(0,N);xb=ix2.clip(0,N);ya=iy1.clip(0,N);yb=iy2.clip(0,N)
  occupied=integ[yb,xb]-integ[ya,xb]-integ[yb,xa]+integ[ya,xa]
  dist=(xx-tx)**2+(yy-ty)**2+(.3 if rot else 0)
  dist[~valid|(occupied>0)]=1e12
  idx=np.argmin(dist);j,i=np.unravel_index(idx,dist.shape)
  if dist[j,i]<1e11 and (best is None or dist[j,i]<best[0]):best=(dist[j,i],float(xs[i]),float(ys[j]),rot,bbox)
 if best is None:raise RuntimeError('No available courtyard: '+p['ref'])
 cost,x,y,rot,bb=best;mark((bb+np.array([x,y,x,y])).tolist());placed.append({'ref':p['ref'],'x':x,'y':y,'rotation_delta':rot,'distance':round(math.hypot(x-tx,y-ty),2)})
json.dump(placed,open(sys.argv[3],'w'),indent=2)
print('Packed',len(placed),'parts; most shifted:',sorted(placed,key=lambda p:-p['distance'])[:12])
