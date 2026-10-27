from pathlib import Path
import hashlib,json,shutil
import pymupdf
OUT=Path(__file__).resolve().parent
BASE=Path('C:/Users/sc/Documents/Dev/Hardware/fpga/小梅哥ACG720国产高云FPGA教学开发板资料')
EXAMPLES=BASE/'02_例程源码/GW5AT60K'
chapter=next(EXAMPLES.glob('第28章*'))
manifest={}
for path in [chapter/'tft_ctrl.gprj',*sorted((chapter/'src').rglob('*'))]:
    if path.is_file():
        dest=OUT/'official-ch28'/path.relative_to(chapter)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest)
        manifest[str(path)]={'copy':str(dest.relative_to(OUT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
panels=BASE/'09_套餐配套模块资料/显示屏/4.3寸5寸800x480高清电容触摸屏'
selected=[next(panels.rglob('芯路恒TFT_V3.0电容触摸显示屏用户手册.pdf')),
          next(panels.rglob('WKS43189_SPEC_V0.0.pdf')),
          next(panels.rglob('裸屏规格书-40Pin标准RGB接口.pdf'))]
for idx,path in enumerate(selected):
    doc=pymupdf.open(path)
    text='\n\n'.join(f'PDF PAGE {i+1}\n'+p.get_text() for i,p in enumerate(doc))
    (OUT/f'panel-{idx}.txt').write_text(text,encoding='utf-8')
    manifest[str(path)]={'text':f'panel-{idx}.txt','pages':len(doc),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    print(idx,path.name,len(doc))
(OUT/'OFFICIAL-SOURCES.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
