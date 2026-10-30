"""Numerically check the generated limits against dense, independently rotated edges."""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from generate_turn_envelope import check_current


def main():
    geometry_path=ROOT/'config/geometry.json'
    geometry=json.loads(geometry_path.read_text())
    check_current(geometry)
    table_path=ROOT/'rtl/a745_turn_envelope.v'
    table=[(int(l),int(r)) for l,r in re.findall(r"left_limit=9'd(\d+);right_limit=9'd(\d+)",table_path.read_text())]
    assert len(table)==72
    footprint=geometry['vehicle_outer_footprint_mm']
    lx,ly=geometry['lidar_origin_in_axle_frame_mm'][:2]
    # Use the source polygon, not the generator's ray/hull functions. Expand
    # the axis-aligned current footprint by the documented 40mm margin.
    xs=[p[0] for p in footprint];ys=[p[1] for p in footprint]
    corners=[(min(xs)-40,min(ys)-40),(max(xs)+40,min(ys)-40),
             (max(xs)+40,max(ys)+40),(min(xs)-40,max(ys)+40)]
    count=0;minimum_margin=10000
    for direction,sign in enumerate((1,-1)):
        for tenths in range(901):
            radians=math.radians(sign*tenths/10)
            c,s=math.cos(radians),math.sin(radians)
            for i,p in enumerate(corners):
                q=corners[(i+1)%4]
                for step in range(17):
                    t=step/16;x=p[0]+t*(q[0]-p[0]);y=p[1]+t*(q[1]-p[1])
                    px=x*c-y*s-lx;py=x*s+y*c-ly
                    angle=math.degrees(math.atan2(py,px))%360
                    limit=table[min(71,int(angle/5))][direction]
                    margin=limit-math.hypot(px,py)
                    assert margin>=0,(direction,tenths,angle,margin)
                    minimum_margin=min(minimum_margin,margin);count+=1
    assert table[0][0]<500 and table[0][1]<500
    # On the right, a 250mm point may allow turning left away from it.
    assert table[54][0]<250<table[54][1]
    assert table[18][1]<250<table[18][0]
    inputs=[geometry_path,table_path,ROOT/'scripts/generate_turn_envelope.py',Path(__file__).resolve()]
    receipt={'passed':True,'checked_rotated_edge_points':count,'orientation_step_deg':0.1,
             'body_margin_mm':40,'minimum_envelope_excess_mm':minimum_margin,
             'physical_measurement':False,'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (ROOT/'.local/tests/turn-geometry-result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
