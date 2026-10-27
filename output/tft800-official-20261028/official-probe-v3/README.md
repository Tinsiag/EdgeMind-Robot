# 官方第28章独立色块对照候选

更新：该候选后来已按用户持续授权完成Flash写入、校验及重新加载；用户反馈仍全白，记录见`output/flash-official-probe-20261028/STATUS.json`。当前已由接口读回诊断版替换，最新硬件状态见根AGENTS.md；以下保留候选准备阶段说明。

仅用于对照白屏，不替换主工程源码。当前板上仍为d5e558ad…2a1ad62b完整800工程，用户报告全白，D0亮、D1/D2闪烁。

此候选以用户官方GW5AT60K第28章的33MHz PLL、扫描器、HW_TFT50参数和八色块逻辑为基础。原厂控制/参数/PLL文件原样保留；顶层PLL锁释放增加两级同步，避免原厂直接跨域释放造成removal违例；输出增加下降沿寄存，使新版面板上升沿采样具有半周期建立/保持余量。增加两个心跳LED和四路电机输出物理GND。无摄像头/DDR/IMU/网口/避障功能，烧录后只预期看到八色块，不显示主工程文字。

候选`impl/pnr/probe.fs`，SHA256=`5f1c436e422728ed56d8b6f22c27134a7d9fe8f7831a9709fb38ba0990f9d250`。

已完成独立两帧800×480色块及输出相位仿真（PLL以理想33MHz模型替代；真实PLL采用原厂配置）、布局1/布线1、时序驱动/hold修复。最终setup+2.835ns、hold+0.188ns、recovery+28.895ns、removal+0.398ns、MPW+7.122ns。真实SDF引脚setup15.2265ns、hold15.0305ns，8ns要求加1ns未实测板/线预算和0.3ns时钟预留后余量5.7305ns。四路电机OBUF均GND。

证据`SIMULATION.json`、`simulation.log`、`REVIEW.json`、`result.json`、`impl/pnr/`。Flash仅预览，尚未取得本候选写入授权，未烧录。

`official-probe`初版输出寄存器合并造成10ns输出约束失败；`official-probe-v2`保留寄存器后仍有原厂锁释放removal违例。两版均未烧录，保留失败证据，不当作此v3的验收。

LED：D0固定亮（仅候选标志，非PLL检测），D1为50MHz计数心跳，D2为16帧心跳，D3～D7灭。该映射只有本候选实际烧录后适用。
