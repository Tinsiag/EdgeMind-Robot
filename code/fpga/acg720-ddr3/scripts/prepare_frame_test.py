from pathlib import Path
import shutil, xml.etree.ElementTree as ET, difflib, hashlib, json

project_root = Path(__file__).resolve().parents[1]
base = project_root / '.local/framebuffer-first'
ref = base / 'official-ch38'
work = base / 'ch38-frame-test'
if not work.exists():
    shutil.copytree(ref, work, ignore=shutil.ignore_patterns('impl'))

def change(text, old, new):
    assert text.count(old) == 1, ('Expected one occurrence', old, text.count(old))
    return text.replace(old,new)

p = ref / 'src/uart_ddr3_tft_hdmi.v'
s = p.read_text(encoding='utf-8-sig')
s = change(s,'parameter USE_TEST_DATA = "FALSE"','parameter USE_TEST_DATA = "TRUE"')
s = change(s,'output [2:0]    led','output [7:0]    led')
s = change(s,'    //TFT Interface','    output camera_reset_n, // Hold attached camera in reset during DDR-only test.\n    //TFT Interface')
s = change(s,'  assign led        = {frame_rx_done_flip,ddr3_init_done,pll_locked};','''  assign camera_reset_n = 1'b0;
  reg [24:0] heartbeat = 0;
  always @(posedge clk50m or negedge reset_n)
    if (!reset_n) heartbeat <= 0;
    else heartbeat <= heartbeat + 1'b1;
  wire any_test_error = input_overflow | ui_test_error | test_timeout | compare_error;
  assign led = {heartbeat[24], any_test_error,
                (compare_pass && !any_test_error), write_frame_done,
                input_frame_done, ddr3_init_done, pll_lock, pll_locked};

  wire wfifo_full, rfifo_empty;
  wire test_ui_clk, test_ui_reset, write_fire, read_fire, read_data_valid;
  wire [27:0] command_address;
  wire read_enable, input_frame_done, input_overflow;
  wire write_frame_done, ui_test_error, test_timeout;
  wire compare_done, compare_error, compare_pass;
  wire [18:0] checked_pixels, first_error_pixel;
  wire [15:0] first_error_expected, first_error_actual;
  framebuffer_frame_test #(
    .FRAME_WIDTH(DISP_WIDTH), .FRAME_HEIGHT(DISP_HEIGHT)
  ) frame_test (
    .reset_n(reset_n), .wr_clk(loc_clk50m), .ui_clk(test_ui_clk),
    .rd_clk(clk_disp), .ui_reset(test_ui_reset), .calibrated(ddr3_init_done),
    .source_valid(image_data_valid), .write_fifo_full(wfifo_full),
    .write_enable(wrfifo_wren), .input_frame_done(input_frame_done),
    .input_overflow(input_overflow), .write_fire(write_fire), .read_fire(read_fire),
    .command_address(command_address), .read_data_valid(read_data_valid),
    .read_enable(read_enable), .write_frame_done(write_frame_done),
    .ui_error(ui_test_error), .timeout_error(test_timeout),
    .read_fifo_empty(rfifo_empty), .read_pixel(rdfifo_dout),
    .read_pop(rdfifo_rden), .compare_done(compare_done),
    .compare_error(compare_error), .compare_pass(compare_pass),
    .checked_pixels(checked_pixels), .first_error_pixel(first_error_pixel),
    .first_error_expected(first_error_expected), .first_error_actual(first_error_actual)
  );''')
s = change(s,'.DataReq     (rdfifo_rden    )','.DataReq     (               )')
s = change(s,'    assign wrfifo_wren = image_data_valid;','    // wrfifo_wren is limited to exactly one frame by frame_test.')
s = change(s,"    reg  pll_lock_r;\n    reg  pll_lock_rr;",'''    reg [15:0] pll_lock_reg = 16'b0;
    wire pll_mdrp_ready = pll_lock_reg[15];''')
s = change(s,".pll_init_bypass(1'b0)",'.pll_init_bypass(pll_mdrp_ready)')
s = change(s,'''    always@(posedge clk50m)begin
        pll_lock_r <= pll_lock;
        pll_lock_rr <= pll_lock_r;
    end''','''    always @(posedge clk50m or negedge reset_n) begin
        if (!reset_n) pll_lock_reg <= 0;
        else pll_lock_reg <= {pll_lock_reg[14:0], pll_lock};
    end''')
s = change(s,'''    always@(posedge clk50m)
        pll_stop_r <= pll_stop;''','''    always @(posedge clk50m or negedge reset_n)
        if (!reset_n) pll_stop_r <= 0;
        else pll_stop_r <= pll_stop;''')
s = s.replace('pll_lock_rr','pll_mdrp_ready')
s = change(s,'''    always@(posedge clk50m)
    if(!pll_mdrp_ready)''','''    always @(posedge clk50m or negedge reset_n)
    if (!reset_n)
        wr <= 1'b0;
    else if(!pll_mdrp_ready)''')
# There is already an earlier wire pll_stop in the vendor top.
s = change(s,'    wire pll_stop;     \n','')
s = change(s,'.rd_load()','.rd_load(1\'b0)')
s = change(s,'.wr_load()','.wr_load(1\'b0)')
s = change(s,'''        .rfifo_dout(rdfifo_dout)''','''        .wrfifo_full(wfifo_full),
        .rdfifo_empty(rfifo_empty),
        .read_enable(read_enable),
        .monitor_ui_clk(test_ui_clk), .monitor_ui_reset(test_ui_reset),
        .monitor_write_fire(write_fire), .monitor_read_fire(read_fire),
        .monitor_read_valid(read_data_valid), .monitor_addr(command_address),
        .rfifo_dout(rdfifo_dout)''')
(work/'src/uart_ddr3_tft_hdmi.v').write_text(s,encoding='utf-8')

p = ref/'src/ddr3_ctrl_2port/ddr3_ctrl_2port.v'
s = p.read_text(encoding='utf-8-sig')
s = change(s,'    //DDR3   ','    input read_enable,\n    output monitor_ui_clk, monitor_ui_reset,\n    output monitor_write_fire, monitor_read_fire, monitor_read_valid,\n    output [27:0] monitor_addr,\n    //DDR3   ')
s = change(s,'    fifo_ddr3_adapter fifo_ddr3_adapter(','''    assign monitor_ui_clk = ui_clk;
    assign monitor_ui_reset = ui_clk_sync_rst;
    assign monitor_write_fire = app_en && app_rdy && app_wdf_rdy && app_cmd == 0;
    assign monitor_read_fire = app_en && app_rdy && app_cmd == 1;
    assign monitor_read_valid = app_rd_data_valid;
    assign monitor_addr = app_addr;
    fifo_ddr3_adapter fifo_ddr3_adapter(''')
s = change(s,'.rst_n(sys_rst_n)               ,','.rst_n(sys_rst_n & ~ui_clk_sync_rst),')
s = change(s,'       .rd_load(rd_load)','       .read_enable(read_enable),\n       .rd_load(rd_load)')
(work/'src/ddr3_ctrl_2port/ddr3_ctrl_2port.v').write_text(s,encoding='utf-8')

p = ref/'src/ddr3_ctrl_2port/fifo_ddr3_adapter.v'
s = p.read_text(encoding='utf-8-sig')
s = change(s,'    //用户接口','    input read_enable, // Static frame must be fully written before reads.\n    //用户接口')
s = change(s,'else if((rfifo_wcount <= rd_bust_len_a) )begin','else if(read_enable && (rfifo_wcount <= rd_bust_len_a))begin')
# Remove duplicate declarations; these have no behavior.
lines=s.splitlines(True);seen=set();clean=[]
for line in lines:
    stripped=line.strip().split('//')[0].strip()
    if stripped in ('reg         wr_rst      ;','reg rd_rst_h;'):
        if stripped in seen:continue
        seen.add(stripped)
    # Different spacing in the two vendor rd_rst_h declarations.
    if stripped == 'reg         rd_rst_h    ;':seen.add('reg rd_rst_h;')
    clean.append(line)
(work/'src/ddr3_ctrl_2port/fifo_ddr3_adapter.v').write_text(''.join(clean),encoding='utf-8')

shutil.copyfile(project_root/'rtl/framebuffer_frame_test.v',work/'src/framebuffer_frame_test.v')
# Isolation found both original FIFO implementations fail RP0007 on 1.9.12.
# Use the already compiled official chapter 47 implementations of identical
# configuration and capacity. Do not change PLL initialization or test ROM logic.
for f in ('src/pll_init.v','src/test_dat_gen/test_dat_gen.v'):
    shutil.copyfile(ref/f,work/f)
fifo_manifest={}
for name in ('rd_data_fifo','wr_data_fifo'):
    donor=project_root/'.local/ch47/src'/name
    recipient=ref/'src'/name
    for f in (f'{name}.ipc','temp/FIFO/fifo_parameter.v','temp/FIFO/fifo_define.v'):
        assert (donor/f).read_bytes()==(recipient/f).read_bytes(), ('FIFO config differs',name,f)
    f=f'{name}.v'
    shutil.copyfile(donor/f,work/'src'/name/f)
    fifo_manifest[name]={'source':str(donor/f),
        'sha256':hashlib.sha256((donor/f).read_bytes()).hexdigest(),
        'original_ch38_sha256':hashlib.sha256((recipient/f).read_bytes()).hexdigest()}
(work/'fifo-compatibility.json').write_text(json.dumps(fifo_manifest,indent=2),encoding='utf-8')
cst=(ref/'src/uart_ddr3_tft_hdmi.cst').read_text(encoding='utf-8-sig')
cst=cst.replace('IO_LOC "uart_rx_flag" K21;','').replace('IO_PORT "uart_rx_flag" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;','')
for pin,ball in [(3,'K21'),(4,'K22'),(5,'J22'),(6,'H22'),(7,'M21')]:
    cst+=f'\nIO_LOC "led[{pin}]" {ball};\nIO_PORT "led[{pin}]" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;\n'
cst+='\nIO_LOC "camera_reset_n" C14;\nIO_PORT "camera_reset_n" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;\n'
(work/'src/uart_ddr3_tft_hdmi.cst').write_text(cst,encoding='utf-8')
# uart_rx_flag is no longer used and should not become an unconstrained output.
top=(work/'src/uart_ddr3_tft_hdmi.v').read_text(encoding='utf-8')
top=top.replace('    output  uart_rx_flag,','').replace('  assign uart_rx_flag = uart_rx;','')
(work/'src/uart_ddr3_tft_hdmi.v').write_text(top,encoding='utf-8')
(work/'src/ch38_frame_test.sdc').write_text('''create_clock -name clk50m -period 20.000 [get_ports {clk50m}]
create_generated_clock -name pixel33m -source [get_ports {clk50m}] -multiply_by 33 -divide_by 50 [get_pins {u_clkdiv/CLKOUT}]
create_generated_clock -name ddr_ui100m -source [get_ports {clk50m}] -multiply_by 2 [get_pins {ddr3_ctrl_2port/DDR3_Memory_Interface_Top/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]
''',encoding='ascii')
tree=ET.parse(ref/'uart_ddr3_tft_hdmi.gprj')
fl=tree.getroot().find('FileList')
for f in fl:
    if f.attrib['type']=='file.gao':f.set('enable','0')
ET.SubElement(fl,'File',path='src/framebuffer_frame_test.v',type='file.verilog',enable='1')
ET.SubElement(fl,'File',path='src/ch38_frame_test.sdc',type='file.sdc',enable='1')
tree.write(work/'ch38_frame_test.gprj',encoding='utf-8',xml_declaration=True)

patch=[]
for p in ref.rglob('*'):
    q=work/p.relative_to(ref)
    if p.is_file() and q.exists() and p.suffix in ('.v','.cst') and p.read_bytes()!=q.read_bytes() and b'begin_protected' not in p.read_bytes():
        patch += difflib.unified_diff(p.read_text(encoding='utf-8',errors='replace').splitlines(True),
                   q.read_text(encoding='utf-8',errors='replace').splitlines(True),
                   fromfile='official-ch38/'+p.relative_to(ref).as_posix(),
                   tofile='ch38-frame-test/'+q.relative_to(work).as_posix())
(work/'frame-test.patch').write_text(''.join(patch),encoding='utf-8')
hashes={p.relative_to(ref).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ref.rglob('*') if p.is_file()}
(work/'reference-sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print('Prepared',work)
