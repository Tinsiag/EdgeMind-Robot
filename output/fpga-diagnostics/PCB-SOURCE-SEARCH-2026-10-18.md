# ACG720及USB-JTAG下载板PCB资料查找，2026-10-18

## 结论

本次没有找到与用户ACG720实物主板或红圈USB-JTAG下载小板对应的完整铜走线PCB文件。找到的PcbDoc属于ACX720机械资料，不能用来定位红圈芯片的电源脚。这个结论限于本次查找范围，不代表厂家一定不提供这些文件。

用户此前报告USB接口附近芯片发烫，读到丝印 `JTAG15M02HS22528`。没有查到可核实的该芯片公开引脚表，不能套用FTDI/CH552等其他型号的电源脚定义。照片显示的局部下载电路未在已检查主板原理图中展开。

## 本机已找到的相关文件

- `model/hardware/ACX720-V3机械文件/ACX720-v2机械文件.PcbDoc`，837632字节。
- `model/hardware/ACX720-V3机械文件/converted/acx720_v2.kicad_pcb`，316186字节。
- `model/hardware/ACX720-V3机械文件/ACX720-V3.DWG`，150108字节。
- 上述原始PcbDoc与DWG在 `C:/Users/sc/Downloads/1/ACX720-V3机械文件/` 各有一份，逐字节SHA256与项目副本相同。
- ACG720通用原理图：`C:/Users/sc/Documents/Dev/Hardware/fpga/小梅哥ACG720国产高云FPGA教学开发板资料/06_硬件图纸/ACG720-138&60K通用原理图.pdf`。它是原理图，不是铜走线PCB。

已检查现有Altium导入报告与KiCad转换文件：33个封装、0段铜走线、32个过孔、0个铜区；封装参考为连接器、开关、按键、安装孔等，无U类IC封装。不能通过这个机械文件追踪JTAG芯片供电。以上计数针对已有转换结果，未在本次重新导入原始Altium文件。

PcbDoc SHA256：`b2199389924b26142aca47f0be626da5d60ee86d3b9bd3f602fbac2de1cddc34`。
DWG SHA256：`f6bb623a6451fad67cc167028831750ba49d55e6438d0496024a058a1e735cce`。

## 查找范围与边界

- 搜索本机 `Documents/Dev/Hardware/fpga`、项目目录及 `Downloads` 下的PcbDoc、kicad_pcb、brd、pcb、epro/eprj等文件。
- 资料包内另外找到两份TFT屏机械PcbDoc；项目电源驱动板KiCad文件也存在，均不属于待查的ACG720主板/JTAG小板。
- FPGA资料包有188个ZIP/RAR/7Z压缩包，按文件名未筛出硬件/PCB/机械/JTAG候选；没有逐一解包全部教学软件和例程压缩包。
- 百度网盘资料页面未能通过浏览工具读取，不能声称已核对其最新在线文件清单。
- 没有改板、改代码、下载固件或请求重新上电。

## 已核对的厂家公开页面

- [所有产品机械结构文件](https://fpga.cn/forum.php?mod=viewthread&tid=28410)：提供ACX720-v2和V3机械资料，明确用于Altium尺寸测量。
- [ACG720产品使用自助服务手册](https://fpga.cn/forum.php?mod=viewthread&tid=29765)：链接全套网盘资料，本页未单列完整PCB文件。
- [高云FPGA下载器使用说明](https://fpga.cn/forum.php?mod=viewthread&tid=30126)：接口接法、故障排查与驱动说明，未找到对应小板PCB或芯片引脚表。
- [所有FPGA核心板原理图PCB设计封装库资料](https://fpga.cn/forum.php?mod=viewthread&tid=30446)：本次页面列出ACG525-CORE和AC601等封装库，未列ACG720或该JTAG小板。

如需向厂家索取，准确目标是“照片这款USB-JTAG下载小板的原理图、PCB走线文件，或JTAG15M02的电源/地脚定义”，不能只用ACX720机械文件代替。未向厂家或其他人发送消息。
