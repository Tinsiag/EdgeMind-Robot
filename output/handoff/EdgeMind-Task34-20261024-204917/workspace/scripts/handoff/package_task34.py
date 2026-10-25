"""Snapshot task 3/4 sources, CAD inputs and diagnostic evidence; never run hardware."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,shutil,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[2]
FUSION=ROOT/'code/camera-car-control/a741-fpga-fusion'
stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
DEST=ROOT/'output/handoff'/('EdgeMind-Task34-'+stamp)
DEST.mkdir(parents=True,exist_ok=False)

def copy(source,relative):
    target=DEST/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)

def acceptable(path):
    parts={p.lower() for p in path.parts}
    if parts&{'.git','.venv','node_modules','__pycache__','release'}:return False
    name=path.name.lower()
    if name.startswith('.env') or name in {'api-key.txt','id_rsa','id_ed25519'}:return False
    if path.suffix.lower() in {'.fs','.bin','.vvp','.pyc','.key','.fcbak','.fcstd','.glb'}:return False
    if name in {'preview-meshes.json','查看模型.html'}:return False
    return True

files=set(filter(None,subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')))
prefixes=('code/camera-car-control/','code/fpga/','scripts/fpga/','scripts/handoff/',
          'model/chassis/v4-lidar-imu/','model/chassis/v5-rgb-touch-display/')
single={'AGENTS.md','README.md','.gitattributes','.gitignore','model/README.md','model/chassis/README.md',
        'doc/自主导航方案调研_2026-10-24.md','doc/项目功能需求书.md'}
for rel in sorted(files):
    path=ROOT/rel
    if path.is_file() and acceptable(Path(rel)) and (rel.startswith(prefixes) or rel in single):
        copy(path,Path('workspace')/rel)

# Include pinned third-party source even when it is a Git submodule/ignored cache.
for folder in (ROOT/'code/camera-car-control/third_party/verilog-ethernet',FUSION/'third_party'):
    for path in folder.rglob('*'):
        if path.is_file() and acceptable(path.relative_to(ROOT)):
            copy(path,Path('workspace')/path.relative_to(ROOT))

# Original, already downloaded vendor archives required by prepare/build.
examples=ROOT/'code/camera-car-control/.local/environment/examples/GW5AT60K'
for path in examples.rglob('*.zip'):
    copy(path,Path('workspace')/path.relative_to(ROOT))
for folder in (ROOT/'code/camera-car-control/.local/platform',FUSION/'.local/platform-tft480',
               FUSION/'.local/platform-motion-lidar',FUSION/'.local/vendor',FUSION/'.local/mapping'):
    if folder.is_dir():
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix.lower() not in {'.obj','.o','.exe','.pdb','.lib'}:
                copy(path,Path('workspace')/path.relative_to(ROOT))

# Keep diagnostics separate from deployable source. No bitstreams or stale netlists.
for folder in (FUSION/'.local/tests',FUSION/'.local/gowin-fusion-tft480',
               FUSION/'.local/gowin-fusion-tft480-synth',FUSION/'.local/timing-units',
               FUSION/'.local/routing-stopped-20261024-1909'):
    if not folder.is_dir():continue
    for path in folder.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.log','.json','.txt','.html','.xml','.tcl','.sdc','.gprj'}:
            copy(path,Path('evidence')/path.relative_to(FUSION/'.local'))

for index,name in enumerate(('bbc93b42-54ee-4c7d-b9e5-d8907ceb075b','f5e5235f-b38d-4960-94b4-6f0715d312b7'),1):
    source=Path('C:/Users/sc/AppData/Local/Temp')/('codex-clipboard-'+name+'.png')
    if source.is_file():copy(source,Path('requirements')/('user-requirements-'+str(index)+'.png'))

git=DEST/'git';git.mkdir()
for name,command in [('status.txt',['git','status','--short']),('HEAD.txt',['git','rev-parse','HEAD']),
                     ('working-tree.patch',['git','diff','--binary','HEAD'])]:
    (git/name).write_bytes(subprocess.check_output(command,cwd=ROOT))
copy(FUSION/'verification/AI-HANDOFF-20261024.md',Path('README_FIRST.md'))
(DEST/'PACKAGE-NOTES.md').write_text('''# 交接包说明

先读README_FIRST.md。用户已暂停；包内没有本轮可交付位流，不得直接烧录旧产物。

workspace/为当前源代码与必要依赖快照，保留原仓库相对目录。包含厂家38/47/59章原始例程ZIP、生成的平台源文件、V4/V5完整STEP及几何核对输入。

evidence/为历史及中断诊断，不是当前整板签核。最后完整48组测试记录对应较早输入；之后49组回归与仅综合被人工停止。单项日志可能混合时刻，必须重新验证源码哈希。

git/保留原HEAD身份、状态和全部已跟踪工作区差异；已有用户修改不等于全部由本轮AI产生。workspace/同时收录所需未跟踪文件，不仅是patch。

没有复制.git数据库、Python虚拟环境、系统/WSL/Gowin安装目录、密钥、旧release位流、仿真可执行文件、旧网表。CAD重复预览网格/HTML/GLB和FreeCAD容器未收录；完整STEP、参数、验证报告和建模脚本已收录。当前任务是读取导航几何，原仓库仍保留全部模型。

在本机原工作区继续最直接。若独立解压，先配置对应工具与Python依赖；编译和仿真保持相对目录。报告脚本中git show HEAD的基线比较需要原仓库Git历史。不要直接覆盖更新过的目录，应先比较差异。

CONTENTS-SHA256.json记录包内每个文件的路径、大小、SHA-256和时间。压缩包另有外部.sha256文件。
''',encoding='utf-8')

records=[]
for path in sorted(DEST.rglob('*')):
    if path.is_file():
        records.append({'path':path.relative_to(DEST).as_posix(),'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'mtime_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()})
(DEST/'CONTENTS-SHA256.json').write_text(json.dumps({'created_beijing':stamp,'files':records},ensure_ascii=False,indent=2),encoding='utf-8')
archive=DEST.with_suffix('.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in sorted(DEST.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(DEST).as_posix())
with zipfile.ZipFile(archive) as z:
    bad=z.testzip()
    if bad:raise RuntimeError('Archive CRC failed: '+bad)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
print(json.dumps({'folder':str(DEST),'zip':str(archive),'bytes':archive.stat().st_size,
                  'sha256':digest,'files':len(records)+1,'crc_verified':True},ensure_ascii=False,indent=2))
