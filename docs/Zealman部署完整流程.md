# Zealman ComfyUI 部署与 Pixelle-Video 集成流程

## 一、租用镜像（5分钟）

1. **AutoDL 应用市场** → 搜 `zealman` → 选最新版 V8.8
2. 显卡选 4090/5090 → **从应用市场部署**（不能从算力市场！）
3. 开机后进入控制面板（6008端口）→ 点「启动 ComfyUI」
4. 等面板显示 ComfyUI 运行中

## 二、本地连接

**SSH 隧道**（开机后每次都要做）：
- AutoDL-SSH-Tools → 填 SSH 指令 + 密码 → 代理端口 6006
- 浏览器打开 `http://127.0.0.1:6006` 确认 ComfyUI 可见

## 三、工作流测试（在 ComfyUI GUI 里做）

1. 打开 ComfyUI 网页 → 菜单加载工作流
2. 修改模型名（如果镜像没自动配好）：
   - WanVideoModelLoader → 选正确的模型文件
   - WanVideoVAELoader → 选 `wan_2.1_vae.safetensors`
   - LoadWanVideoT5TextEncoder → 选 `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
3. 上传测试图 → 填提示词 → Queue Prompt → **确认能出视频**

## 四、配置 API 参数（在面板里做）

1. 打开 zealman 控制面板 → **API 生成** → 找到跑通的工作流
2. 勾选需要外部控制的参数（图片节点、提示词节点）
3. 保存 → 记下 `workflow_id`

## 五、确认 API 参数名（最重要的步骤）

**GUI 显示的名字 ≠ API 参数名！**

去面板查 `/api/workflow/config/{workflow_id}`，确认：
- 图片节点的 ID 和字段名（如 `52:image`）
- 提示词节点的 ID 和字段名（如 `88:value`，不是 `88:text`！）

## 六、放入 Pixelle-Video

1. ComfyUI 里 Export → API Format → 保存到 `workflows/selfhost/`
2. 给 LoadImage 加 `_meta.title = "$image.path"`
3. 给提示词节点加 `_meta.title = "$prompt.value!"`（注意字段名）
4. 文件名以 `video_` 或 `image_` 开头
5. Pixelle-Video → 本地 ComfyUI → `http://127.0.0.1:6006` → 选工作流

## 七、API 直连（可选，不需要隧道）

```python
B = "https://uu1021136-781466526648.bjb2.seetacloud.com:8443"  # 每次开机会变

# 上传图片
POST /api/comfy/upload/file  (multipart)
# 返回 {"name": "xxx.jpg"}

# 提交任务
POST /api/workflow/generate
{
    "workflow_id": "G03-图生视频-Wan2.2SmoothMix",
    "input_values": {"52:image": "xxx.jpg", "88:value": "提示词"}
}

# 轮询结果
GET /api/workflow/result?prompt_id=xxx
# pending=false 时取 results[].url
```

## 踩坑记录

1. **应用市场 vs 算力市场**：必须从应用市场部署，算力市场的进不去面板
2. **GUI ID ≠ API ID**：GUI 里显示 52:image，API 里可能是 52:image 或 132:90:image
3. **字段名不是 text**：PrimitiveStringMultiline 的字段是 `value`，CLIPTextEncode 的字段是 `text`
4. **地址会变**：每次重启 AutoDL 实例，8443 面板地址会变
5. **先 GUI 跑通再 API**：不要在 API 上试错，GUI 跑通确认工作流没问题再配 API
