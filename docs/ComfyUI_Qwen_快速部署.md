# Qwen Image 生图快速部署指南

**目标**：15分钟在 AutoDL 4090 上跑通 Qwen Image 生图

## 1. 租机器（2分钟）
AutoDL → 租 4090 → 社区镜像搜 `ComfyUI` → 选下载量最高的 → 开机

## 2. 链接模型（1分钟）
开机后 JupyterLab → Terminal：
```bash
cd /root/autodl-tmp/ComfyUI/models
ln -sf /root/autodl-tmp/models/diffusion_models/* unet/
ln -sf /root/autodl-tmp/models/vae/* vae/
ln -sf /root/autodl-tmp/models/clip/* clip/
```

## 3. 启动 ComfyUI（1分钟）
```bash
cd /root/autodl-tmp/ComfyUI && python main.py --listen 0.0.0.0 --port 6006
```

## 4. 连接（本地 Windows）
AutoDL-SSH-Tools → 填 SSH 指令+密码+端口6006 → 浏览器打开 `http://127.0.0.1:6006`

## 5. 部署工作流（1分钟）
服务器终端：
```bash
mkdir -p /root/autodl-tmp/ComfyUI/user/default/workflows/pixelle
```
本机 `D:\claude\Pixelle-Video\workflows\selfhost\image_qwen.json` → ComfyUI 网页里 Ctrl+V 粘贴

## 6. 配置 Pixelle-Video（1分钟）
`config.yaml`：
```yaml
comfyui:
  selfhost:
    url: "http://127.0.0.1:6006"
```
Pixelle-Video 界面 → 媒体来源选「本地 ComfyUI」→ 工作流选 `image_qwen.json`

## 7. 生图测试
Pixelle-Video → 输入文案 → AI分析生成分镜 → 确认内容 → 预览

---

**关键模型**（镜像自带，不用下载）：
- `svdq-int4_r128-qwen-image-lightningv1.1-8steps.safetensors` (unet)
- `qwen_2.5_vl_7b_fp8_scaled.safetensors` (clip)
- `qwen_image_vae.safetensors` (vae)

**磁盘**：50G 足够，Qwen 模型都在镜像里
**费用**：4090 竞价 ¥1.5-2/时
