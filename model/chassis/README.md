# EdgeMind 四轮外壳与底盘 CAD

**当前版本：[2026-10-15 V3 摄像头立板与连续围栏](v3-camera-closed-rails/README.md)**。上下层均为5mm，增加摄像头立板及两处电机过线孔；删除上方侧护栏，下层围栏连成一体并保留通风孔。[完整装配STEP](v3-camera-closed-rails/EdgeMind_Assembly.step)、[FreeCAD源文件](v3-camera-closed-rails/EdgeMind_Chassis.FCStd)、[离线预览](v3-camera-closed-rails/查看模型.html)。[V2](v2-r3x-casters/README.md) 与以下V1记录保留。

2026-10-12。按项目第二版四轮概念图建模，并采纳用户最终选择：四轮均为直径 80mm 的普通轮，后轮由两台 MG513X 驱动，前轮固定朝前、独立轴承从动，无前轮电机。

模型目录：[v1-fixed-front-wheels/](v1-fixed-front-wheels/)。优先打开其中的 `EdgeMind_Chassis.FCStd` 或 `EdgeMind_Assembly.step`；双击 `查看模型.html` 可离线旋转、隐藏硬件和展开上层托盘。

## 交付文件

| 文件 | 用途 |
| --- | --- |
| `EdgeMind_Shell.step` | 25 个外壳、安装座及支柱实体，供 CAD 装配和后续结构修改 |
| `EdgeMind_Assembly.step` | 外壳、四轮、两台电机、电池和板卡参考的装配，173 个实体 |
| `EdgeMind_Chassis.FCStd` | FreeCAD 原生装配文件，各零件独立分组，可移动、隐藏及替换；不是全约束的草图特征树 |
| `EdgeMind_Assembly.glb` | 轻量三维预览，glTF 标准米单位、Y 向上；CAD 文件为 mm、Z 向上 |
| `parts-step/` | 15 个设计零件的独立 STEP |
| `parts-stl/` | 同样 15 个零件的封闭 STL，毫米单位；保持装配坐标，切片软件可自动放到底面 |
| `查看模型.html` 与 `vendor/` | 本地交互预览，无网络请求；旋转、缩放、部件显示、上层展开 |
| `preview-*.png` | 装配、外壳、展开和俯视的真实网格渲染 |
| `verification.json` | CAD 实体、STEP 回读、STL 封闭性、轴高及主要干涉的检查记录 |

## 尺寸和坐标

| 项目 | 数值，mm |
| --- | --- |
| 主体底板 / 上层托盘 | 260 × 180，厚 3，前后角倒角 |
| 装配包络，长 × 宽 × 高 | 265 × 234 × 96.35827 |
| 下层底板底面 / 顶面 | Z=18 / Z=21 |
| 上层托盘底面 / 顶面 | Z=64 / Z=67 |
| 板卡基准面 | Z=76 |
| 四个轮子 | 直径 80，胎宽 18，左右轮中心 X=±106 |
| 前轮 / 后轮轴线 | Y=−95 / Y=+80，Z=40 |
| 前轮轴承参考 | 内径 8、外径 22、宽 7，每轮两个，轴径 8 |
| 电池 | 105 × 33 × 25，中央纵向安装 |

单位为毫米，X 为左右，前方为 −Y，后方为 +Y，地面 Z=0。上下层之间四根支柱，银色侧护边、琥珀色装饰条、前后护板和通风槽沿用概念图的造型语言。前轮固定支座采用螺钉装配，方便后续替换。

## 来源与建模边界

- 造型和总体尺寸来自 `output/chassis-concept-2026-10-12/chassis-concept-v2-four-wheel.png`、`四轮版本说明.md` 及原尺寸装配参考。
- 两台 MG513X 直接载入 `model/hardware/` 的原 STEP，未缩放。对齐其实际输出轴而非外形中心；安装座四孔按源几何的 50 × 26.5mm 孔中心距布置。
- 电源板采用概念图中的原嘉立创 100×50mm STEP，保留 101 个原实体；安装孔从 STEP 板体的圆柱面读取。**这份机械参考没有替换为刚复制到主工程的约96×97mm AI KiCad PCB。若最终使用那块新版板，应调整下层电源板和电池的位置及孔位。**
- FPGA 使用 V3 板面 138.049×91.567mm 的板卡包络；器件和安装位置为参考，不是实物高度认证。荔枝派采用原模型的 84.455×103.814×20.35827mm 包络，连接器细节作简化，没有把119MB原装配重复嵌入外壳文件。
- 后轮和前轮的轮毂、轴承、适配套是结构参考。前轮固定朝前时，左右差速转弯存在横向拖擦；本轮按用户明确选择保留此配置。
- 未指定加工材料或做承载分析，未加入完整线束、轮胎形变、紧固件公差、散热及整车载荷验证。板卡孔位、实际轮毂与电机轴的配合应在加工前按实物定型。

## 已执行检查

- 173 个 FreeCAD 实体可重新载入，均有效。
- 外壳 STEP 的 25 个实体及装配 STEP 的 173 个实体重新读入有效，精确 B-rep 包络与体积一致。
- 15 个 STL 分件重新读入为封闭网格。
- 四个轮胎最低点均为 Z=0。
- 外壳和安装件对两台电机、电池、板卡包络、轮胎、轮轴及后轮适配套的主要体积干涉为0。此项不是完整的装配公差、线束或所有零件间干涉验收。
- 离线 HTML 在浏览器中实际载入；硬件隐藏、上层展开和俯视操作通过，控制台无错误。

## 修改和重新生成

主要参数在同级 `parameters.json`，几何定义在 `build_chassis.py`。FreeCAD 文件保存独立实体和参数来源；要修改总体参数，可调整 JSON 后运行生成脚本。某些孔位及安装座依据原电机/电源板固定几何，不会随任意总体参数自动重新约束。

在本机 PowerShell 中：

```powershell
& 'D:\FreeCAD 1.1\bin\python.exe' 'model\chassis\build_chassis.py'
& 'D:\FreeCAD 1.1\bin\python.exe' 'model\chassis\create_preview.py'
& 'D:\FreeCAD 1.1\bin\python.exe' 'model\chassis\verify_model.py'
& 'C:\Users\Shan_\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'model\chassis\verify_preview.cjs'
```

浏览器核验脚本使用本机 Chrome 及 Codex 提供的 Playwright，只为生成预览和核验操作；打开已生成的 HTML 不需要这些运行环境。离线预览所用 Three.js 的原许可文本保留在 `vendor/three.LICENSE.txt`。
