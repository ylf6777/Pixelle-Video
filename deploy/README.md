# ylf_Video 部署指南

## 快速部署

### 1. 安装依赖
```bash
git clone <repo-url> /opt/ylf_video
cd /opt/ylf_video
uv sync
```

### 2. 配置
```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 LLM API Key 和 ComfyUI 地址
```

### 3. 启动服务
```bash
# 开发模式（直接运行）
uv run python api/app.py --host 0.0.0.0 --port 8000

# 生产模式（systemd 守护）
sudo cp deploy/systemd/ylf-video.service /etc/systemd/system/
sudo useradd -r -s /bin/false ylf-video
sudo chown -R ylf-video:ylf-video /opt/ylf_video
sudo systemctl daemon-reload
sudo systemctl enable --now ylf-video
```

### 4. 配置 Nginx（可选，推荐）
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/ylf_video
# 编辑 server_name
sudo ln -s /etc/nginx/sites-available/ylf_video /etc/nginx/sites-enabled/
sudo nginx -t && sudo nginx -s reload
```

### 5. 验证
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/workflows | jq length
```

## 日志
```bash
# 应用日志
tail -f logs/ylf_video_$(date +%Y-%m-%d).log

# systemd 日志
sudo journalctl -u ylf-video -f

# Nginx 日志
sudo tail -f /var/log/nginx/ylf_video_access.log
```

## 更新
```bash
cd /opt/ylf_video
git pull
sudo systemctl restart ylf-video
```
