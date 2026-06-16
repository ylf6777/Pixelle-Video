# zealman 面板 API 清单（实测版本）

**BASE_URL**: `https://{instance}.bjb2.seetacloud.com:8443`（每次重启会变）
**鉴权**: 无（面板自动绑定 AutoDL 实例，局域网级别安全）
**跨域**: 已启用 CORS

## 工作流 API

### POST /api/workflow/generate — 提交生成任务
```json
// Request
{
  "workflow_id": "G03-图生视频-Wan2.2SmoothMix",  // 面板保存的工作流名
  "input_values": {
    "52:image": "test.jpg",        // 节点ID:字段名（先上传拿name）
    "88:value": "提示词内容"
  },
  "client_id": "optional-client-id"
}

// Response
{"success": true, "prompt_id": "d1e7a2b8-..."}
```

### GET /api/workflow/result?prompt_id={pid} — 轮询结果
```json
// pending=true 时
{"success": true, "pending": true}

// pending=false 时
{
  "success": true, "pending": false,
  "results": [
    {"type": "video", "url": "/output/2026/video.mp4"},
    {"type": "image", "url": "/output/2026/image.png"}
  ]
}
```
轮询间隔建议 2-3秒，视频生成 60-180s

### GET /api/workflow/list — 列出所有已保存工作流
### GET /api/workflow/config/{id} — 获取工作流配置（含 enabledParams）
### POST /api/workflow/save — 保存工作流配置
### PUT /api/workflow/rename — 重命名
### DELETE /api/workflow/{id} — 删除

## 文件上传 API

### POST /api/comfy/upload/image — 上传图片
multipart/form-data, 字段名 `image`
```json
// Response
{"name": "test.jpg", "subfolder": "", "type": "input"}
```
### POST /api/comfy/upload/file — 通用文件上传
兼容 `file`/`image`/`video`/`audio` 字段名

## 控制面板 API

### GET /api/health — 健康检查 `{"status":"ok","uptime":3600}`
### GET /api/gpu/info — GPU 信息 `{"gpuName":"RTX 5090","isRTX5090":true}`
### GET /api/comfy/status — ComfyUI 状态 `{"running":true,"port":6006}`
### POST /api/comfy/start — 启动 ComfyUI `{"useProxy":true,"proxyType":"network_turbo"}`
### POST /api/comfy/stop — 停止 ComfyUI
### GET /api/disk/size — 磁盘使用

## 关键参数命名规则

- 格式: `{nodeID}:{fieldName}`
- **不是 text 是 value**：PrimitiveStringMultiline → `88:value`
- **是 text**：CLIPTextEncode → `754:text`
- **是 image**：LoadImage → `52:image`
- 去 `/api/workflow/config/{id}` 查 `enabledParams` 确认

## 错误码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 参数错误（缺少 workflow_template/无效 input_values） |
| 404 | 端点不存在或实例地址已变 |
| 405 | 方法不允许（GET 用了 POST 端点） |
| 422 | 请求体过大（图片 base64 超限） |
| 500 | 服务器内部错误（通常是 ComfyUI 挂了） |
