# 2026-10-15 实板串口证据快照

从本机 `.local/` 复制的当日原始串口日志/逐帧 JSON，便于远程交接；不包含虚拟环境、厂家资料、密码或位流。SHA256SUMS.json 校验本目录归档文件。记录包含内部状态快照，不是引脚/电压/电流实测。

- bench-uart：3次完整STATUS回复。
- bench-no-motion：VM断电零限幅配置、ARM/STOP状态切换。
- bench-left-limited、limited2、limited3：20kHz三次左轮短脉冲；limited第一次收尾超时，后续单独安全恢复查询结果见BENCH文档，原始失败记录不覆盖。
- bench-left-start50：另有已存在的20kHz/50%上限短脉冲日志，最高幅值512、无计数；与A718的1kHz/1秒不同。此记录不用于替代用户对其他测试的现场反馈。

最新板上诊断/测量状态、安全边界和下一步见工程README及开环工程README。不要执行原始记录中的命令来自动重放。
