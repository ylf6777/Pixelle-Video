# ComfyUI 实战知识库

## 四大平台速查

| 平台 | 用途 | 地址 |
|------|------|------|
| LiblibAI | 找模板/工作流/模型 | liblib.art |
| eSheep | 在线直接跑 ComfyUI | esheep.com |
| RunningHub | 云端 ComfyUI + 工作流变现 | runninghub.cn |
| ComfyUI官方 | Wan2.1 视频教程 | docs.comfy.org/zh/tutorials/video/wan/wan-video |

## Wan2.1 RTX 4090 配置表

| 任务 | 模型 | 精度 | 显存 |
|------|------|------|------|
| T2V 480P | wan2.1_t2v_1.3B | FP16 | ~8GB |
| T2V 720P | wan2.1_t2v_14B | FP8 | ~18GB |
| I2V 480P | wan2.1_i2v_480p_14B | FP8 | ~20GB |

**关键参数**：帧数 33-49，步数 25-30，CFG 7-8

## 下载模型渠道

| 平台 | 适用 |
|------|------|
| modelscope.cn | 国内高速，大模型首选 |
| hf-mirror.com | HuggingFace 镜像 |
| liblib.art | 模型社区 |

## Qwen Image 快速部署（15分钟）

1. AutoDL 租 4090 → 选 ComfyUI 镜像
2. 链接预置模型
3. 启动 ComfyUI → 粘贴 image_qwen.json
4. Pixelle-Video 连接 → 生图

详见 `docs/ComfyUI_Qwen_快速部署.md`
