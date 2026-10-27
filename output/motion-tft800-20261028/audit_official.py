"""Check board pinout and PLL parameters against read-only original examples."""
from pathlib import Path
import hashlib,json,re
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
P=ROOT/'code/camera-car-control/a741-fpga-fusion/.local/platform-basic-tft800'
original=ROOT/'output/tft800-official-20261028/official-ch28/src'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def parameters(p):return dict(re.findall(r'defparam\s+[^.]+\.(\w+)\s*=\s*([^;]+);',p.read_text(encoding='utf-8-sig')))
pll=parameters(original/'gowin_pll/gowin_pll_mod.v')
assert pll==parameters(P/'tft_gowin_pll_mod.v')
assert pll['FCLKIN']=='"50"' and pll['IDIV_SEL']=='2' and pll['FBDIV_SEL']=='1' and pll['MDIV_SEL']=='33' and pll['ODIV0_SEL']=='25'
renamed=[]
for rel in ('gowin_pll/gowin_pll.v','gowin_pll/gowin_pll_mod.v','pll_init.v'):
 text=(original/rel).read_text(encoding='utf-8-sig')
 for old,new in (('Gowin_PLL_MOD','A741_TFT_PLL_MOD'),('Gowin_PLL','A741_TFT_PLL'),('PLL_INIT','A741_TFT_PLL_INIT')):
  text=re.sub(r'\b'+old+r'\b',new,text)
 dest=P/('tft_'+Path(rel).name)
 assert text==dest.read_text(encoding='utf-8')
 renamed.append({'source':rel,'original_sha256':sha(original/rel),'prepared_sha256':sha(dest)})
pin=lambda p:dict(re.findall(r'IO_LOC "([^"]+)" (\w+);',p.read_text(encoding='utf-8-sig')))
official=pin(original/'tft_ctrl.cst');prepared=pin(P/'a741.cst')
matched={}
for signal,ball in official.items():
 if not signal.startswith('TFT_'):continue
 current=signal.lower().replace('tft_pwm','tft_bl').replace('tft_hs','tft_hsync').replace('tft_vs','tft_vsync')
 assert prepared[current]==ball,(current,ball)
 matched[current]=ball
assert len(matched)==21
result={'passed':True,'same_official_tft_pin_count':len(matched),'pins':matched,
        'pll_mhz':50/2*33/25,'pll_parameters_unchanged':True,'pll_init_renamed_only':True,'pll_files':renamed,
        'sample_edge_source':'WKS43189_SPEC_V0.0.pdf page12','geometry_source':'same PDF page4',
        'board_model_confirmed_by_marking':False,'user_selected_size':[800,480],
        'measured_active_area_approx_mm':[95,55],'diagonal_inches':(95**2+55**2)**.5/25.4}
(OUT/'OFFICIAL-REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS unchanged official33MHz PLL/init and all21 TFT pin assignments')
