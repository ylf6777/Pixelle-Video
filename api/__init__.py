# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Pixelle-Video API 层

基于 FastAPI 的 REST API，提供视频生成、LLM 对话、TTS 合成等服务的 HTTP 接口。

子包结构::

    api/
      ├── __init__.py          — 本文件，包入口
      ├── app.py               — FastAPI 应用入口（路由注册、lifespan、中间件）
      ├── config.py            — API 配置（APIConfig）
      ├── dependencies.py      — 依赖注入（PixelleVideoDep）
      ├── error_handler.py     — 异常→HTTP 状态码映射
      ├── routers/             — 路由模块
      │   ├── health.py        — 健康检查 /health, /version
      │   ├── llm.py           — LLM 对话 /api/llm/chat
      │   ├── tts.py           — TTS 合成 /api/tts/synthesize
      │   ├── image.py         — 图片生成 /api/image/generate
      │   ├── content.py       — 内容生成 /api/content/*
      │   ├── video.py         — 视频生成 /api/video/generate/*
      │   ├── tasks.py         — 任务管理 /api/tasks/*
      │   ├── files.py         — 文件服务 /api/files/*
      │   ├── resources.py     — 资源发现 /api/resources/*
      │   └── frame.py         — 帧渲染 /api/frame/*
      ├── schemas/             — Pydantic 数据模型
      │   ├── base.py          — 基础响应模型
      │   ├── llm.py           — LLM 请求/响应
      │   ├── tts.py           — TTS 请求/响应
      │   ├── image.py         — 图片生成请求/响应
      │   ├── content.py       — 内容生成请求/响应
      │   ├── video.py         — 视频生成请求/响应
      │   ├── frame.py         — 帧渲染请求/响应
      │   └── resources.py     — 资源发现请求/响应
      └── tasks/               — 异步任务管理
          ├── __init__.py      — 公共接口导出
          ├── manager.py       — TaskManager 核心逻辑
          └── models.py        — Task/TaskStatus/TaskType 数据模型
"""
