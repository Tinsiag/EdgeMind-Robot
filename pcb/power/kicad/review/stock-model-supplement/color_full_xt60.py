"""Add AP214 presentation colors to the already aligned seven-solid full model."""
from pathlib import Path
import re

p=Path(__file__).with_name('AMASS_XT60PW-M_1x02_P7.20mm_Horizontal.step')
text=p.read_text(encoding='utf-8')
if 'COLOUR_RGB' not in text:
    ids=[int(v) for v in re.findall(r'#(\d+)\s*=',text)]
    solids=[int(v) for v in re.findall(r'#(\d+)\s*=\s*MANIFOLD_SOLID_BREP',text)]
    assert len(solids)==7
    context=int(re.search(r'#(\d+)\s*=\s*\(\s*GEOMETRIC_REPRESENTATION_CONTEXT\(3\)',text).group(1))
    serial=max(ids);lines=[]
    def entity(code):
        global serial
        serial+=1;lines.append(f'#{serial} = {code};');return serial
    styled=[]
    for i,solid in enumerate(solids):
        rgb=(0.90,0.66,0.015) if i==6 else (0.68,0.72,0.82)
        color=entity("COLOUR_RGB('',"+','.join(map(str,rgb))+")")
        fill=entity(f"FILL_AREA_STYLE_COLOUR('',#{color})")
        area=entity(f"FILL_AREA_STYLE('',(#{fill}))")
        surface=entity(f'SURFACE_STYLE_FILL_AREA(#{area})')
        side=entity(f"SURFACE_SIDE_STYLE('',(#{surface}))")
        use=entity(f'SURFACE_STYLE_USAGE(.BOTH.,#{side})')
        assign=entity(f'PRESENTATION_STYLE_ASSIGNMENT((#{use}))')
        styled.append(entity(f"STYLED_ITEM('',(#{assign}),#{solid})"))
    entity("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',("+','.join('#'+str(v) for v in styled)+f'),#{context})')
    end=text.rfind('ENDSEC;')
    text=text[:end]+'\n'.join(lines)+'\n'+text[end:]
    p.write_text(text,encoding='utf-8')
print('Colored full XT60 model:',p)
