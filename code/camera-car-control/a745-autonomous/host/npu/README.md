# NPU序列化模型

`shl.hhb.bm`是现有4A服务所用的量化YOLOv5n序列化模型。
SHA-256为`c343b37b699fd4b5d87373c2931612d3c4a57edc484739224b978021a42fafad`。
本轮从旧诊断输出移至部署树，文件字节未改变。

部署目标为 `/home/debian/fpga/npu/shl.hhb.bm`，匹配TH1520的SHL运行库。
原模型及第三方运行库按各自许可使用，不赋予项目统一开源许可。
构建与使用见[视频服务](../README-video.md)。
