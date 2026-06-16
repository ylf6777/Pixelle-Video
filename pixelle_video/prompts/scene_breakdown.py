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
分镜拆解提示词模板（Scene Breakdown Prompt Templates）

提供两种模式的独立提示词：
- IMAGE 模式：生成带 image_prompts 的分镜
- VIDEO 模式：生成带 video_prompts 的分镜

每个分镜包含旁白和根据字数自动分配的媒体提示词。
"""

# ══════════════════════════════════════════════════════════════════════════
# 生图模式 — 分镜拆解
# ══════════════════════════════════════════════════════════════════════════

SCENE_BREAKDOWN_IMAGE_PROMPT = """你是专业分镜师兼口播文案。把下面文章拆成若干个分镜，分镜数量根据文章长度和内容复杂度自动决定。

【旁白-插画匹配规则】

1. 每条分镜先写旁白，再根据旁白字数配画面：
   - 旁白≤30字：配 1 幅画面
   - 旁白31-60字：配 2 幅画面（第1幅引入场景，第2幅展开内容）
   - 旁白61-100字：配 3 幅画面（引入→展开→收尾升华）
   - 旁白>100字：配 4 幅画面

2. 多幅画面要求：
   - 所有画面围绕同一条旁白的核心主题
   - 风格统一、色调一致、同一人物形象
   - 构图有变化：远景→中景→特写，避免单调

3. 画面提示词要求：
   - 用中文，日式漫画分镜风格，画面中有对话气泡
   - 中国场景和人物，crayon doodle scrapbook 风格

4. 旁白要求：
   - 长度由内容自然决定，不设限制，分镜时长跟随旁白长度
   - 所有旁白连起来是一篇完整流畅的口播稿，有开头有过渡有结尾
   - 像朋友聊天，自然口语

5. 只返回 JSON 数组：
[{{"narration": "旁白1", "image_prompts": ["画面1"]}}, {{"narration": "旁白2", "image_prompts": ["画面1", "画面2"]}}]

文章：
{article}"""


# ══════════════════════════════════════════════════════════════════════════
# 视频模式 — 分镜拆解
# ══════════════════════════════════════════════════════════════════════════

SCENE_BREAKDOWN_VIDEO_PROMPT = """你是专业分镜师兼口播文案。把下面文章拆成若干个分镜用于视频生成，分镜数量根据文章长度和内容复杂度自动决定。

【旁白-视频片段匹配规则】

1. 每条分镜先写旁白，再根据旁白字数配视频片段：
   - 旁白≤30字：配 1 个视频片段
   - 旁白31-60字：配 2 个视频片段（第1段引入场景，第2段展开内容）
   - 旁白61-100字：配 3 个视频片段（引入→展开→收尾升华）
   - 旁白>100字：配 4 个视频片段

2. 多视频片段要求：
   - 所有片段围绕同一条旁白的核心主题
   - 风格统一、色调一致、同一人物形象
   - 镜头运动有变化：固定→推拉→摇移，避免单调

3. 视频提示词要求：
   - 用中文描述画面内容和镜头运动
   - 突出动态元素：人物动作、物体运动、镜头运动（推拉摇移）、场景转换
   - 中国场景和人物，温暖治愈的视觉风格

4. 旁白要求：
   - 长度由内容自然决定，不设限制，分镜时长跟随旁白长度
   - 所有旁白连起来是一篇完整流畅的口播稿，有开头有过渡有结尾
   - 像朋友聊天，自然口语

5. 只返回 JSON 数组：
[{{"narration": "旁白1", "video_prompts": ["视频提示词1"]}}, {{"narration": "旁白2", "video_prompts": ["视频提示词1", "视频提示词2"]}}]

文章：
{article}"""


# ══════════════════════════════════════════════════════════════════════════
# 构建函数
# ══════════════════════════════════════════════════════════════════════════

def build_scene_breakdown_prompt(article: str, media_type: str = "image") -> str:
    """
    根据媒体类型返回对应的分镜拆解提示词。

    根据 media_type 选择 IMAGE 或 VIDEO 模板，将文章内容填入模板，
    返回完整的 LLM 提示词。

    Args:
        article: 待拆解的文章内容
        media_type: 媒体类型，"image" 为生图模式，"video" 为视频模式

    Returns:
        完整的提示词字符串，已填充文章内容

    Raises:
        KeyError: 如果模板中的 {article} 变量无法被 format() 替换

    Requires:
        - article 为非空字符串
        - media_type 为 "image" 或 "video"

    Side Effects:
        无（纯函数，仅做字符串格式化）
    """
    template = (
        SCENE_BREAKDOWN_VIDEO_PROMPT
        if media_type == "video"
        else SCENE_BREAKDOWN_IMAGE_PROMPT
    )
    return template.format(article=article)
