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
风格转换提示词（Style Conversion Prompt）

用于将用户自定义的风格描述（支持任意语言）转换为
适合 Stable Diffusion / FLUX 模型的英文图像生成提示词。
"""


STYLE_CONVERSION_PROMPT = """Convert this style description into a detailed image generation prompt for Stable Diffusion/FLUX:

Style Description: {description}

Requirements:
- Focus on visual elements, colors, lighting, mood, atmosphere
- Be specific and detailed
- Use professional photography/art terminology
- Output ONLY the prompt in English (no explanations)
- Keep it under 100 words
- Use comma-separated descriptive phrases

Image Prompt:"""


def build_style_conversion_prompt(description: str) -> str:
    """
    构建风格转换提示词。

    将用户自定义的风格描述（任意语言）转换为适合
    Stable Diffusion/FLUX 模型的英文图像生成提示词。

    Args:
        description: 用户的风格描述文本（支持任意语言）

    Returns:
        格式化后的完整提示词字符串

    Raises:
        KeyError: 如果模板变量名与 .format() 参数不匹配

    Requires:
        - description 为非空字符串

    Side Effects:
        无（纯函数，仅做字符串格式化）

    Example:
        >>> build_style_conversion_prompt("赛博朋克风格，霓虹灯，未来感")
        # 返回提示词，LLM 将转换为英文图像生成提示词
    """
    return STYLE_CONVERSION_PROMPT.format(description=description)
