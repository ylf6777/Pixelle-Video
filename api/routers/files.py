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
文件服务端点

提供对生成文件和资源文件的 HTTP 访问。
支持视频、音频、图片、HTML 模板、JSON 工作流等多种文件类型。

安全策略:
    仅允许访问以下目录中的文件（白名单机制）：
    - output/       — 生成的文件（视频、图片、音频）
    - workflows/     — ComfyUI 工作流文件
    - templates/     — HTML 模板文件
    - bgm/           — 背景音乐文件
    - data/bgm/      — 用户自定义背景音乐
    - data/templates/— 用户自定义模板
    - resources/     — 其他资源文件
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from api.error_handler import map_exception

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/{file_path:path}")
async def get_file(file_path: str):
    """
    按路径获取文件

    从允许的目录中通过相对路径提供文件访问。
    支持内联预览（浏览器直接显示）和下载。

    入参:
        - **file_path** (str): 相对于允许目录的文件路径。
            如果不以任何允许的目录前缀开头，默认假定位于 output/ 下。

        路径示例:
            - ``"abc123.mp4"`` → output/abc123.mp4
            - ``"workflows/runninghub/image_flux.json"``
            - ``"templates/1080x1920/default.html"``
            - ``"bgm/default.mp3"``
            - ``"resources/example.png"``

    Returns:
        FileResponse: 文件响应，包含适当的 Content-Type 和 Content-Disposition 头。
            浏览器可直接预览图片/视频/音频，HTML/JSON 可在线查看。

    Raises:
        HTTPException 400: 路径指向的不是文件（是目录）
        HTTPException 403: 访问被拒绝 — 路径不在允许的白名单目录中
        HTTPException 404: 文件不存在 — 路径对应的文件未找到

    Requires:
        - 文件系统           — 允许目录必须存在于当前工作目录下
        - Path.cwd()        — 用于构建绝对路径和相对路径校验

    Side Effects:
        - 读取文件系统中的文件（文件 I/O）
        - 根据文件后缀自动设置 MIME 类型
    """
    try:
        # 定义允许访问的目录（按优先级顺序）
        allowed_prefixes = [
            "output/",
            "workflows/",
            "templates/",
            "bgm/",
            "data/bgm/",
            "data/templates/",
            "resources/",
        ]

        # 检查路径是否以允许的前缀开头，否则默认尝试 output/
        full_path = None
        for prefix in allowed_prefixes:
            if file_path.startswith(prefix):
                full_path = file_path
                break

        # 没有匹配的前缀时，假定在 output/ 下（向后兼容）
        if full_path is None:
            full_path = f"output/{file_path}"

        abs_path = Path.cwd() / full_path

        if not abs_path.exists():
            raise HTTPException(status_code=404, detail=f"文件未找到: {file_path}")

        if not abs_path.is_file():
            raise HTTPException(status_code=400, detail=f"路径不是文件: {file_path}")

        # 安全检查：仅允许访问白名单目录中的文件
        try:
            rel_path = abs_path.relative_to(Path.cwd())
            rel_path_str = str(rel_path)

            # 检查路径是否以任意允许的前缀开头
            is_allowed = any(rel_path_str.startswith(prefix.rstrip('/')) for prefix in allowed_prefixes)

            if not is_allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"访问被拒绝: 仅允许访问 {', '.join(p.rstrip('/') for p in allowed_prefixes)} 目录"
                )
        except ValueError:
            raise HTTPException(status_code=403, detail="访问被拒绝")

        # 根据文件后缀确定 MIME 类型
        suffix = abs_path.suffix.lower()
        media_types = {
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.html': 'text/html',
            '.json': 'application/json',
        }
        media_type = media_types.get(suffix, 'application/octet-stream')

        # 使用 inline 方式让浏览器预览（而非强制下载）
        return FileResponse(
            path=str(abs_path),
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{abs_path.name}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "files")
