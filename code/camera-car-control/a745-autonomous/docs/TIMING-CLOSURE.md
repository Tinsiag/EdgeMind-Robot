# Gowin 布局布线与时序审核

适用 GW5AT-60B / GW5AT-LV60PG484AC1/I0、Gowin V1.9.12.04。
当前构建是否签核、是否烧录，以[当前STATUS](../../../../output/current-firmware/STATUS.json)
和真实 Flash 审计为准。本文中的优化方案不代表实板验收通过。

## 历史优化说明的来源

清理前提交 `ac56a9e^` 中保留了以下文档，可直接用 `git show` 阅读：

- `TIMING-FIX-20261027.md`：TX FIFO RAM 最小脉宽修正的实际记录。
- `code/camera-car-control/a741-fpga-fusion/docs/TIMING-CLOSURE.md`：接口预算、DDR 局部例外依据。
- `output/handoff-basic-tft480-20261027/USER-OPTIMIZATION-IDEAS-1.md`：先读报告、局部修改、分阶段构建的优化说明。

本次沿用其诊断方法，不恢复旧工程或旧位流。

## 本次定位的瓶颈

1. 检测包采用流式校验，避免动态读取整包寄存器造成大规模多路选择器。
2. 包解析从 125 MHz 移到 50 MHz，用整帧异步 FIFO 连接 MAC；校验与发布分周期。
3. 125 MHz PLL 直接驱动 RAM 时，建立/保持通过，但最小脉宽仍有约 -0.07 ns 裕量。
   路由优先级调整未解决。按历史依据将 PLL 输出改为 250 MHz，经专用 `CLKDIV /2`
   生成 MAC/RAM 的 125 MHz。`prepare.py` 只修改生成副本的 ODIV1=6→3，原厂源文件保留。
   不是用普通逻辑寄存器生成时钟；不强制其使用 BUFG，以免专用连接出现绕路。
4. RGMII RX 的五条数据/控制路径采用相同 IODELAY96。独立 SDF 审核覆盖两个 DDR 边沿、
   三个 PVT 角；仅 STA 快角 hold 通过不足以放行。

## 构建与复用

在仓库根目录运行：

```powershell
$env:GOWIN_PLACE_OPTION='2'
$env:GOWIN_ROUTE_OPTION='2'
$env:GOWIN_CLOCK_ROUTE_ORDER='1'
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/build.py build --timeout 1800
```

`synth` 只综合；`pnr` 复用相同 SHA 的综合网表，只允许 SDC 改动或实现策略调整。
RTL、CST、固件或源文件集合改变必须重新综合。编译输入冻结期间不能修改。
频率优先时钟路由选项依据 SUG1220-2.1E 第 41 页；它不能替代时序检查。
每轮应记录资源、Placement/Route 耗时、关键路径、高扇出、拥塞和负裕量。

不能为缩短编译删掉运动保护、减少视频整帧 FIFO 到不足一帧，或通过全局 false path
屏蔽跨域。独立叶模块综合仿真不能写成整板网表执行。

## 接口和 DDR 约束依据

RTL8211F-CG 集成延迟模式 Table58 setup/hold 最小 1.2 ns，预留板级偏斜 0.2 ns，
RX 两沿输入转换窗口为前一相反边沿后 1..3 ns。额外预留 0.035 ns 不确定度。
TX 须审核同次 SDF 的数据/控制相对转发时钟偏斜，并独立满足 Q 到 pad 0.5..3 ns。
STA 粗略绝对到达上限不能替代此项相对审核。预算不是板级示波器测量。

DDR 例外来自 Gowin DDR3 RefDesign 5.8E（历史资料 SHA256
`39d0d30584a7c1740d5921c1d7934b334f5fc2db7909d99e4283a25e9a75cc03`）及
IPUG281-2.6E §4.4.2/4.4.3；匹配板卡的明文仿真模型在 `vendor/reference/`，SHA256
`c9da2a7b0f89226a6063b3d57037f6ed3d36ca2a0914de2eaefe7bf22a119cbd`。
只针对初始化复位、DQS/HOLD、IDES/CALIB、DLL/STEP 和已核对的同步首级/握手信号。
保留流数据路径和后级同步路径检查，每次确认实际 routed 原语端点及约束 Actived。

## 放行门

须通过完整 RTL、独立协议/几何/回放/CPU、同源导航与显示叶模块原语执行，
并核对同次 PNR 的 setup、hold、recovery、removal、minimum pulse width。
再执行 `scripts/fpga/validation/` 内的实现检查、六项接口审核和最终门，完整命令见[开发指南](../../../../docs/contributing.md)。
所有审核绑定同一位流 SHA；Flash 写入/校验、重载、就绪、UserCode 和被动健康另外记录。
屏幕实物观察与真实断电启动单独验收。
