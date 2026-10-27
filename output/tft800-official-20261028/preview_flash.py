from pathlib import Path
import json,subprocess,sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
b=json.loads((OUT/'build-evidence-final/result.json').read_text())
cmd=[sys.executable,'-X','utf8',str(ROOT/'scripts/fpga/program_flash.py'),'--bitstream',str(OUT/'build-evidence-final/a741.fs'),
     '--sha256',b['artifact_sha256'],'--log-dir',str(ROOT/'output/flash-tft800-20261028')]
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
(OUT/'FLASH-PREVIEW.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
assert r.returncode==0 and 'PREVIEW ONLY' in r.stdout
(OUT/'FLASH-COMMAND.json').write_text(json.dumps({'preview_command':cmd,'authorized':False,'program_command_if_authorized':cmd+['--program']},indent=2)+'\n')
print('PASS exact-hash Flash preview; no programmer launched')
