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
提示词包（Prompts Package）

集中管理所有 LLM 交互的提示词模板。
每个子模块提供一个 `build_xxx_prompt()` 函数，
用于将参数格式化到提示词模板中。

子模块:
    - topic_narration: 从话题/主题生成旁白
    - content_narration: 从用户提供的内容生成旁白
    - title_generation: 从内容生成短视频标题
    - image_generation: 从旁白生成英文图像提示词
    - style_conversion: 将自定义风格描述转换为图像提示词
    - video_generation: 从旁白生成英文视频提示词
    - scene_breakdown: 将文章拆为分镜（含每镜提示词）
    - asset_script_generation: 从用户素材生成视频脚本

Requires:
    - Python 3.10+

Side Effects:
    - 无（纯模块导入，无副作用）
"""

# 旁白提示词
from pixelle_video.prompts.topic_narration import build_topic_narration_prompt
from pixelle_video.prompts.content_narration import build_content_narration_prompt
from pixelle_video.prompts.title_generation import build_title_generation_prompt

# 图像提示词
from pixelle_video.prompts.image_generation import build_image_prompt_prompt
from pixelle_video.prompts.style_conversion import build_style_conversion_prompt

# 视频提示词
from pixelle_video.prompts.video_generation import build_video_prompt_prompt

# 分镜拆解
from pixelle_video.prompts.scene_breakdown import build_scene_breakdown_prompt


__all__ = [
    # 旁白构建器
    "build_topic_narration_prompt",
    "build_content_narration_prompt",
    "build_title_generation_prompt",

    # 图像构建器
    "build_image_prompt_prompt",
    "build_style_conversion_prompt",

    # 视频构建器
    "build_video_prompt_prompt",

    # 分镜拆解
    "build_scene_breakdown_prompt",
]
