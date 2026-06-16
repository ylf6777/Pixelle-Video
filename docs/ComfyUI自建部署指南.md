# ComfyUI 自建部署指南
不依赖应用市场，任何 GPU 云都能搭

## 一、选镜像（2分钟）

AutoDL、RunPod、Vast.ai 通用：
- 搜 `comfyanonymous/ComfyUI` 官方镜像 → 选最新的
- 或选带 PyTorch + CUDA 的基础镜像自己装

**AutoDL 路径**：算力市场 → 选显卡 → 社区镜像搜 `comfyui` → 选官方 `comfyanonymous/ComfyUI`

## 二、基础部署（5分钟）

```bash
# 1. 进入数据盘
cd /root/autodl-tmp

# 2. 如果没有 ComfyUI，克隆一份
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装插件管理器
cd custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# 5. 启动
cd /root/autodl-tmp/ComfyUI
python main.py --listen 0.0.0.0 --port 6006
```

## 三、安装 Wan 视频插件（核心）

```bash
cd /root/autodl-tmp/ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
cd ComfyUI-WanVideoWrapper
pip install -r requirements.txt
# 重启 ComfyUI
```

## 四、下载模型

### 方案A：ModelScope（国内高速）
```bash
pip install modelscope
python3 -c "
from modelscope import snapshot_download
# Wan2.1 I2V 480P
snapshot_download('Wan-AI/Wan2.1-T2V-14B', cache_dir='models/diffusion_models')
"
```

### 方案B：HuggingFace 镜像
```bash
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download \
  Comfy-Org/Wan_2.1_ComfyUI_repackaged \
  split_files/diffusion_models/wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors \
  split_files/vae/wan_2.1_vae.safetensors \
  split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  split_files/clip_vision/clip_vision_h.safetensors \
  --local-dir models
```

### 必须下载的模型清单

| 模型 | 目录 | 大小 |
|------|------|------|
| wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors | diffusion_models/ | 16G |
| wan_2.1_vae.safetensors | vae/ | 250M |
| umt5_xxl_fp8_e4m3fn_scaled.safetensors | clip/ | 6.3G |
| clip_vision_h.safetensors | clip_vision/ | 2.4G |

## 五、磁盘规划

| GPU 显存 | 数据盘最低 | 推荐 |
|----------|-----------|------|
| 24G (4090) | 100G | 150G |
| 32G (5090) | 150G | 200G |

Wan2.1 全套模型约 25-30G，加上 ComfyUI 和插件约 10G。
**系统盘只有 30G，所有操作必须在数据盘。**

## 六、连接 Pixelle-Video

1. SSH 隧道连 6006 → `http://127.0.0.1:6006`
2. `config.yaml` 填 `url: "http://127.0.0.1:6006"`
3. 工作流放入 `workflows/selfhost/`，文件名以 `video_` 或 `image_` 开头

## 七、从零到出图完整时间线

| 步骤 | 耗时 |
|------|------|
| 选镜像开机 | 2min |
| 装插件 | 2min |
| 下模型(国内) | 15-30min |
| 导入工作流 | 1min |
| 首次测试 | 2-5min |

总计约 30-40 分钟。

## 八、与 zeaman 对比

| | zealman 应用市场 | 自建 |
|------|------|------|
| 速度 | 5分钟 | 30分钟 |
| 可控性 | 低（依赖第三方） | 高 |
| 可迁移 | 差（镜像锁死） | 好（任何平台） |
| 工作流 | 200+ 预置 | 需自己找 |
