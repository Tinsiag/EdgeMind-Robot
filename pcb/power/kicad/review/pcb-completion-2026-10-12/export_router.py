"""Export protected existing copper and front-preferred, two-layer rules."""
import sys,json,re
from pathlib import Path
import pcbnew as k
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kicad_tools import parse,child,children,apply_edits
b=k.LoadBoard(sys.argv[1])
for t in b.GetTracks():t.SetLocked(True)
assert b.GetCopperLayerCount()==2
assert k.ExportSpecctraDSN(b,sys.argv[2])
p=Path(sys.argv[2]);s=p.read_text().replace('(string_quote ")','(string_quote "")');root=parse(s);net=child(root,'network');structure=child(root,'structure')
groups={'motor_bus':(3.0,['VM_SWITCHED']), 'motor_feed':(2.0,['VM_L','VM_R','Net-(J16-Pin_2)','Net-(J17-Pin_2)']), 'motor_out':(1.8,['Net-(J3-Pin_1)','Net-(J3-Pin_6)','Net-(J4-Pin_1)','Net-(J4-Pin_6)']), 'buck_input':(1.5,['VLOGIC_IN']), 'power5':(1.2,['+5V_AI','+5V_FPGA']), 'protected5':(1.0,['+5V_AI_PROT','+5V_FPGA_PROT']),
        'logic3':(.6,['+3V3','+3V3_ONBOARD','+3V3_RAW','+3V3_SENS','3V3_FPGA_IN'])}
reserved={n for _,ns in groups.values() for n in ns}
groups['signal']=(.25,[str(n[1]) for n in children(net,'net') if n[1] not in reserved])
classes=[]
for name,(w,names) in groups.items():
    via_name='Via[0-1]_1200:600_um' if name not in ['signal','logic3'] else 'Via[0-1]_600:300_um'
    classes.append('(class '+name+' '+' '.join(json.dumps(n) for n in names)+'\n(circuit (use_via "'+via_name+'")) (rule (width '+str(w*1000)+') (clearance 200)))')
lib=child(root,'library');via_scope=child(structure,'via')
padstack='(padstack "Via[0-1]_1200:600_um" (shape (circle "Top Layer" 1200)) (shape (circle "Bottom Layer" 1200)) (attach off))'
edits=[(lib.end-1,lib.end-1,padstack),(via_scope.end-1,via_scope.end-1,' "Via[0-1]_1200:600_um"')]
edits+=[(c.start,c.end,'') for c in children(net,'class')]
edits.append((net.end-1,net.end-1,'\n'+'\n'.join(classes)+'\n'))
settings='''
    (autoroute_settings
      (fanout off) (autoroute on) (postroute on) (vias on)
      (via_costs 35) (plane_via_costs 10) (start_ripup_costs 100)
      (layer_rule "Top Layer" (active on) (preferred_direction horizontal)
        (preferred_direction_trace_costs 1) (against_preferred_direction_trace_costs 1))
      (layer_rule "Bottom Layer" (active on) (preferred_direction vertical)
        (preferred_direction_trace_costs 4) (against_preferred_direction_trace_costs 4)))
'''
# Freerouting 2.5.0 only parses settings before the first plane/keepout has
# initialized layerStructure. Placing them last silently truncates the import.
boundary=child(structure,'boundary')
edits.append((boundary.start,boundary.start,settings))
s=apply_edits(s,edits).replace('(string_quote "")','(string_quote ")')
p.write_text(s)
print('DSN:',p,'fixed existing wiring; front cost 1, rear cost 4')
