# 电源板 KiCad 工程

主工程 `ProPrj_power_2026-10-02.kicad_pro`，主原理图及PCB同名。使用KiCad 10打开，功能子页为01_power_input至09_control_io。项目本地符号/封装库、3D模型、fp-lib-table和sym-lib-table均需保留。

普通说明用中文和默认字体，电气网络名/位号/型号/层级引脚保持ASCII，公共地为GND，维护约定见本目录AGENTS.md。编辑原理图时局部修改，保留PCB布局、走线和铜区几何，不重新运行历史整套生成脚本。

review中保留接口线序、BOM和仍有用的器件/模型资料；历史改造脚本、备份和布局试验已列入根目录清理清单。nextpcb包含已有制造导出，是否适合新投板须依据当前PCB重新核验。此目录KiCad维护工程与同级原始EasyEDA工程独立，不能把一个格式的旧导出当作另一个的同步结果。

FPGA固件及其布局布线结果见根目录HANDOFF-20261030.md；当前PCB源文件和器件库的内容保留。
