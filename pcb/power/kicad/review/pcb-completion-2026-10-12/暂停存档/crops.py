import json,sys
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Circle
D=json.load(open(sys.argv[1]));fig,axs=plt.subplots(2,2,figsize=(13,12))
for ax,(x0,y0,x1,y1,title) in zip(axs.flat,[(94,44,101,54,'U7 fault'),(80,44,87,56,'U8 fault'),(42,101,49,111,'U10 reset'),(86,90,102,98,'Motor bus right')]):
 ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.set_aspect('equal');ax.set_title(title)
 for t in D['tracks']:
  if not any(x0-3<p[0]<x1+3 and y0-3<p[1]<y1+3 for p in [t['start'],t['end']]):continue
  color='#b23333' if t['layers']==[0] else '#2255b5'
  a,b=t['start'],t['end'];ax.plot([a[0],b[0]],[a[1],b[1]],c=color,lw=t['width']*27,solid_capstyle='round',alpha=.7)
  if t['via']:ax.add_patch(Circle(a,t['width']/2,fc='#449977',ec='black'))
 for p in D['pads']:
  if x0-2<p['pos'][0]<x1+2 and y0-2<p['pos'][1]<y1+2:
   for poly in p['polys']:ax.add_patch(Polygon(poly['outer'],fc='#c9a657',ec='black',lw=.3))
   ax.text(*p['pos'],p['ref']+':'+p['num'],fontsize=5,ha='center',va='center')
 ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(sys.argv[2],dpi=150)
