import sys
sys.path.insert(0,'/home/smallcoral/Dev/EdgeMind-Robot/pcb/power/kicad/review/pcb-completion-2026-10-12')
from route_remaining import *
for net,a,c in [('USB1_FAULT_PULSE_N','U7:7','R66:2'),('USB2_FAULT_PULSE_N','U8:7','R68:2'),('Net-(U12A-~{R})','U10:11','U12:1')]:
 route(net,anchor(net,ref=a,whole=True),anchor(net,ref=c,whole=True),.2,step=.05,label=a+' to '+c)
net='VM_SWITCHED'
for w in [3,2.5,2,1.8]:
 if route(net,anchor(net,point=(57.2375,94.8)),anchor(net,point=(90.2375,94.8)),w,step=.1,via_size=1.2,drill=.6,via_cost=35,rear_cost=1.3,label='main bus'):break
for net,a,c,widths in [('VLOGIC_IN','C101:1','C8:1',[1.5,1.2,1]),('VM_L','U2:6','U2:9',[2,1.8,1.5]),('VM_R','U4:9','U4:6',[2,1.8,1.5]),('VM_R','C131:1','J17:1',[2,1.8,1.5])]:
 for w in widths:
  if route(net,anchor(net,ref=a),anchor(net,ref=c),w,step=.1,via_size=1.2,drill=.6,via_cost=25,rear_cost=1.3,label=a+' to '+c):break
