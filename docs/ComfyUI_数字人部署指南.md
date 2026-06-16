# ComfyUI 数字人部署指南

## 方案对比

| 方案 | 基础模型 | 特点 | 显存 |
|------|---------|------|------|
| **InfiniteTalk + Wan2.1** | Wan2.1 I2V 14B | 无限时长、精准口型、微表情同步 | 12-24GB |
| LivePortrait | 独立模型 | 轻量、照片驱动 | 4-8GB |
| MuseTalk | 独立模型 | 实时、轻量 | 4-8GB |

推荐：**InfiniteTalk + Wan2.1**（最新、质量最高）

## InfiniteTalk 部署步骤

### 1. 模型下载（6个核心文件）

| 文件 | 目录 | 大小 |
|------|------|------|
| wan2.1_i2v_480p_14B_fp16.safetensors | diffusion_models/ | ~28GB |
| Wan2_1-InfiniTetalk-Single_fp16.safetensors | diffusion_models/ | ~5GB |
| Wan2_1_VAE_bf16.safetensors | vae/ | ~500MB |
| clip_vision_h.safetensors | clip_vision/ | ~2.4GB |
| wav2vec2-base（中文） | wav2vec2/ | 自动下载 |
| lightx2v LoRA（可选加速） | lora/ | ~1GB |

GGUF 量化版可将 diffusion model 压缩到 8-12GB。

下载源：huggingface.co/MeiGen-AI 和 huggingface.co/Kijai

### 2. 工作流

Kijai WanVideoWrapper 已内置 InfiniteTalk 示例工作流：
- `wanvideo_I2V_InfiniteTalk_example_03.json`（照片→视频）
- `wanvideo_InfiniteTalk_V2V_example_02.json`（视频→重绘口型）

### 3. 输入
- 一张人物照片/一段视频
- 一段音频文件（TTS配音）

### 4. 输出
- 口型同步的数字人视频

## 关键插件
- ComfyUI-WanVideoWrapper (by Kijai) — 核心
- ComfyUI Manager → Install Missing Custom Nodes 自动补全

## 4090 显存优化
- 使用 GGUF/FP8 量化版模型
- 启用 Block Swap（CPU offload）
- 降低帧数到 33-49 帧
