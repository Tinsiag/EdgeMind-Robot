from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / '.local/framebuffer-first/ch38-camera-bars'
target = root / '.local/framebuffer-first/ch38-camera-live'
if not target.exists():
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('impl'))
rom = target / 'src/ov5640_init_table_rgb.v'
text = (source / 'src/ov5640_init_table_rgb.v').read_text(encoding='utf-8')
assert text.count("24'h503D_80") == 1
rom.write_text(text.replace("24'h503D_80", "24'h503D_00"), encoding='utf-8')
ctrl = target / 'src/ov5640_ctrl.v'
text = (source / 'src/ov5640_ctrl.v').read_text(encoding='utf-8')
assert text.count("default: verify_value=8'h80;") == 1
ctrl.write_text(text.replace("default: verify_value=8'h80;", "default: verify_value=8'h00;"), encoding='utf-8')
shutil.copy2(source / 'ch38_camera_bars.gprj', target / 'ch38_camera_live.gprj')
print('Prepared isolated live-frame project; this command does not create a hardware pass record')
