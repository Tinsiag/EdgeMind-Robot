"""Measure changed features directly in the delivered CAD geometry."""
from pathlib import Path
import json,math
import FreeCAD as App
import Part

HERE=Path(__file__).resolve().parent
def measure_features(doc,report):
    low=report['parameters']['lower_deck_bottom_z'];top=report['parameters']['upper_deck_bottom_z']
    tray=doc.getObject('LowerTray').Shape
    measurements={}
    for name,z in [('LowerTray',low),('UpperDeck',top)]:
        section=doc.getObject(name).Shape.common(Part.makeLine(App.Vector(0,100,z-1),App.Vector(0,100,z+10)))
        thick=sum(e.Length for e in section.Edges)
        assert abs(thick-5)<1e-6,(name,thick)
        measurements[name]=thick
    openings=[]
    for h in report['motor_wire_holes']:
        x,y=h['center'];w=h['width'];l=h['length'];r=h['radius']
        envelope=Part.makeBox(w,l,5,App.Vector(x-w/2,y-l/2,low))
        area=(envelope.Volume-tray.common(envelope).Volume)/5
        expected=w*l-4*r*r*(1-math.pi/4)
        assert abs(area-expected)<1e-4,(h['connector'],area,expected)
        b=h['connector_bounds'];assert x-w/2<b[0]<b[3]<x+w/2 and y-l/2<b[1]<b[4]<y+l/2
        openings.append({'connector':h['connector'],'measured_open_area_mm2':area,'expected_area_mm2':expected})
    bracket=doc.getObject('CameraBracket').Shape;mount_z=report['camera']['camera_board_bottom_z']+3
    for x in (-12,12):assert not bracket.isInside(App.Vector(x,-121.5,mount_z),1e-6,True)
    assert not bracket.isInside(App.Vector(0,-121.5,report['camera']['camera_board_bottom_z']+26),1e-6,True)
    camera=Part.read(str(HERE/'EdgeMind_CameraAssembly.step'))
    assert camera.isValid() and camera.isClosed()
    expected_solids=sum(len(o.Shape.Solids) for o in doc.Objects if o.TypeId=='Part::Feature' and o.Name.startswith('Camera'))
    assert len(camera.Solids)==expected_solids
    result={'measured_plate_thicknesses_mm':measurements,'measured_motor_openings':openings,
        'camera_mount_slots_clear':True,'camera_header_window_clear':True,'camera_STEP_valid':True,'camera_STEP_solids':len(camera.Solids)}
    report['feature_measurements']=result
    return result

if __name__=='__main__':
    r=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    d=App.openDocument(str(HERE/'EdgeMind_Chassis.FCStd'))
    result=measure_features(d,r)
    App.closeDocument(d.Name)
    (HERE/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
