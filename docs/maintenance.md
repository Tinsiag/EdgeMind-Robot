# 项目维护与清理

## 文件归属

| 内容 | 唯一入口 |
| --- | --- |
| 实板SHA、Flash与验收标志 | `output/current-firmware/STATUS.json` |
| 原始Flash执行证据 | `output/current-firmware/flash/audit.json` |
| 候选签核和静态接口审查 | `output/current-firmware/` |
| FPGA审核工具 | `scripts/fpga/validation/` |
| 本机只读遥测工具 | `scripts/fpga/` |
| 当前NPU序列化模型 | `code/camera-car-control/a745-autonomous/host/npu/` |
| 真实LD06回放输入 | `code/camera-car-control/a745-autonomous/tests/fixtures/ld06-capture.json` |
| 人类使用和开发说明 | `docs/`及各子项目README |

原始审计保留执行当时的命令和暂存路径；归档后的现存位置由当前状态和整理记录维护。
审核脚本只生成哈希索引，不再复制整套SDF/网表。
当前可复核主构建保留FS、SDF、VO、STA和综合网表，重新构建后这些生成物可替换。

## 本轮执行情况

已核实本地和远端基线一致，并迁移必要证据、模型与回放输入。
旧根交接文档已删除，长期维护文档取代旧交接入口。

**历史缓存和备份的目录删除尚未完成。**
自动审批分别拒绝整批递归删除和一个明确历史目录的递归删除，只返回`blocked by policy`。
命令在运行前被拒绝；未换工具删除相同缓存、未移到项目外制造新备份。
待处理目录与容量见[删除计划](../output/project-maintenance-20261104/PLAN.json)，实际结果见[整理记录](../output/project-maintenance-20261104/RESULT.json)。

## 验证整理结果

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/check_project.py
```

该检查核对Markdown相对链接、当前状态/Flash/位流SHA、源码输入及必需的CAD/NPU资料。
不要因资料整理而重新烧录或把待验收标志改成通过。
