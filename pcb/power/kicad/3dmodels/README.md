# 电源板 3D 模型

2026-10-03：模型文件随工程保存，通过 `${KIPRJMOD}/3dmodels/文件名.step` 引用。
PCB 的 53 个元件和本地封装库的 23 个封装均已绑定；H1～H4 是裸安装孔，不添加实体。
这些模型用于布局观察，不能直接作为厂家机械公差和装配验收依据。

| 使用位置 | 模型 | 匹配程度与变换 |
| --- | --- | --- |
| R1～R15 | R_0603_1608Metric.step | 通用 0603 外形 |
| 0603/0805 电容 | C_0603_1608Metric.step / C_0805_2012Metric.step | 通用尺寸；实际电容高度随具体料号变化 |
| LED1、D1 | LED_0603_1608Metric.step / D_SOD-123.step | 通用封装；LED 按焊盘中心微调位置 |
| U1/U5 | TSOT-23-8.step | 通用 TSOT-23-8，模型 Z 旋转 -90° 后匹配焊盘方向 |
| J1/J2 | PinHeader_1x08_P2.54mm_Vertical.step | 单排 8 针，2.54mm；X 偏移 -8.89mm、Z 旋转 -90° |
| J5～J8 | PinSocket_1x07_P2.54mm_Vertical.step | 单排 7 孔排母，2.54mm；X 偏移 -7.62mm、Z 旋转 -90° |
| J3/J4 | JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical.step | XH 六针替代外形，焊盘实测间距 2.50mm；X 偏移 -6.25mm。不是汉夏厂家原始 CAD |
| USB1/USB2 | USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step | GCT 相近外形；模型 Y 偏移 -1.30mm 后，四个壳脚及信号脚位置与当前焊盘对应。不是 LAIL 原始 CAD |
| L1/L2 | L_TechFuse_SL0630.step | 0630 替代外形，7.12×6.60×3.00mm；PSA 规格为长最大 7.3mm、宽 6.6±0.2mm、高最大 3.0mm。模型不表示电感值或厂家标记 |
| SW2 | SS-12D10L5.step | McFLY 公开同型号模型，端子 X 为 -4.7/0/+4.7mm；沿用作者 X 旋转 -90°。不是厂家公差确认文件 |
| CN1 | XT60PW-M.step | 公开库中的完整 SolidWorks STEP，包含外壳、两组触点、焊接端子和固定片，共 7 个实体；外壳 18.2×15.5×8.4mm。偏移 (-12.35, 0, 4.2)mm、旋转 (-90, 0, 90)°，端子及固定片对齐现有焊盘 |

AT8236 模块目前仅显示板上的四条排母。模块实际孔排中心距、插接高度尚未确认，未虚构模块本体。
J6/J8 孔序方向问题仍需修改封装方向并重布线；增加模型不会解决该电气问题。

## 来源与许可

除开关和 XT60 外，STEP 文件来自本机 KiCad 10 官方模型库，保持原文件及作者头信息。
库许可为 CC-BY-SA 4.0，包含 KiCad 电子设计使用例外；见 [KiCad-LICENSE.md](KiCad-LICENSE.md) 和
[官方库许可](https://www.kicad.org/libraries/license/)。上表替代型号只是外形映射，没有更改 BOM 厂商型号。

开关来源：[McFLY 原始 STEP](https://gitea.mcflyer.ru/McFLY/kicad_libs/raw/commit/ce0ecbd4969c26cee32dae61125bddf5e67dff2c/my_additions.3d/ss-12d10l5.step)，
对应 [作者封装](https://gitea.mcflyer.ru/McFLY/kicad_libs/raw/commit/ce0ecbd4969c26cee32dae61125bddf5e67dff2c/my_additions.pretty/SS-12D10Lx_slider_switch.kicad_mod)。
检索到的来源未附独立许可证；保留作者归属，若单独公开分发该第三方模型，需要先确认许可。

XT60 来源：[Northeastern Rover Electrical Team 的 rover-lib 模型库](https://cadlab.io/project/25916/master/files/3dmodels/rover-lib.3dshapes)，文件 `XT60PW-M.step`。
保留下载文件原始内容，STEP 头记录 SolidWorks 2017、2019-02-01；来源未声明独立模型许可证，也未确认属于厂家原始 CAD。
简化外形已从活动模型目录移走，PCB 和封装库均使用上述完整模型。
绑定脚本、逐元件映射、核验记录在 `../review/`。

## 在 KiCad 中查看

请从本目录的上一级打开 `ProPrj_power_2026-10-02.kicad_pro`，再打开 PCB 并按 `Alt+3`。
如果旧 PCB 编辑窗口仍在打开，请先关闭旧窗口并重新打开更新后的 PCB；旧窗口内存中的模型引用可能会在保存时覆盖磁盘修复。
当前引用统一为 `${KIPRJMOD}/3dmodels/`，不再依赖原来缺失的 `EASYEDA_MODELS` 目录。
