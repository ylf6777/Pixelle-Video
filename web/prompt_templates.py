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
Prompt template definitions for the style config dropdown.

All built-in template prompts are defined here so they can be updated
without touching the UI code in style_config.py.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PromptTemplate:
    """一个命名的提示词模板定义"""
    name_key: str                        # i18n 翻译键
    prompt: str                          # 实际的提示词前缀内容
    locked: bool = True                  # True = 普通用户不可编辑
    frame_template: Optional[str] = None # 绑定的画面模板路径
    fixed_params: Optional[Dict[str, str]] = None  # 固定模板参数
    tts_voice: Optional[str] = None      # 绑定的 TTS 语音 ID
    tts_speed: Optional[float] = None    # 绑定的 TTS 语速


# ---------------------------------------------------------------------------
# 内置模板注册表
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATES: Dict[str, PromptTemplate] = {
    "template_xiaojun": PromptTemplate(
        name_key="style.template_name.xiaojun",
        prompt=(
            "Rough shaky outlines, uneven crayon coloring with visible grain texture, "
            "paper background texture like a sketchbook page, chibi-style big round eyes, "
            "lots of hand-drawn doodle symbols and stars and hearts, "
            "cute messy scrapbook aesthetic like a 10-year-old's sketchbook, "
            "photo-to-doodle effect, no text no letters no speech bubbles in the image, "
            "just the characters and scene, main characters: young mom with messy bun hair "
            "and tired eyes, little boy with round cheeks, everyday family moments"
        ),
        locked=True,
        frame_template="1080x1920/image_default.html",
        fixed_params={
            "author": "晓君老师",
            "brand": "育儿小窍门",
            "describe": "喜欢我，关注我！！",
        },
        tts_voice="zh-CN-XiaoxiaoNeural",
        tts_speed=1.0,
    ),
    "template_elderly": PromptTemplate(
        name_key="style.template_name.elderly",
        prompt=(
            "warm watercolor illustration, soft natural light coming through the window, "
            "warm muted tones of cream, light brown and pale green, cozy home atmosphere, "
            "healthy food theme, suitable for middle-aged and elderly aesthetic"
        ),
        locked=True,
        frame_template="1080x1920/image_fashion_vintage.html",
        fixed_params={},
        tts_voice="zh-CN-XiaoxiaoNeural",
        tts_speed=0.8,
    ),
}

# 自定义模板保留键
CUSTOM_TEMPLATE_KEY = "template_custom"
CUSTOM_TEMPLATE_NAME_KEY = "style.template_name.custom"


def get_template_prompt(template_key: str) -> str:
    """获取指定模板键的提示词文本"""
    if template_key == CUSTOM_TEMPLATE_KEY:
        return ""
    tpl = BUILTIN_TEMPLATES.get(template_key)
    return tpl.prompt if tpl else ""


def get_template_name(template_key: str, tr_func) -> str:
    """获取模板键的翻译后显示名称"""
    if template_key == CUSTOM_TEMPLATE_KEY:
        return tr_func(CUSTOM_TEMPLATE_NAME_KEY)
    tpl = BUILTIN_TEMPLATES.get(template_key)
    return tr_func(tpl.name_key) if tpl else template_key


def is_template_locked(template_key: str) -> bool:
    """检查模板是否被锁定（普通用户不可编辑）"""
    if template_key == CUSTOM_TEMPLATE_KEY:
        return False
    tpl = BUILTIN_TEMPLATES.get(template_key)
    return tpl.locked if tpl else True


def check_edit_permission() -> bool:
    """检查当前用户是否有编辑内置模板的权限

    满足以下任一条件即可：
    - 环境变量 PIXELLE_VIDEO_DEV_MODE 设为真值
    - 环境变量 PIXELLE_VIDEO_EDIT_TEMPLATES 设为真值
    - st.session_state 中 can_edit_templates 为 True
    """
    if os.environ.get("PIXELLE_VIDEO_DEV_MODE", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("PIXELLE_VIDEO_EDIT_TEMPLATES", "").strip().lower() in ("1", "true", "yes"):
        return True
    try:
        import streamlit as st
        if st.session_state.get("can_edit_templates", False):
            return True
    except Exception:
        pass
    return False


def get_template_binding(template_key: str) -> Optional[PromptTemplate]:
    """获取模板的绑定信息（画面模板 + 固定参数），自定义模板返回 None"""
    if template_key == CUSTOM_TEMPLATE_KEY:
        return None
    tpl = BUILTIN_TEMPLATES.get(template_key)
    if tpl and tpl.frame_template:
        return tpl
    return None


def get_template_choices(tr_func) -> List[Tuple[str, str]]:
    """构建下拉菜单的 (key, display_name) 选项列表"""
    choices = []
    for key, tpl in BUILTIN_TEMPLATES.items():
        choices.append((key, tr_func(tpl.name_key)))
    choices.append((CUSTOM_TEMPLATE_KEY, tr_func(CUSTOM_TEMPLATE_NAME_KEY)))
    return choices
