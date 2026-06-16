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
HTML-based Frame Generator Service

Renders HTML templates to frame images using Playwright for headless browser rendering.

Linux Environment Requirements:
    - fontconfig package must be installed
    - Basic fonts (e.g., fonts-liberation, fonts-noto) recommended
    
    Ubuntu/Debian: sudo apt-get install -y fontconfig fonts-liberation fonts-noto-cjk
    CentOS/RHEL: sudo yum install -y fontconfig liberation-fonts google-noto-cjk-fonts
    
    Playwright browser install: playwright install --with-deps chromium
"""

import asyncio
import os
import re
import tempfile
import uuid
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger

from pixelle_video.utils.template_util import parse_template_size


class HTMLFrameGenerator:
    """
    基于 HTML 模板的帧图片生成器

    使用 Playwright 无头浏览器将 HTML 模板渲染为 PNG 帧图片，支持变量替换和自定义参数。

    Requires:
        - Playwright Chromium 浏览器已安装（playwright install --with-deps chromium）
        - Linux 环境需安装 fontconfig 及中文字体
    """
    
    _browser = None
    _playwright = None
    _browser_loop = None

    def __init__(self, template_path: str):
        """
        初始化 HTML 帧生成器，加载模板并解析尺寸

        Args:
            template_path: HTML 模板文件路径（如 "templates/1080x1920/default.html"）

        Side Effects:
            加载模板内容到 self.template，解析尺寸设置 self.width/self.height，检查 Linux 字体依赖
        """
        self.template_path = template_path
        self.template = self._load_template(template_path)
        
        # Parse video size from template path
        self.width, self.height = parse_template_size(template_path)
        
        self._check_linux_dependencies()
        logger.debug(f"Loaded HTML template: {template_path} (size: {self.width}x{self.height})")
    
    
    def _check_linux_dependencies(self):
        """
        检查 Linux 系统字体依赖（fontconfig），缺失时发出警告

        Side Effects:
            依赖缺失时通过 logger.warning 输出安装提示
        """
        if os.name != 'posix':
            return
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['fc-list'], 
                capture_output=True, 
                timeout=2
            )
            
            if result.returncode != 0:
                logger.warning(
                    "fontconfig not found or not working properly. "
                    "Install with: sudo apt-get install -y fontconfig fonts-liberation fonts-noto-cjk"
                )
            elif not result.stdout:
                logger.warning(
                    "No fonts detected by fontconfig. "
                    "Install fonts with: sudo apt-get install -y fonts-liberation fonts-noto-cjk"
                )
            else:
                logger.debug(f"Fontconfig detected {len(result.stdout.splitlines())} fonts")
                
        except FileNotFoundError:
            logger.warning(
                "fontconfig (fc-list) not found on system. "
                "Install with: sudo apt-get install -y fontconfig"
            )
        except Exception as e:
            logger.debug(f"Could not check fontconfig status: {e}")
    
    def _load_template(self, template_path: str) -> str:
        """
        从文件加载 HTML 模板内容

        Args:
            template_path: 模板文件路径

        Returns:
            HTML 模板字符串内容

        Raises:
            FileNotFoundError: 模板文件不存在时抛出
        """
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.debug(f"Template loaded: {len(content)} chars")
        return content
    
    def _parse_media_size_from_meta(self) -> tuple[Optional[int], Optional[int]]:
        """
        从模板的 meta 标签中解析媒体尺寸（用于图片/视频生成）

        查找 meta 标签：
        - <meta name="template:media-width" content="1024">
        - <meta name="template:media-height" content="1024">

        Returns:
            (width, height) 元组，未找到时返回 (None, None)
        """
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(self.template, 'html.parser')
            
            width_meta = soup.find('meta', attrs={'name': 'template:media-width'})
            height_meta = soup.find('meta', attrs={'name': 'template:media-height'})
            
            if width_meta and height_meta:
                width = int(width_meta.get('content', 0))
                height = int(height_meta.get('content', 0))
                
                if width > 0 and height > 0:
                    logger.debug(f"Found media size in meta tags: {width}x{height}")
                    return width, height
            
            return None, None
            
        except Exception as e:
            logger.warning(f"Failed to parse media size from meta tags: {e}")
            return None, None
    
    def get_media_size(self) -> tuple[int, int]:
        """
        获取图片/视频生成的媒体尺寸

        返回模板 meta 标签中指定的媒体尺寸，未指定时回退到 1024x1024。

        Returns:
            (width, height) 元组，默认为 (1024, 1024)
        """
        media_width, media_height = self._parse_media_size_from_meta()
        
        if media_width and media_height:
            return media_width, media_height
        
        logger.warning(f"No media size meta tags found in template {self.template_path}, using fallback 1024x1024")
        return 1024, 1024
    
    def parse_template_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        从 HTML 模板中解析自定义参数定义

        支持 DSL 语法：{{param:type=default}}
        - {{param}} → text 类型，无默认值
        - {{param=value}} → text 类型，带默认值
        - {{param:type}} → 指定类型，无默认值
        - {{param:type=value}} → 指定类型，带默认值

        支持类型：text, number, color, bool
        预设参数（title, text, image, index）会被跳过。

        Returns:
            自定义参数配置字典：
            {
                'param_name': {
                    'type': 'text' | 'number' | 'color' | 'bool',
                    'default': Any,
                    'label': str
                }
            }
        """
        PRESET_PARAMS = {'title', 'text', 'image', 'index'}
        
        PARAM_PATTERN = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-z]+))?(?:=([^}]+))?\}\}'
        
        params = {}
        
        for match in re.finditer(PARAM_PATTERN, self.template):
            param_name = match.group(1)
            param_type = match.group(2) or 'text'
            default_value = match.group(3)
            
            if param_name in PRESET_PARAMS:
                continue
            
            if param_name in params:
                continue
            
            if param_type not in {'text', 'number', 'color', 'bool'}:
                logger.warning(f"Unknown parameter type '{param_type}' for '{param_name}', defaulting to 'text'")
                param_type = 'text'
            
            parsed_default = self._parse_default_value(param_type, default_value)
            
            params[param_name] = {
                'type': param_type,
                'default': parsed_default,
                'label': param_name,
            }
        
        if params:
            logger.debug(f"Parsed {len(params)} custom parameter(s) from template: {list(params.keys())}")
        
        return params
    
    def _parse_default_value(self, param_type: str, value_str: Optional[str]) -> Any:
        """
        根据参数类型解析默认值字符串

        Args:
            param_type: 参数类型（text, number, color, bool）
            value_str: 要解析的字符串值（可为 None）

        Returns:
            对应类型的解析值，value_str 为 None 时返回类型默认值（text=""、number=0、color="#000000"、bool=False）
        """
        if value_str is None:
            return {
                'text': '',
                'number': 0,
                'color': '#000000',
                'bool': False,
            }.get(param_type, '')
        
        if param_type == 'number':
            try:
                if '.' in value_str:
                    return float(value_str)
                else:
                    return int(value_str)
            except ValueError:
                logger.warning(f"Invalid number value '{value_str}', using 0")
                return 0
        
        elif param_type == 'bool':
            return value_str.lower() in {'true', '1', 'yes', 'on'}
        
        elif param_type == 'color':
            if value_str.startswith('#'):
                return value_str
            else:
                return f'#{value_str}'
        
        else:  # text
            return value_str
    
    def _replace_parameters(self, html: str, values: Dict[str, Any]) -> str:
        """
        将模板中的参数占位符替换为实际值

        替换优先级：values 字典 > 占位符默认值 > 空字符串

        Args:
            html: HTML 模板内容
            values: 参数值字典

        Returns:
            占位符已被替换的 HTML 字符串
        """
        PARAM_PATTERN = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-z]+))?(?:=([^}]+))?\}\}'
        
        def replacer(match):
            param_name = match.group(1)
            param_type = match.group(2) or 'text'
            default_value_str = match.group(3)
            
            if param_name in values:
                value = values[param_name]
                if isinstance(value, bool):
                    return 'true' if value else 'false'
                return str(value) if value is not None else ''
            
            elif default_value_str:
                return default_value_str
            
            else:
                return ''
        
        return re.sub(PARAM_PATTERN, replacer, html)

    @classmethod
    async def _ensure_browser(cls):
        """
        延迟初始化共享的 Playwright Chromium 浏览器实例，自动处理跨事件循环重用

        Returns:
            Playwright Browser 实例

        Side Effects:
            设置类属性 _browser, _playwright, _browser_loop
        """
        current_loop = asyncio.get_running_loop()
        browser_usable = (
            cls._browser is not None
            and cls._browser_loop is current_loop
            and cls._browser.is_connected()
        )

        if not browser_usable:
            if cls._browser is not None and cls._browser_loop is not current_loop:
                logger.warning(
                    "Detected cross-loop Playwright browser reuse attempt; "
                    "recreating browser for current event loop"
                )

            cls._browser = None
            cls._playwright = None
            from playwright.async_api import async_playwright
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions',
                ]
            )
            cls._browser_loop = current_loop
            logger.debug("Initialized Playwright Chromium browser")
        return cls._browser

    @classmethod
    def _discard_browser_references(cls):
        """
        丢弃属于另一个事件循环的过期 Playwright 对象引用

        Side Effects:
            将 _browser, _playwright, _browser_loop_id 设为 None
        """
        cls._browser = None
        cls._playwright = None
        cls._browser_loop_id = None

    @classmethod
    async def _reset_browser(cls):
        """
        尽力重置过期或损坏的 Playwright 连接，关闭浏览器并停止 Playwright 实例

        Side Effects:
            关闭 _browser 和 _playwright，并将引用设为 None
        """
        if cls._browser:
            try:
                if cls._browser.is_connected():
                    await asyncio.wait_for(cls._browser.close(), timeout=5)
            except Exception as e:
                logger.debug(f"Ignoring error while closing stale browser: {e}")
            finally:
                cls._browser = None

        if cls._playwright:
            try:
                await asyncio.wait_for(cls._playwright.stop(), timeout=5)
            except Exception as e:
                logger.debug(f"Ignoring error while stopping stale Playwright: {e}")
            finally:
                cls._playwright = None
                cls._browser_loop_id = None

    @classmethod
    async def close_browser(cls):
        """
        关闭共享的浏览器实例（应在应用退出时调用）

        Side Effects:
            关闭 _browser 和 _playwright，引用设为 None
        """
        if cls._browser:
            await cls._browser.close()
            cls._browser = None
            cls._browser_loop = None
        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None
            logger.debug("Playwright browser closed")

    async def generate_frame(
        self,
        title: str,
        text: str,
        image: str,
        ext: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        从 HTML 模板生成帧图片，使用 Playwright 无头浏览器渲染

        Args:
            title: 视频标题
            text: 本帧旁白文本
            image: AI 生成图片的路径（支持相对路径、绝对路径或 HTTP URL）
            ext: 额外数据字典（content_title, content_author 等），优先级低于命名参数
            output_path: 自定义输出路径（None 时自动生成）

        Returns:
            生成的帧图片文件路径

        Raises:
            RuntimeError: HTML 渲染失败时抛出
        """
        if image and not image.startswith(('http://', 'https://', 'data:', 'file://')):
            image_path = Path(image)
            if not image_path.is_absolute():
                image_path = Path.cwd() / image
            
            if not image_path.exists():
                logger.warning(f"Image file not found: {image_path}")
            else:
                image = image_path.as_uri()
                logger.debug(f"Converted image path to: {image}")
        
        context = {
            "title": title,
            "text": text,
            "image": image,
        }

        if ext:
            context.update(ext)
            # 命名参数的优先级高于 ext，防止 ext 中的空值覆盖实际内容
            context["title"] = title
            context["text"] = text
            context["image"] = image
        
        html = self._replace_parameters(self.template, context)

        if output_path is None:
            from pixelle_video.utils.os_util import get_output_path
            output_filename = f"frame_{uuid.uuid4().hex[:16]}.png"
            output_path = get_output_path(output_filename)
        else:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        logger.debug(f"Rendering HTML template to {output_path} (size: {self.width}x{self.height})")
        tmp_html_path = None
        page = None
        try:
            try:
                browser = await self._ensure_browser()
                page = await browser.new_page(
                    viewport={'width': self.width, 'height': self.height},
                    device_scale_factor=1,
                )
            except Exception as e:
                logger.warning(f"Playwright browser connection failed, restarting once: {e}")
                await self._reset_browser()
                browser = await self._ensure_browser()
                page = await browser.new_page(
                    viewport={'width': self.width, 'height': self.height},
                    device_scale_factor=1,
                )

            try:
                # Write HTML to a temp file and navigate via file:// URL so that
                # local file:// image references are loaded under the same origin.
                fd, tmp_html_path = tempfile.mkstemp(suffix='.html', prefix='pv_frame_')
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(html)
                
                await page.goto(Path(tmp_html_path).as_uri(), wait_until='load', timeout=30000)
                await page.screenshot(path=output_path, type='png', omit_background=True)
            finally:
                if page:
                    await page.close()
                if tmp_html_path and os.path.exists(tmp_html_path):
                    os.unlink(tmp_html_path)
            
            logger.info(f"Frame generated: {output_path}")
            return output_path
            
        except Exception as e:
            logger.exception("Failed to render HTML template")
            raise RuntimeError(
                f"HTML rendering failed: {type(e).__name__}: {e}"
            ) from e
