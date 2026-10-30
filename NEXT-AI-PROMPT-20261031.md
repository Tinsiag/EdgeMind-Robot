请接手 EdgeMind-Robot，项目目录 C:\Users\sc\Documents\Dev\Hardware\EdgeMind-Robot，GitHub 为 Tinsiag/EdgeMind-Robot，main 分支。

先读 AGENTS.md、.agent/main/handoff.md、output/refactor-autonomous-20261030/STATUS.json。当前 FW74504 已固化且用户确认真实断电重启正常，位流 SHA-256 为 74cef81a075feb78f9c5bc70a91384a368dc81e080ad65a3eccbb867f01719df，发布文件 output/releases/fw74504/a745.fs（Git LFS）。

用户最终要求仅前方50cm停车，侧后方按车身转弯空间；左右择路后用陀螺仪完成转角，再锁新航向直行。当前能前进，但用户报告没有转弯、MODE为BLOCK，问题尚未解决。先恢复只读遥测，取得固定场景F/L/R、左右转向许可及实际阻挡雷达点，使用 output/refactor-autonomous-20261030/capture_turn_blocks.py 定位；此前待机时F一度约10cm不能冒充BLOCK测试的根因。

保留安全联锁、上电未ARM、S1启停和S0急停，网口仅传数据。当前未实现卡尔曼滤波。不要盲降几何门槛或直接重烧。VM当前状态未确认，任何烧录前先核实关闭；持续烧录授权有效，不重复索取权限。先架空验证左右选向和约2秒S1停止，再受控低速验证落地约90度转弯及转后直行。架空时车身不转，超过4.5秒ERR0080是无航向进度保护。

源码、交接、必要证据和旧文件删除记录已随本次提交上传，远端main当前目录同步清理；不恢复旧备份、不拆公共GND。不要自动关机。只在有真实证据时更新验收结论。
