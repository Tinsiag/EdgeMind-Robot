"""Isolated placement comparison; reuses the verified lightweight netlist."""
from pathlib import Path
import hashlib,json,os,re,subprocess,time

root=Path(__file__).resolve().parent
path=root/'result.json'
record=json.loads(path.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(p)==h for p,h in record['source_sha256'].items())
assert sha(root/'impl/gwsynthesis/a741.vg')==record['synthesis_netlist_sha256']
started=time.time()
record.update(run_state='running',started_unix=started,pid=os.getpid())
path.write_text(json.dumps(record,indent=2),encoding='utf-8')
with (root/'build.log').open('w',encoding='utf-8') as log:
    with subprocess.Popen(['C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',str(root/'build.tcl')],cwd=root,stdout=log,stderr=subprocess.STDOUT) as proc:
        record['tool_pid']=proc.pid
        path.write_text(json.dumps(record,indent=2),encoding='utf-8')
        try:
            rc=proc.wait(timeout=10800)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait();rc=-1;record['timed_out']=True
        except KeyboardInterrupt:
            proc.terminate();proc.wait();rc=130;record['interrupted']=True
changed=any(sha(p)!=h for p,h in record['source_sha256'].items())
fs=root/'impl/pnr/a741.fs'
log=(root/'build.log').read_text(encoding='utf-8',errors='replace')
passed=rc==0 and not changed and fs.is_file() and fs.stat().st_mtime>=started and not re.search(r'^\s*(?:ERROR|FATAL)',log,re.M)
record.update(run_state='completed' if passed else 'failed',compile_passed=passed,returncode=rc,seconds=time.time()-started,sources_changed=changed)
if passed:
    record.update(artifact=str(fs),artifact_sha256=sha(fs))
tr=root/'impl/pnr/a741.tr'
if tr.is_file() and tr.stat().st_mtime>=started:
    text=tr.read_text(encoding='utf-8',errors='replace')
    record['timing_report_sha256']=sha(tr)
    record['timing_violations']={k.lower():int(v) for k,v in re.findall(r'<Numbers of (Setup|Hold|Recovery|Removal) Violated Endpoints>:(\d+)',text)}
path.write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='source_sha256'},indent=2),flush=True)
raise SystemExit(0 if passed else 1)
