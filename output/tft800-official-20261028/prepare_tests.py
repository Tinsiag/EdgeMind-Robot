from pathlib import Path
import shutil
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]/'code/camera-car-control/a741-fpga-fusion'
ref=ROOT/'display/reference/acg720-ch28';ref.mkdir(parents=True,exist_ok=True)
for name in ('disp_driver.v','disp_parameter_cfg.v'):
    shutil.copy2(OUT/'official-ch28/src'/name,ref/name)
text=(ROOT/'tests/camera_tft_tb.v').read_text(encoding='utf-8')
text=text.replace('camera_tft_tb','camera_tft800_tb').replace('480x272','800x480')
text=text.replace('reg ui_clk=0;', 'reg disp_clk=0;always #15.151515 disp_clk=~disp_clk;\n reg ui_clk=0;')
text=text.replace('a741_video #(.SKIP_FRAMES(0)) video(.clk(clk)', 'a741_video #(.WIDTH(800),.HEIGHT(480),.SKIP_FRAMES(0)) video(.clk(disp_clk)')
text=text.replace('a741_osd overlay(.clk(clk)', 'a741_osd #(.WIDTH(800),.HEIGHT(480),.PIPELINED(1)) overlay(.clk(disp_clk)')
text=text.replace('.status_snapshot(snapshot),.status_update(1\'b1),.fusion_snapshot(fusion_snapshot)', '.status_snapshot(display_snapshot),.status_update(display_update),.fusion_snapshot(display_fusion)')
text=text.replace('a741_tft480_panel #(.BACKLIGHT_FRAMES(1)) panel(.*);', '''wire [895:0] display_snapshot;wire [255:0] display_fusion;wire display_update;
 wire [35:0] system_display_status;
 a741_display_cdc display_cdc(.sys_clk(clk),.sys_rst_n(rst_n),.disp_clk(disp_clk),.disp_rst_n(rst_n),
  .status_snapshot(snapshot),.fusion_snapshot(fusion_snapshot),.system_flags(6'b110011),
  .display_status({available,camera_error,ddr_error,overflow,frames}),.display_snapshot(display_snapshot),
  .display_fusion(display_fusion),.display_flags(),.display_update(display_update),.system_display_status(system_display_status));
 a741_tft800_panel #(.BACKLIGHT_FRAMES(1)) panel(.clk(disp_clk),.*);''')
text=text.replace('memory[0:32767]', 'memory[0:131071]').replace('[14:0] word_index={app_addr[20],app_addr[16:3]}', '[16:0] word_index={app_addr[20],app_addr[18:3]}').replace('[14:0] write_index,read_index', '[16:0] write_index,read_index')
text=text.replace('row<272','row<480').replace('column<480','column<800')
text=text.replace('.ddr_ready(available),.frame_ready(available),.camera_error(camera_error),.ddr_error(ddr_error),.video_overflow(overflow),.video_frames(frames)', '.ddr_ready(system_display_status[35]),.frame_ready(system_display_status[35]),.camera_error(system_display_status[34]),.ddr_error(system_display_status[33]),.video_overflow(system_display_status[32]),.video_frames(system_display_status[31:0])')
text=text.replace('x>=48 && x<432', 'x>=208 && x<592').replace('y>=232 && y<264','y>=440 && y<472')
start=text.index(' reg selected_text;')
end=text.index(' integer frame_file=0;',start)
text=text[:start]+''' reg selected_text;
 reg [10:0] px0,py0,px1,py1;reg text0,text1,valid0,valid1;
 always @(posedge disp_clk) if(rst_n) begin
  px0<=x;py0<=y;px1<=px0;py1<=py0;px<=px1;py<=py1;
  text0<=in_text;text1<=text0;selected_text<=text1;
  valid0<=pixel_request && available && scan_frames>=3;valid1<=valid0;check_pixel<=valid1;
  if(pixel_request && available && scan_frames>=3 && !pixel_valid) $fatal(1,"800 DDR underrun %d,%d",x,y);
  if(frame_blank) begin scan_frames=scan_frames+1;tag_seen=0;end
 end
'''+text[end:]
text=text.replace('480 272', '800 480').replace('camera-tft.ppm', 'camera-tft800.ppm')
text=text.replace('always @(negedge tft_clk)', 'always @(posedge tft_clk)')
text=text.replace('scan_frames==2 && frame_file', 'scan_frames==4 && frame_file')
text=text.replace('wait(scan_frames==2)', 'wait(scan_frames==4)').replace('wait(scan_frames==3)', 'wait(scan_frames==5)')
text=text.replace('correct_pixels<180000', 'correct_pixels<650000').replace('writes<16320 || reads<16320','writes<48000 || reads<48000')
text=text.replace('camera/TFT integration watchdog','800 camera/TFT integration watchdog')
text=text.replace('PASS full camera800x480', 'PASS 50MHz control + CDC snapshots +33MHz full camera800x480')
(ROOT/'tests/camera_tft800_tb.v').write_text(text,encoding='utf-8')

text=(ROOT/'display/tests/display_diagnostic_tb.v').read_text(encoding='utf-8')
text=text.replace('display_diagnostic_tb','display800_diagnostic_tb').replace('always #10 clk=~clk','always #15.151515 clk=~clk')
text=text.replace('.FRAMES_PER_COLOR(2)', '.FRAMES_PER_COLOR(2),.WIDTH(800)')
text=text.replace('a741_osd osd','a741_osd #(.WIDTH(800),.HEIGHT(480),.PIPELINED(1)) osd').replace('a741_tft480_panel','a741_tft800_panel')
text=text.replace('integer sampled_x,sampled_y,seen', 'integer sampled_x,sampled_y,x0,x1,y0,y1,seen')
text=text.replace('if(pixel_request) begin sampled_x=x;sampled_y=y;end','x0<=x;x1<=x0;sampled_x<=x1;y0<=y;y1<=y0;sampled_y<=y1;')
text=text.replace('negedge tft_clk','posedge tft_clk').replace('480*272','800*480')
text=text.replace('sampled_x>=48 && sampled_x<432','sampled_x>=208 && sampled_x<592')
text=text.replace('sampled_x>=300 && sampled_x<360','sampled_x>=500 && sampled_x<600')
text=text.replace('red_bar!=60','red_bar!=100').replace('live_pixels!=5*480','live_pixels!=5*800')
text=text.replace('PASS diagnostic display:', 'PASS 800x480/33MHz diagnostic display:')
(ROOT/'display/tests/display800_diagnostic_tb.v').write_text(text,encoding='utf-8')
