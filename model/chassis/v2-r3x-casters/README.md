# EdgeMind 底盘 V2：R3X 轮组与双前万向轮

2026-10-15 按用户提供的 R3X STEP 更新。主体仍为 260 × 180 mm 双层结构。

## 打开文件

- **完整装配：[EdgeMind_Assembly.step](EdgeMind_Assembly.step)**。包含全部外壳、上层板卡、电源板、两只前万向轮、原配后轮和电机。
- **FreeCAD 装配：[EdgeMind_Chassis.FCStd](EdgeMind_Chassis.FCStd)**。上层零件收进 `06 上层总成`，修改这个总成的 `Placement → Position → z` 可整体抬升。装配状态为 0，查看下层时可设为 65 mm。
- **已展开的 FreeCAD 文件：[EdgeMind_Exploded.FCStd](EdgeMind_Exploded.FCStd)**。上层已整体抬升 65 mm，便于检查下层。
- **离线预览：[查看模型.html](查看模型.html)**。直接双击，用“上层展开”滑块；关闭“显示上层总成”可看电池围栏。
- [外壳与支撑 STEP](EdgeMind_Shell.step)、[GLB 轻量模型](EdgeMind_Assembly.glb)、[独立 STEP](parts-step/)、[独立 STL](parts-stl/)。STL 使用装配坐标，切片时可自动放平并落到平台。
- **SolidCraft 可编辑底板：[EdgeMind_Base.solidcraft](EdgeMind_Base.solidcraft)**。通过 SolidCraft 0.11.1 的 MCP 建模，有厚度、围栏、扎带孔、安装孔等特征历史。

SolidCraft 0.11.1 MCP 的底板建模、改参和导出均成功；尝试导入完整轮组与板卡 STEP 时，该版本在 NURBS 曲线处报 `ZeroRange`，随后内存分配失败，未生成整机 `.solidcraft`。整机请用上面的 STEP 或 FreeCAD 文件；`build_solidcraft_assembly.py` 保留这次兼容性尝试，不属于必需的重建步骤。

## 本次结构

| 部位 | 处理 |
| --- | --- |
| 前轮 | 复制 R3X 前方万向轮两套，轮径 25 mm；保留轮胎、叉架、轮轴原几何 |
| 后轮及电机 | 使用 R3X 两套原后轮、轮毂、电机、编码器和原配安装支架，未缩放；后轮外径约 66.36 mm |
| 底板 | 厚度由 3 改为 4 mm；上层托盘保持 3 mm |
| 电池 | 平底板上加四周围栏，内腔 87 × 49 mm，适配 85 × 47 mm 电池，每边留 1 mm；围栏高 3 mm、厚 2 mm |
| 扎带 | 围栏左右各两个 3.5 × 8 mm 通孔，可穿两条尼龙扎带；不设电池厚度或电池实体 |
| 下层布局 | 电源板放前部，电池围栏放后部，保持两者占位分开 |
| 底板高度 | 原配电机支架装于板下，底板下表面 Z≈57.781 mm；万向轮隔柱长约 23.781 mm，四个轮子最低点均为 Z=0 |
| 后轮轴位置 | Y=+60 mm，让原配电机支架和全部安装孔落在 260 mm 底板以内 |

`CasterSpacer1` 是万向轮隔柱的制造参考件，**共需 8 件**。长度按来源模型的轮胎几何配平，实际装配可用支柱与垫片调整；四个轮子均为刚性安装，地面不平时仍可能存在三点接触。

## 模型范围与核验

- R3X 原文件收录在 `model/hardware/R3X-320x240-reference.step`。`reference-extraction.json` 记录来源 SHA-256、原实体编号和变换后尺寸；`hardware-brep/` 为未缩放的提取缓存。
- 底板由 SolidCraft MCP 制作，导出后用 FreeCAD 的精确实体布尔差检查，确认围栏、孔位和板厚符合独立构建的参考实体。SolidCraft 参数走查、请求记录见 `solidcraft-verification.json` 与 `solidcraft-mcp-log.json`。
- `verification.json` 记录原生文件、STEP 回读、STL 闭合性、关键实体干涉和万向轮保守回转范围。`viewer-verification.json` 记录实际浏览器载入与上层整体展开验证。
- 电源板仍采用上一版 **100 × 50 mm 原 STEP**；此前复制到 KiCad 主项目的约 96 × 97 mm AI PCB 尚未替换进机械装配。FPGA 和 LPi4A 保持上一版包络参考，并非完整实物模型。
- 本轮检查覆盖几何、孔位与主要净空；线束、紧固件详细选型、载荷、强度和加工公差需结合实物确定。

## 重建

在项目目录运行，先安装 FreeCAD Python 环境及 SolidCraft CLI 0.11.1。所有脚本只输出到本 V2 目录，V1 保留。

1. 用 FreeCAD Python 执行 `extract_reference.py`。
2. 用 FreeCAD Python 执行 `solidcraft_workflow.py <solidcraft-cli.exe 的路径>`。这是独立的 MCP stdio 会话，不接管打开的文档。
3. 用 FreeCAD Python 执行 `build_model.py`、`verify_model.py`、`generate_viewer.py`。
4. 用 Node 执行 `verify_viewer.cjs`，生成真实浏览器截图与验证记录。本机脚本中的 Playwright/Chrome 路径需按环境调整。

`solidcraft-build.json` 同时保留 MCP 使用的命令列表，可用 `solidcraft-cli run` 直接重建底板。
