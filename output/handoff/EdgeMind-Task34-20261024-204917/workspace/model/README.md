# 硬件机械模型与参考图

2026-10-12 按用户要求，将 `C:/Users/sc/Downloads/1` 中的模型、转换资料和离线查看器复制到 [hardware/](hardware/)，并收纳本轮使用的嘉立创 EDA 电源驱动板 STEP。原文件内容保持不变；每个文件的大小与 SHA-256 见 [复制校验清单](hardware/model-manifest.json)。

## 主要模型

| 部件 | 文件 | 尺寸与用途 |
| --- | --- | --- |
| 电源驱动板 | [3D_PCB1_2026-10-12.step](hardware/3D_PCB1_2026-10-12.step) | 用户当前嘉立创 EDA 现板导出；PCB 约 100×50 mm，模型包络约 100×50.06×18.30 mm |
| 荔枝派 LPi4A | [SIPEED_LPi4A_51601.step](hardware/SIPEED_LPi4A_51601.step) | 原始装配模型；含突出接口的包络约 84.455×103.814×20.358 mm；使用 Git LFS |
| MG513X 霍尔编码电机 | [电机 STP](hardware/直流电机-MG513X（霍尔编码器）/直流电机-MG513X（霍尔编码器）.stp) | 含安装法兰的包络 64.5×57.6×38 mm；四轮概念使用两台驱动后轮 |
| FPGA V3 机械图 | [ACX720-V3.DWG](hardware/ACX720-V3机械文件/ACX720-V3.DWG) | 二维图纸；V3 板面 138.049×91.567 mm；实际 ACG720 版本须复核 |
| FPGA V2 原始机械 PCB | [ACX720-v2机械文件.PcbDoc](hardware/ACX720-V3机械文件/ACX720-v2机械文件.PcbDoc) | V2 与 V3 尺寸不同，不混用几何 |

## FPGA 转换资料

[converted/](hardware/ACX720-V3机械文件/converted/) 保留从下载目录复制的 STEP、STL、GLB、DXF、SVG、转换脚本、报告及离线 HTML 查看器。

- [V2 STEP 包络模型](hardware/ACX720-V3机械文件/converted/acx720_v2_reference.step)：板面约 149.861×109.220 mm，源器件包络统一高 3.81 mm；这些高度及层叠厚度未按实物验证。
- [V3 平面 STEP](hardware/ACX720-V3机械文件/converted/acx720_v3_planar_reference.step)：来自二维 DWG，无器件高度信息，保持零厚度平面。
- [转换报告](hardware/ACX720-V3机械文件/converted/conversion_report.json)：记录源文件哈希、板框、已知异常及转换边界。
- [离线查看器](hardware/ACX720-V3机械文件/converted/open_3d.html)：克隆并取得实际文件后，用浏览器打开本地文件；保留同目录文件和 `vendor/`。GitHub 文件页面显示 HTML 源码。

转换资料中的 `acx720_v2.kicad_pcb` 只是 V2 原机械图的中间转换文件，与当前嘉立创电源板无关。没有复制 `.kicad_prl` 编辑器个人状态。

## 获取大模型

首次克隆时先安装 Git LFS，然后执行：

```sh
git lfs install
git clone https://github.com/Tinsiag/EdgeMind-Robot.git
cd EdgeMind-Robot
git lfs pull
```

已有仓库执行 `git lfs pull` 即可取得荔枝派的完整 STEP。只得到三行 LFS 指针文本时，不能将其直接作为 STEP 打开。

## 底盘概念

**2026-10-20 当前版本为 [V4 第三层传感器平台](chassis/v4-lidar-imu/README.md)**：第三层板厚5mm，45mm支柱架起，LD06位于正前中央、MPU6050位于前侧靠边且双孔朝外，用户洞洞板居中放在雷达后方。打开 [V4完整装配STEP](chassis/v4-lidar-imu/EdgeMind_Assembly.step)、[V4 FreeCAD装配](chassis/v4-lidar-imu/EdgeMind_Chassis.FCStd)、[V4离线预览](chassis/v4-lidar-imu/查看模型.html) 或 [第三层板STEP](chassis/v4-lidar-imu/ThirdDeck.step)。R3X轮组、原V3摄像头、连续围栏与85×47mm电池位保留。[V3](chassis/v3-camera-closed-rails/README.md) 和 [V2](chassis/v2-r3x-casters/README.md) 保留。

以下为保留的V1与最初概念参考。

已根据四轮概念图生成 [外壳与底盘 CAD 模型](chassis/README.md)，前轮按用户最终选择改为与后轮同直径的80mm固定轴承从动轮。可打开 [外壳 STEP](chassis/v1-fixed-front-wheels/EdgeMind_Shell.step)、[FreeCAD 装配](chassis/v1-fixed-front-wheels/EdgeMind_Chassis.FCStd) 或 [离线3D预览](chassis/v1-fixed-front-wheels/查看模型.html)。板卡参考、核验范围与加工前需确认的尺寸见模型说明。

[四轮版本说明](../output/chassis-concept-2026-10-12/四轮版本说明.md) 包含后轮 MG513X×2、前万向轮×2 的布局、原尺寸装配参考和 AI 造型效果图。电池按用户给定 105×33×25 mm 留位，没有独立的电池 STEP。模型和概念图用于结构讨论；实际开孔、轴线、接口净空和完整干涉仍需核验。

## 原有参考图

- `BE11300D28AD57C96EC11B6DEDBB3751.bmp`：灰度板卡布局图，标注约 84.45×99.06 mm；单独截图的板型尚未最终核实。
- `EDE6B28DC4BC051CA18BC4B2684486C0.png`：Autodesk Viewer 的 `ACX720-V3.DWG.png` 截图。132.461×85.979 mm 标注取点位于角部孔中心，不能直接当作完整板框尺寸；V3 板框以正式图纸及转换报告为准。

原始模型、转换数据和附带库的作者信息与许可文本保持原样，设计权利仍归相应提供方。
