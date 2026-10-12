"""Readable engineering preview from KiCad's actual copper geometry."""
import sys,json,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle,Circle
from matplotlib.collections import LineCollection
D=json.load(open(sys.argv[1]));bx0,by0,bx1,by1=D['outline'];fig,ax=plt.subplots(figsize=((bx1-bx0)/8,(by1-by0)/8))
ax.set_xlim(bx0-2,bx1+2);ax.set_ylim(by1+2,by0-2);ax.set_aspect('equal');ax.set_facecolor('#f4f7f5')
scale=(bx1-bx0)/8*72/(bx1-bx0+4)
for layer,color in [(2,'#557bb3'),(0,'#b34747')]:
    for t in D['tracks']:
        if layer not in t['layers']:continue
        a,b=t['start'],t['end']
        if t['via']:ax.add_patch(Circle(a,t['width']/2,facecolor='#56866e',edgecolor='none',zorder=3))
        else:ax.plot([a[0],b[0]],[a[1],b[1]],c=color,lw=t['width']*scale,solid_capstyle='round',alpha=.9,zorder=2)
for f in D['parts']:
    x1,y1,x2,y2=f['box'];ax.add_patch(Rectangle((x1,y1),x2-x1,y2-y1,fc='none',ec='#6b8175',lw=.45,zorder=3))
    ax.text((x1+x2)/2,y1-.45,f['ref'],ha='center',va='bottom',fontsize=5.5,color='#132e22',zorder=7,clip_on=True)
for p in D['pads']:
    for poly in p['polys']:ax.add_patch(Polygon(poly['outer'],fc='#c9a657',ec='#8f753f',lw=.15,zorder=4))
    if p['drill'][0]:ax.add_patch(Circle(p['pos'],min(p['drill'])/2,facecolor='#f4f7f5',edgecolor='none',zorder=5))
ax.add_patch(Rectangle((bx0,by0),bx1-bx0,by1-by0,fill=False,edgecolor='#132e22',linewidth=1.2))
ax.grid(alpha=.12);ax.set_xlabel('mm');ax.set_ylabel('mm');fig.tight_layout()
fig.savefig(sys.argv[2],dpi=160)
