# ComfyUI 工作流批量部署手册

## 环境信息

- **服务器**: AutoDL 内蒙B区 RTX 4090 24G
- **ComfyUI 路径**: `/root/autodl-tmp/ComfyUI`
- **工作流目录**: `/root/autodl-tmp/ComfyUI/user/default/workflows/pixelle/`
- **模型路径**: `/root/autodl-tmp/models/`（软链到 `ComfyUI/models/`）
- **服务端口**: 6006

## 已安装模型

| 类型 | 模型文件 | 用途 |
|------|---------|------|
| DiT | `svdq-int4_r128-qwen-image-lightningv1.1-8steps.safetensors` | Qwen Image 生图 |
| DiT | `svdq-int4_r128-qwen-image-edit-2509-lightningv2.0-4steps.safetensors` | Qwen Image 编辑 |
| CLIP | `qwen_2.5_vl_7b_fp8_scaled.safetensors` | Qwen 文本编码 |
| VAE | `qwen_image_vae.safetensors` | Qwen 图像解码 |
| VAE | `sdxl_vae_fp16_fix.safetensors` | SDXL 图像解码 |

## 工作流状态（28个）

### 可正常提交（20个）

| 工作流 | 类型 | 状态 |
|--------|------|------|
| `image_qwen.json` | Qwen 生图 | ✅ 已验证 |
| `image_qwen_chinese_cartoon.json` | Qwen 国风生图 | ✅ |
| `image_Z-image.json` | Z-Image 生图 | ✅ |
| `image_nano_banana.json` | Nano Banana 生图 | ✅ |
| `image_flux2.json` | Flux2 生图 | ✅ 需 Flux 模型 |
| `image_sd3.5.json` | SD3.5 生图 | ✅ 需 SD3.5 模型 |
| `image_sdxl.json` | SDXL 生图 | ✅ 需 SDXL 模型 |
| `video_wan2.2.json` | Wan2.2 视频 | ✅ 需 Wan 模型 |
| `video_qwen_wan2.2.json` | Qwen+Wan 视频 | ✅ 需 Wan 模型 |
| `video_Z_image_wan2.2.json` | Z-Image+Wan 视频 | ✅ 需 Wan 模型 |
| `video_understanding.json` | 视频理解 | ✅ |
| `analyse_video.json` | 视频分析 | ✅ |
| `af_scail.json` | AF Scail | ✅ |
| `i2v_LTX2.json` | 图生视频 LTX2 | ✅ 需 LTX2 模型 |
| `digital_combination.json` | 数字人组合 | ✅ |
| `digital_customize.json` | 数字人自定义 | ✅ |
| `tts_edge.json` | TTS Edge | ✅ |
| `tts_index2.json` | TTS Index2 | ✅ |
| `tts_spark.json` | TTS Spark | ✅ |
| `infinitetalk_runninghub.json` | InfiniteTalk | ✅ |

### 需补充模型（8个）

| 工作流 | 失败原因 |
|--------|---------|
| `image_flux.json` | 缺少 Flux unet 模型 |
| `analyse_image.json` | 需要特定模型 |
| `video_wan2.1_fusionx.json` | 缺少 Wan2.1 模型 |
| `digital_human_sonic.json` | 缺少 Sonic 模型 |
| `digital_image.json` | 缺少特定模型 |
| `daVinci-MagiHuman...json` | 需要 MagiHuman 模型 |
| 对口型数字人...json | 500 服务器错误 |
| 最强开源数字人...json | 500 服务器错误 |

## 批量部署命令

### 1. 上传本机工作流到服务器

```bash
# 在服务器上创建目录
mkdir -p /root/autodl-tmp/ComfyUI/user/default/workflows/pixelle

# 本机执行上传（scp 或 paramiko 脚本）
python tools/batch_deploy_workflows.py
```

### 2. 重启 ComfyUI 加载新工作流

```bash
kill $(pgrep -f "main.py")
cd /root/autodl-tmp/ComfyUI
nohup python main.py --listen 0.0.0.0 --port 6006 > /tmp/comfyui.log 2>&1 &
```

### 3. 批量测试工作流

```bash
# 服务器上执行
for f in /root/autodl-tmp/ComfyUI/user/default/workflows/pixelle/*.json; do
  echo "Testing: $(basename $f)"
  curl -s -X POST http://127.0.0.1:6006/prompt \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": $(cat $f), \"client_id\": \"test\"}" \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print('OK' if not r.get('node_errors') else f'FAIL: {r[\"node_errors\"]}')"
done
```

## 常用故障排查

### 工作流加载报 "node XXX does not exist"
- 缺少自定义节点 → `cd custom_nodes && git clone <节点仓库>`
- 重启 ComfyUI

### 模型文件缺失
```bash
# 检查模型
ls /root/autodl-tmp/ComfyUI/models/unet/
ls /root/autodl-tmp/ComfyUI/models/clip/
ls /root/autodl-tmp/ComfyUI/models/vae/

# 下载 Flux 模型（示例）
wget -O unet/flux1-dev.safetensors \
  https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors
```

### GPU 内存不足
- `cpu_offload` 设为 `auto` 或 `enable`
- 降低分辨率（1024→768→512）
- 减少 `num_blocks_on_gpu`

### ComfyUI 不响应
```bash
# 查看日志
tail -f /tmp/comfyui.log

# 检查进程
ps aux | grep main.py

# 强制重启
kill -9 $(pgrep -f "main.py")
cd /root/autodl-tmp/ComfyUI && python main.py --listen 0.0.0.0 --port 6006
```

## 新增工作流步骤

1. 本机 `workflows/selfhost/` 放入新 .json
2. 运行 `python tools/batch_deploy_workflows.py`
3. 检查测试结果，下载缺失模型
4. Pixelle-Video 界面重启后即可看到新工作流
