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
帧/模板渲染端点

提供单帧渲染和模板参数查询接口。
使用 HTML 模板 + Playwright 浏览器引擎进行帧渲染。
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.error_handler import map_exception
from api.dependencies import PixelleVideoDep
from api.schemas.frame import FrameRenderRequest, FrameRenderResponse, TemplateParamsResponse
from pixelle_video.services.frame_html import HTMLFrameGenerator
from pixelle_video.utils.template_util import parse_template_size, resolve_template_path

router = APIRouter(prefix="/frame", tags=["Frame Rendering"])


@router.post("/render", response_model=FrameRenderResponse)
async def render_frame(
    request: FrameRenderRequest,
    pixelle_video: PixelleVideoDep
):
    """
    使用 HTML 模板渲染单帧

    将模板、标题、文本和图片组合生成一张帧图片。
    适用于预览模板效果或生成自定义帧。

    入参（FrameRenderRequest）:
        - **template** (str): 模板 key。如 '1080x1920/default.html'。必填
        - **title** (str, optional): 帧标题
        - **text** (str): 帧文本内容，必填
        - **image** (str, optional): 图片路径（可以是本地路径或 URL）

    Returns:
        FrameRenderResponse: 包含以下字段：
            - frame_path (str): 生成的帧图片路径
            - width (int): 帧宽度（像素）
            - height (int): 帧高度（像素）

    Raises:
        HTTPException 400: ValueError — 参数无效（template 路径不存在等）
        HTTPException 500: 内部服务错误 — Playwright 渲染失败

    Requires:
        - HTMLFrameGenerator        — pixelle_video.services.frame_html 中的渲染引擎
        - resolve_template_path      — pixelle_video.utils.template_util 中的路径解析工具
        - parse_template_size        — 同上，从模板中解析尺寸
        - Playwright 浏览器          — HTMLFrameGenerator 依赖的无头浏览器

    Side Effects:
        - 启动或复用 Playwright 浏览器实例
        - 渲染 HTML 页面为 PNG 图片
        - 图片写入磁盘（output 目录）
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"帧渲染请求: template={request.template}")

        # 解析模板路径（返回带 "templates/" 或 "data/templates/" 前缀的绝对路径）
        template_path = resolve_template_path(request.template)

        # 从模板中解析尺寸
        width, height = parse_template_size(template_path)

        # 创建 HTML 帧生成器
        generator = HTMLFrameGenerator(template_path)

        # 生成帧图片
        frame_path = await generator.generate_frame(
            title=request.title,
            text=request.text,
            image=request.image
        )

        return FrameRenderResponse(
            frame_path=frame_path,
            width=width,
            height=height
        )

    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "frame")


@router.get("/template/params", response_model=TemplateParamsResponse)
async def get_template_params(
    template: str
):
    """
    获取模板的自定义参数

    返回模板 HTML 文件中定义的所有可配置参数及其类型和默认值。
    这些参数可通过视频生成请求中的 ``template_params`` 字段传入。

    模板参数语法（在 HTML 中使用）::

        {{param_name:type=default}}

    支持的参数类型:
        - ``text``   — 字符串输入
        - ``number`` — 数值输入
        - ``color``  — 颜色选择器（hex 格式，如 #ff0000）
        - ``bool``   — 布尔复选框

    Args:
        template (str): 模板路径。
            如 '1080x1920/image_default.html'。必填的查询参数。

    Returns:
        TemplateParamsResponse: 包含以下字段：
            - template (str): 模板路径
            - media_width (int): 模板 meta 标签中定义的媒体宽度
            - media_height (int): 模板 meta 标签中定义的媒体高度
            - params (Dict[str, TemplateParamConfig]): 参数名到配置的映射。
              每个配置包含 type、default、label 字段。

    Raises:
        HTTPException 404: 模板文件不存在 — 模板路径解析失败
        HTTPException 500: 内部服务错误 — 模板解析失败

    Requires:
        - HTMLFrameGenerator        — 用于解析模板中的 {{param:type=default}} 语法
        - resolve_template_path      — 解析模板路径
        - templates/ 目录            — 模板文件必须存在

    Side Effects:
        - 读取 HTML 模板文件（文件 I/O）
        - 记录 info 级别请求日志
    """
    try:
        logger.info(f"获取模板参数: {template}")

        # 解析模板路径
        template_path = resolve_template_path(template)

        # 创建生成器并解析参数
        generator = HTMLFrameGenerator(template_path)
        params = generator.parse_template_parameters()
        media_width, media_height = generator.get_media_size()

        return TemplateParamsResponse(
            template=template,
            media_width=media_width,
            media_height=media_height,
            params=params
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"模板未找到: {template}")
    except HTTPException:
        raise
    except Exception as e:
        raise map_exception(e, "frame")
