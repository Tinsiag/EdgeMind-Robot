from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
baseline = root / '.local/framebuffer-first/ch38-frame-test'
target = root / '.local/framebuffer-first/ch38-camera-bars'
if not target.exists():
    shutil.copytree(baseline, target, ignore=shutil.ignore_patterns('impl'))

def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)

# A separate CRC controller leaves the passed static comparison unchanged.
text = (root / 'rtl/framebuffer_frame_test.v').read_text()
text = replace_once(text, 'module framebuffer_frame_test', 'module framebuffer_camera_test')
text = replace_once(text, 'parameter UI_TIMEOUT_CYCLES = 100000000', 'parameter UI_TIMEOUT_CYCLES = 500000000')
text = replace_once(text, 'input source_valid,', '''input source_valid,
    input [15:0] source_pixel,
    input capture_good,
    output [31:0] source_crc,
    output [31:0] read_crc,''')
text = replace_once(text, 'reg [26:0] timeout_count;', '''localparam TIMEOUT_WIDTH = $clog2(UI_TIMEOUT_CYCLES + 1);
    reg [TIMEOUT_WIDTH-1:0] timeout_count;
    reg [31:0] source_crc_state, read_crc_state;
    (* ASYNC_REG = "TRUE" *) reg [1:0] capture_ui, capture_rd, input_done_rd;
    // The CRC bus is stable before capture_good is asserted at frame end.
    // Two-stage ready synchronizers establish a bundled-data handshake.
    assign source_crc = ~source_crc_state;
    assign read_crc = ~read_crc_state;
    function [31:0] crc16;
        input [31:0] previous_crc;
        input [15:0] pixel;
        reg [31:0] current_crc;
        reg [7:0] octet;
        integer byte_index, bit_index;
        begin
            current_crc = previous_crc;
            for (byte_index=0; byte_index<2; byte_index=byte_index+1) begin
                octet = byte_index == 0 ? pixel[15:8] : pixel[7:0];
                current_crc = current_crc ^ octet;
                for (bit_index=0; bit_index<8; bit_index=bit_index+1)
                    current_crc = current_crc[0] ?
                        (current_crc >> 1) ^ 32'hedb88320 : (current_crc >> 1);
            end
            crc16 = current_crc;
        end
    endfunction''')
text = replace_once(text, 'assign read_enable = write_frame_done && (reads < BLOCKS)', 'assign read_enable = write_frame_done && capture_ui[1] && (reads < BLOCKS)')
text = replace_once(text, 'assign read_pop = rd_cal[1] && rd_written[1] && !read_fifo_empty', 'assign read_pop = rd_cal[1] && rd_written[1] && capture_rd[1] && input_done_rd[1] && !read_fifo_empty')
text = text.replace('input_pixels <= 0;', "input_pixels <= 0; source_crc_state <= 32'hffffffff;")
text = replace_once(text, "input_pixels <= input_pixels + 1'b1;", "input_pixels <= input_pixels + 1'b1;\n                    source_crc_state <= crc16(source_crc_state, source_pixel);")
text = text.replace('done_ui <= 0;', 'done_ui <= 0; capture_ui <= 0;')
text = replace_once(text, 'done_ui <= {done_ui[0], compare_done};', 'done_ui <= {done_ui[0], compare_done};\n            capture_ui <= {capture_ui[0], capture_good};')
text = text.replace('rd_cal <= 0; rd_written <= 0;', "rd_cal <= 0; rd_written <= 0;\n            capture_rd <= 0; input_done_rd <= 0; read_crc_state <= 32'hffffffff;")
text = replace_once(text, 'rd_written <= {rd_written[0], write_frame_done};', 'rd_written <= {rd_written[0], write_frame_done};\n            capture_rd <= {capture_rd[0], capture_good};\n            input_done_rd <= {input_done_rd[0], input_frame_done};')
text = replace_once(text, 'if (!rd_cal[1]) begin', "if (!rd_cal[1]) begin\n                read_crc_state <= 32'hffffffff;")
start = text.index('                if (read_pixel != expected_pixel)')
end = text.index('                if (read_column == FRAME_WIDTH - 1)', start)
text = text[:start] + '''                read_crc_state <= crc16(read_crc_state, read_pixel);
                if (checked_pixels == PIXELS - 1 &&
                    crc16(read_crc_state, read_pixel) != source_crc_state)
                    compare_error <= 1;
''' + text[end:]
text = text.replace('// One-frame test controller for the official chapter 38 FIFO/DDR path.', '// Camera-frame CRC32 test of the passed chapter 38 FIFO/DDR path.')
(root / 'rtl/framebuffer_camera_test.v').write_text(text)
for name in ['framebuffer_camera_test.v', 'camera_frame_gate.v']:
    shutil.copy2(root / 'rtl' / name, target / 'src' / name)

camera_src = root / '.local/ch47/src/camera_init'
for name in ['sccb_master.v', 'ov5640_ctrl.v', 'ov5640_init_table_rgb.v']:
    source_file = camera_src / name if name == 'ov5640_init_table_rgb.v' else root / 'rtl/camera_init' / name
    shutil.copy2(source_file, target / 'src' / name)
shutil.copy2(root / '.local/ch47/src/DVP_Capture/DVP_Capture.v', target / 'src/DVP_Capture.v')
rom = (target / 'src/ov5640_init_table_rgb.v').read_text()
rom = replace_once(rom, "24'h503D_00", "24'h503D_80")
# Constant-only always @* has an empty Icarus sensitivity list. Address changes
# initialize the identical constant table in simulation as well as synthesis.
rom = replace_once(rom, 'always@(*) begin', 'always@(addr) begin')
# Preserve the previously working crop, PLL, HTS/VTS and format table.
# Width/height are parameters; do not infer frame rate from unknown oscillator.
(target / 'src/ov5640_init_table_rgb.v').write_text(rom)

ctrl = (target / 'src/ov5640_ctrl.v').read_text()
ctrl = replace_once(ctrl, 'ST_READ_B_LAUNCH=8, ST_READ_B_WAIT=9, ST_HALTED=10;', 'ST_READ_B_LAUNCH=8, ST_READ_B_WAIT=9, ST_HALTED=10,\n        ST_VERIFY_LAUNCH=11, ST_VERIFY_WAIT=12;')
ctrl = replace_once(ctrl, 'reg [7:0] rom_addr;', '''reg [7:0] rom_addr;
    reg [3:0] verify_index;
    function [15:0] verify_register;
        input [3:0] index;
        begin
            case(index)
                0: verify_register=16'h3808;
                1: verify_register=16'h3809;
                2: verify_register=16'h380a;
                3: verify_register=16'h380b;
                4: verify_register=16'h4300;
                5: verify_register=16'h501f;
                default: verify_register=16'h503d;
            endcase
        end
    endfunction
    function [7:0] verify_value;
        input [3:0] index;
        begin
            case(index)
                0: verify_value=(IMAGE_WIDTH >> 8);
                1: verify_value=IMAGE_WIDTH;
                2: verify_value=(IMAGE_HEIGHT >> 8);
                3: verify_value=IMAGE_HEIGHT;
                4: verify_value=8'h61;
                5: verify_value=8'h01;
                default: verify_value=8'h80;
            endcase
        end
    endfunction''')
ctrl = replace_once(ctrl, 'state == ST_READ_B_WAIT) &&', 'state == ST_READ_B_WAIT || state == ST_VERIFY_WAIT) &&')
assert ctrl.count('delay_count<=0; rom_addr<=0;') == 2
ctrl = ctrl.replace('delay_count<=0; rom_addr<=0;', 'delay_count<=0; rom_addr<=0; verify_index<=0;')
ctrl = replace_once(ctrl, 'init_done<=1; init_error<=0;', 'init_done<=0; init_error<=0;')
ctrl = replace_once(ctrl, 'init_busy<=0; state<=ST_HALTED;\n                    end\n                end\n\n                ST_HALTED:', '''if (xfer_ack_error || xfer_timeout || rd_data != 8'h40) begin
                            init_busy<=0; state<=ST_HALTED;
                        end else begin
                            verify_index<=0; state<=ST_VERIFY_LAUNCH;
                        end
                    end
                end
                ST_VERIFY_LAUNCH: begin
                    xfer_read<=1; xfer_reg<=verify_register(verify_index); xfer_data<=0;
                    wait_count<=0; state<=ST_VERIFY_WAIT;
                end
                ST_VERIFY_WAIT: begin
                    if (wait_count == 0) wait_count<=1;
                    if (xfer_done) begin
                        if (xfer_ack_error || xfer_timeout || rd_data != verify_value(verify_index)) begin
                            init_error<=1; init_busy<=0; state<=ST_HALTED;
                        end else if (verify_index == 6) begin
                            init_done<=1; init_busy<=0; state<=ST_HALTED;
                        end else begin
                            verify_index<=verify_index+1'b1; state<=ST_VERIFY_LAUNCH;
                        end
                    end
                end

                ST_HALTED:''')
(target / 'src/ov5640_ctrl.v').write_text(ctrl)

top = (baseline / 'src/uart_ddr3_tft_hdmi.v').read_text()
top = replace_once(top, 'output camera_reset_n, // Hold attached camera in reset during DDR-only test.', '''output camera_reset_n,
    inout camera_sclk, inout camera_sdat,
    input camera_vsync, input camera_href, input camera_pclk,
    input [7:0] camera_data,''')
top = replace_once(top, "assign camera_reset_n = 1'b0;", '''// Bring up camera only after the proven DDR baseline is calibrated.
  (* ASYNC_REG = "TRUE" *) reg [1:0] cal50;
  reg [20:0] camera_wait;
  reg camera_reset_reg, camera_enable;
  wire camera_init_done, camera_init_error;
  assign camera_reset_n = camera_reset_reg;
  always @(posedge clk50m or negedge reset_n) begin
    if (!reset_n) begin
      cal50 <= 0; camera_wait <= 0; camera_reset_reg <= 0; camera_enable <= 0;
    end else begin
      cal50 <= {cal50[0], ddr3_init_done};
      if (!cal50[1]) begin
        camera_wait <= 0; camera_reset_reg <= 0; camera_enable <= 0;
      end else if (!camera_reset_reg) begin
        if (camera_wait == 49999) begin camera_reset_reg <= 1; camera_wait <= 0; end
        else camera_wait <= camera_wait + 1'b1;
      end else if (!camera_enable) begin
        if (camera_wait == 999999) camera_enable <= 1;
        else camera_wait <= camera_wait + 1'b1;
      end
    end
  end
  ov5640_ctrl #(.CLK_HZ(50000000), .SCCB_HZ(100000),
    .IMAGE_WIDTH(DISP_WIDTH), .IMAGE_HEIGHT(DISP_HEIGHT)) camera_ctrl (
    .clk(clk50m), .rst_n(reset_n), .enable(camera_enable),
    .sccb_sda(camera_sdat), .sccb_scl(camera_sclk),
    .init_busy(), .init_done(camera_init_done), .init_error(camera_init_error),
    .last_read_id(), .table_index()
  );
  (* ASYNC_REG = "TRUE" *) reg [1:0] camera_ready_pclk;
  always @(posedge camera_pclk or negedge reset_n)
    if (!reset_n) camera_ready_pclk <= 0;
    else camera_ready_pclk <= {camera_ready_pclk[0], camera_init_done && ddr3_init_done};
  wire captured_valid, captured_hs, captured_vs;
  DVP_Capture capture (
    .Rst_n(reset_n && camera_ready_pclk[1]), .PCLK(camera_pclk),
    .Vsync(camera_vsync), .Href(camera_href), .Data(camera_data),
    .ImageState(), .DataValid(captured_valid), .DataPixel(image_data),
    .DataHs(captured_hs), .DataVs(captured_vs), .Xaddr(), .Yaddr()
  );
  wire capture_done, capture_good, geometry_error;
  wire [18:0] frame_pixels;
  wire [11:0] line_pixels;
  wire [10:0] frame_lines;
  camera_frame_gate #(.FRAME_WIDTH(DISP_WIDTH), .FRAME_HEIGHT(DISP_HEIGHT)) frame_gate (
    .clk(camera_pclk), .reset_n(reset_n), .ready(camera_ready_pclk[1]),
    .frame_active(captured_vs), .line_active(captured_hs), .pixel_valid(captured_valid),
    .source_valid(image_data_valid), .frame_done(capture_done), .frame_good(capture_good),
    .geometry_error(geometry_error), .frame_pixels(frame_pixels),
    .line_pixels(line_pixels), .frame_lines(frame_lines)
  );''')
top = replace_once(top, 'input_overflow | ui_test_error | test_timeout | compare_error;', 'input_overflow | ui_test_error | test_timeout | compare_error | camera_init_error | geometry_error;')
top = replace_once(top, 'input_frame_done, ddr3_init_done, pll_lock, pll_locked};', 'camera_init_done, ddr3_init_done, pll_lock, pll_locked};')
top = replace_once(top, 'framebuffer_frame_test #(', 'wire [31:0] source_crc, read_crc;\n  framebuffer_camera_test #(')
top = replace_once(top, '.reset_n(reset_n), .wr_clk(loc_clk50m), .ui_clk(test_ui_clk),', '.reset_n(reset_n), .wr_clk(camera_pclk), .ui_clk(test_ui_clk),')
top = replace_once(top, '.source_valid(image_data_valid), .write_fifo_full(wfifo_full),', '.source_valid(image_data_valid), .source_pixel(image_data),\n    .capture_good(capture_good), .source_crc(source_crc), .read_crc(read_crc),\n    .write_fifo_full(wfifo_full),')
start = top.index('generate\n')
end = top.index('  //TFT', start)
top = top[:start] + '// Official DVP_Capture now drives the passed write FIFO.\n' + top[end:]
top = replace_once(top, '.wr_clk(loc_clk50m)             ,', '.wr_clk(camera_pclk)             ,')
(target / 'src/uart_ddr3_tft_hdmi.v').write_text(top)

cst = (baseline / 'src/uart_ddr3_tft_hdmi.cst').read_text()
for name, ball in [('camera_sclk','B13'),('camera_sdat','D15'),('camera_vsync','C13'),
                   ('camera_href','D14'),('camera_pclk','B18')]+[
                   (f'camera_data[{i}]',b) for i,b in enumerate(['C15','B15','B16','D17','C17','E16','D16','B17'])]:
    pull = 'UP' if name in ['camera_sclk','camera_sdat'] else 'NONE'
    cst += f'\nIO_LOC "{name}" {ball};\nIO_PORT "{name}" IO_TYPE=LVCMOS33 PULL_MODE={pull} BANK_VCCIO=3.3;\n'
(target / 'src/uart_ddr3_tft_hdmi.cst').write_text(cst)
sdc = (baseline / 'src/ch38_frame_test.sdc').read_text()
sdc += '\n# Conservative 100 MHz PCLK constraint; oscillator frequency remains unmeasured.\ncreate_clock -name camera_pclk -period 10.000 [get_ports {camera_pclk}]\n'
(target / 'src/ch38_camera_bars.sdc').write_text(sdc)
tree = ET.parse(baseline / 'ch38_frame_test.gprj')
files = tree.find('FileList')
for el in list(files):
    if el.attrib['path'] in ['src/framebuffer_frame_test.v','src/ch38_frame_test.sdc']:
        files.remove(el)
for name in ['camera_frame_gate.v','framebuffer_camera_test.v','DVP_Capture.v',
             'sccb_master.v','ov5640_ctrl.v','ov5640_init_table_rgb.v']:
    ET.SubElement(files,'File',path=f'src/{name}',type='file.verilog',enable='1')
ET.SubElement(files,'File',path='src/ch38_camera_bars.sdc',type='file.sdc',enable='1')
tree.write(target / 'ch38_camera_bars.gprj',encoding='utf-8',xml_declaration=True)
print(f'Prepared {target}; passed static baseline unchanged')
