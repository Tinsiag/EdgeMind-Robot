# EdgeMind-Robot 维护约定

## 入口和范围

- 活动 FPGA 工程是 `code/camera-car-control/a745-autonomous/`。
- 实板状态以 `output/current-firmware/STATUS.json` 与对应真实 Flash 审计为准。
- 当前记录、待验收项与来源见 `docs/project-status.md`；不要按历史版本号推定实板。
- 本轮是本地目录与文档整理，不触发编译、Flash、4A部署、运动、远端推送或关机。
- 保留用户现有修改；未明确要求时不推送、强推或改写 Git 历史。

## 常用命令

在仓库根目录运行：

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/check_project.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/scripts/check.py
```

完整构建与签核命令由 `docs/contributing.md` 维护。
审核工具放在 `scripts/fpga/validation/`，输出统一写入 `output/current-firmware/`。
`inspect_implementation.py` 与 `final_gate.py` 只更新候选证据，不能覆盖已烧录实板状态。

## 硬件操作

- 禁止电脑 ARM、模拟本地 S1 或替用户启动实物运动。
- 上电未 ARM；S1 本地启停，S0 复位停车。
- 持续 Flash 授权有效：必要门通过、明确路径/SHA、已知 VM 关闭时直接 Flash，不重复问权限。
- 若 VM 状态已变化或未知，只核实物理状态；烧录和重载时 VM 关闭、轮子架空。
- 统一使用 `scripts/fpga/program_flash.py`，完成外部 Flash 写入校验、重载、只读就绪和 UserCode 比对。
- 写入/校验失败先查原因，不盲重试，不以 SRAM 下载代替固化。
- Flash 成功、被动遥测、实屏、真实断电启动和运动验收分别记录，不能相互代替。
- 不用 IMU 灯亮推定电源稳定；ERR0001/ERR0011 的电气根因未确认。

## 运动与网络约束

- 保留前方300mm停车、当前CAD转向/出口扫掠检查、陀螺仪航向与每轮速度PI。
- 三方堵塞时，仅后方严格大于350mm且几何安全才60mm/s短退；任一轮约100mm或2秒止，停稳150ms，每阶段一次。
- 无脉冲1秒只提示；约2us编码器AB过滤与非法跳变累计大于64的锁存保护保留。
- 保留22.5度倾斜、IMU有效性、CPU、雷达与全部真实故障联锁，不靠放宽阈值掩盖错误。
- ED10 UDP6105在三种模式接收显示；ET10 UDP6106只有本地模式3、S1会话、新鲜传感器及全部联锁允许时才能影响电机。
- ED10框坐标/类别/分数数据的隔离不等于整个RX隔离；共享流控与诊断可能影响新鲜度并停车。
- 相机/雷达标定默认未验证，未完成实物标定不得宣称自动接近或到达。
- 旧GND锁是FPGA内部锁低；公共GND必须保留。左A18/A19，右F13/F14。

## 显示与签核

- 保留800×480/33MHz扫描、AB22 DE/AB21背光、P7 TY-OV5640自带晶振接法。
- HUD在实拍480×272安全区内32列，不能用仿真代替新SHA实屏验收。
- 保留250MHz PLL经专用CLKDIV/2生成125MHz的MAC/RAM时钟方案。
- 不全局切时钟组，不用全局false path掩盖违例；同次PNR检查setup/hold/recovery/removal/最小脉宽、RX/TX/TFT/DVP与DDR端点。
- 保留CPU显式FF寄存器和原监督固件/看门狗；独立叶模块执行不能写成整板网表执行。
- 编译输入冻结期间不修改；RTL/CST/固件/输入集合变化需重综合。
- 仅SDC变化时，允许脚本核对原网表SHA和其余输入后复用PNR。

## 资料与清理

- V4目录的五个文件仍供V5重建和导航几何使用，必须保留；详见 `model/chassis/README.md`。
- 保留原厂IP、第三方许可、PCB/CAD源文件和真实回放数据。
- 模型位于 `code/camera-car-control/a745-autonomous/host/npu/`，不要删除正在使用的序列化模型。
- 删除目录前核实绝对路径在本工作区内，排除 `.git`、符号链接及联接点。
- 自动审批拒绝的删除不换工具或变相重试；记录未完成目标。
- 不新建备份包或交接文档；事实由状态文件、操作文档和当前证据维护。
- 当前递归缓存清理被自动审批阻止，残留及执行情况见整理记录，不得写成已删完。
