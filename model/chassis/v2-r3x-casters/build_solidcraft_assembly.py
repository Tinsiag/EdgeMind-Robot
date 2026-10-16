"""Insert the remaining exact STEP hardware into the editable SolidCraft base."""
from pathlib import Path
import json,sys
from solidcraft_workflow import MCP

HERE=Path(__file__).resolve().parent
sc=MCP(sys.argv[1])
try:
    assert not sc.call('inspect_design',{'measure':False,'sketches':False})['timeline']
    sc.call('open',{'path':str(HERE/'EdgeMind_Base.solidcraft')})
    sc.call('execute',{'command':'file.insert_step','params':{'path':str(HERE/'_assembly-input.step')},'verbose':False})
    state=sc.call('inspect_design',{'measure':False,'sketches':False})
    bad=[f for f in state['timeline'] if f.get('error') or f.get('warning')]
    assert not bad,bad
    expected=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    assert len(state['bodies'])==len(expected['parts']),(len(state['bodies']),len(expected['parts']))
    sc.call('save',{'path':str(HERE/'EdgeMind_Assembly.solidcraft')})
    (HERE/'solidcraft-assembly-verification.json').write_text(json.dumps({'backend':'SolidCraft 0.11.1 MCP',
        'body_count':len(state['bodies']),'timeline_warnings':bad,'state':state},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'assembly_saved':True,'bodies':len(state['bodies'])}),flush=True)
except Exception as error:
    (HERE/'solidcraft-assembly-verification.json').write_text(json.dumps({'assembly_saved':False,
        'error':str(error),'details':'See solidcraft-stderr.log. Full STEP and FreeCAD are the complete assembly deliverables.'},ensure_ascii=False,indent=2),encoding='utf-8')
    raise
finally:
    # Keep the base-building evidence in its original file.
    (HERE/'solidcraft-assembly-mcp-log.json').write_text(json.dumps(sc.log,ensure_ascii=False,indent=2),encoding='utf-8')
    sc.close()
