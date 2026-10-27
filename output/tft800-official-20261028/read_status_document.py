from pathlib import Path
import pymupdf
base=Path('C:/Users/sc/Documents/Dev/Hardware/fpga/小梅哥ACG720国产高云FPGA教学开发板资料')
paths=list((base/'05_配套软件和驱动/Programmer/doc/CN').glob('*UG718*.pdf'))
for path in paths:
 doc=pymupdf.open(path)
 for i,p in enumerate(doc):
  t=p.get_text()
  if ('状态寄存器' in t or 'Status Register' in t) and ('CRC' in t or 'DONE' in t or '位' in t):
   print('PAGE',i+1,path.name);print(t)
