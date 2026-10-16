"""Build the thicker base and raised battery fence through SolidCraft's stdio MCP.

Usage: FreeCAD's python.exe solidcraft_workflow.py <solidcraft-cli.exe>
Runs in a fresh private headless session and never changes an open app document.
"""
from pathlib import Path
import json,subprocess,threading,queue,sys,time

HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))

class MCP:
    def __init__(self,exe):
        self.log=[];self.number=0;self.q=queue.Queue()
        self.err=(HERE/'solidcraft-stderr.log').open('w',encoding='utf-8')
        self.proc=subprocess.Popen([exe,'mcp','--allow-path',str(HERE)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=self.err,text=True,encoding='utf-8',bufsize=1)
        def read():
            for line in self.proc.stdout:
                try:self.q.put(json.loads(line))
                except ValueError:self.q.put({'error':line})
            self.q.put({'error':'SolidCraft MCP exited before replying; see solidcraft-stderr.log'})
        threading.Thread(target=read,daemon=True).start()
        self.rpc('initialize',{'protocolVersion':'2025-06-18','capabilities':{},
            'clientInfo':{'name':'EdgeMind CAD','version':'2'}})
        self.proc.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n');self.proc.stdin.flush()
    def rpc(self,method,params):
        self.number+=1
        request={'jsonrpc':'2.0','id':self.number,'method':method,'params':params}
        self.proc.stdin.write(json.dumps(request)+'\n');self.proc.stdin.flush()
        response=self.q.get(timeout=240)
        self.log.append({'request':request,'response':response})
        if 'error' in response:raise RuntimeError(response['error'])
        return response['result']
    def call(self,name,arguments):
        r=self.rpc('tools/call',{'name':name,'arguments':arguments})
        if r.get('isError'):raise RuntimeError(r)
        texts=[c['text'] for c in r.get('content',[]) if c['type']=='text']
        if texts:
            try:return json.loads(texts[0])
            except ValueError:return texts[0]
        return r
    def close(self):
        self.proc.stdin.close()
        try:self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:self.proc.terminate()
        self.err.close()

def command(identifier,**params):return {'command':identifier,'params':params}

def build(exe):
    sc=MCP(exe)
    try:
        initial=sc.call('inspect_design',{'measure':False,'sketches':False})
        assert not initial['timeline']
        cmds=[]
        for name,val,comment in [
            ('base_w',P['body_width'],'180 mm layout reference; edit mounts when changing width'),
            ('base_l',P['body_length'],'260 mm layout reference; edit mounts when changing length'),
            ('base_t',P['lower_plate_thickness'],'4 to 6 mm; uncut flat floor under the battery'),
            ('base_z',P['lower_deck_bottom_z'],'Fixed by source rear motor brackets and wheel contact'),
            ('pocket_w',P['battery_width']+2*P['battery_clearance_each_side'],'49 mm; 47 mm battery plus 1 mm per side'),
            ('pocket_l',P['battery_length']+2*P['battery_clearance_each_side'],'87 mm; 85 mm battery plus 1 mm per side'),
            ('pocket_y',P['battery_centre_y'],'Battery pocket centre Y, fixed at 35 mm for this layout'),
            ('guard_h',P['battery_guard_height'],'2 to 6 mm above the floor; battery thickness not assumed'),
            ('guard_wall',P['battery_guard_wall'],'1.5 to 3 mm perimeter wall')]:
            cmds.append(command('parameters.add',name=name,expression=str(val)+' mm',comment=comment))
        cmds += [command('solid.box',length='base_w',width='base_l',height='base_t',corner=['-base_w/2','-base_l/2','base_z'],
                         operation='new',name='BaseBlank',body_name='LowerDeck'),
                 command('solid.chamfer',edges=[[-90,-130,P['lower_deck_bottom_z']+2],[90,-130,P['lower_deck_bottom_z']+2]],distance=20,name='FrontCorners'),
                 command('solid.chamfer',edges=[[-90,130,P['lower_deck_bottom_z']+2],[90,130,P['lower_deck_bottom_z']+2]],distance=12,name='RearCorners')]
        (HERE/'solidcraft-build.json').write_text(json.dumps({'commands':cmds},indent=2))
        sc.call('batch',{'commands':cmds,'verbose':False})
        print('SolidCraft base blank built',flush=True)
        stages=[sc.call('measure',{})]
        cuts=[]
        for name,x,y,dx,dy in [
            ('BatteryFenceLeft','-pocket_w/2-guard_wall','pocket_y-pocket_l/2-guard_wall','guard_wall','pocket_l+2*guard_wall'),
            ('BatteryFenceRight','pocket_w/2','pocket_y-pocket_l/2-guard_wall','guard_wall','pocket_l+2*guard_wall'),
            ('BatteryFenceFront','-pocket_w/2','pocket_y-pocket_l/2-guard_wall','pocket_w','guard_wall'),
            ('BatteryFenceRear','-pocket_w/2','pocket_y+pocket_l/2','pocket_w','guard_wall')]:
            cuts.append(command('solid.box',length=dx,width=dy,height='guard_h + .5 mm',
                corner=[x,y,'base_z+base_t-.5 mm'],operation='join',targets=['LowerDeck'],name=name))
        for sx in (-1,1):
            for y in P['tie_slot_y']:
                cuts.append(command('solid.box',length=P['tie_slot_width'],width=P['tie_slot_length'],height='base_t+2 mm',
                    corner=[sx*P['tie_slot_x']-P['tie_slot_width']/2,y-P['tie_slot_length']/2,'base_z-1 mm'],
                    operation='cut',targets=['LowerDeck'],name='CableTie'+str(sx)+str(int(y))))
        # Actual motor-bracket foot holes are measured from the supplied source.
        reference=json.loads((HERE/'reference-extraction.json').read_text(encoding='utf-8'))
        holes=[(x,y,1.7) for x,y,r in reference['rear_bracket_mount_holes_xy_radius']]
        holes += [(x,y,1.7) for x in (-76,76) for y in (-111,114)]
        holes += [(sx*P['caster_pivot_x']+dx,P['caster_pivot_y']+dy,1.7)
                  for sx in (-1,1) for dx in (-15,15) for dy in (-12,12)]
        # The power-board holes match the unchanged source PCB in the assembly.
        old=json.loads((HERE.parent/'v1-fixed-front-wheels/verification.json').read_text(encoding='utf-8'))
        holes += [(x-49.992,y+P['power_board_centre_y']+25,1.7) for x,y,r in old['power_pcb_holes_from_step']]
        for i,(x,y,r) in enumerate(holes):
            cuts.append(command('solid.cylinder',radius=r,height='base_t+2 mm',base=[x,y,'base_z-1 mm'],
                operation='cut',targets=['LowerDeck'],name='MountHole'+str(i+1)))
        sc.call('batch',{'commands':cuts,'verbose':False})
        cmds+=cuts
        (HERE/'solidcraft-build.json').write_text(json.dumps({'commands':cmds},indent=2))
        stages.append(sc.call('measure',{}))
        state=sc.call('inspect_design',{'measure':True,'sketches':True})
        assert not any(f.get('error') or f.get('warning') for f in state['timeline']),state['timeline']
        # Exercise supported thickness and fence-height endpoints and return to nominal.
        walk=[]
        for name,val in [('base_t',6),('guard_h',6),('guard_h',2),('guard_h',3),('base_t',4)]:
            changed=sc.call('set_parameter',{'name':name,'value':str(val)+' mm'})
            assert not changed.get('errors'),changed
            walk.append({'name':name,'value':val,'measure':sc.call('measure',{})})
        sc.call('save',{'path':str(HERE/'EdgeMind_Base.solidcraft')})
        sc.call('export',{'path':str(HERE/'SolidCraft_LowerDeck.step'),'bodies':['LowerDeck']})
        sc.call('screenshot',{'path':str(HERE/'preview-solidcraft-base.png'),'source':'model','view':'top','width':1100,'height':900})
        (HERE/'solidcraft-verification.json').write_text(json.dumps({'initial_empty':True,'backend':'SolidCraft 0.11.1 MCP headless',
            'stages':stages,'parameter_walk':walk,'final':state,'warnings':[]},ensure_ascii=False,indent=2),encoding='utf-8')
        print('SolidCraft base saved and exported',flush=True)
    finally:
        (HERE/'solidcraft-mcp-log.json').write_text(json.dumps(sc.log,ensure_ascii=False,indent=2),encoding='utf-8')
        sc.close()

if __name__=='__main__':build(sys.argv[1])
