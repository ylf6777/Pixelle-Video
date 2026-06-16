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
Prompt helper utilities

Simple utilities for building prompts with optional prefixes.
Used to compose image/video prompts by prepending style prefixes.
"""


def build_image_prompt(prompt: str, prefix: str = "") -> str:
    """
    构建带可选前缀的最终图像/视频提示词。

    将 style prefix 与用户原始 prompt 用逗号拼接。两者都会先做 strip 处理。

    Args:
        prompt: 用户的原始提示词
        prefix: 可选的风格前缀（如 "anime style"），为空时直接返回 prompt

    Returns:
        拼接后的最终提示词：
        - 有 prefix 且有 prompt → "{prefix}, {prompt}"
        - 仅有 prefix → "{prefix}"
        - 仅有 prompt → "{prompt}"

    Raises:
        无（纯拼接函数，不抛异常）

    Requires:
        无（纯函数）

    Side Effects:
        无

    Examples:
        >>> build_image_prompt("a cat", "")
        'a cat'

        >>> build_image_prompt("a cat", "anime style")
        'anime style, a cat'

        >>> build_image_prompt("a cat", "  anime style  ")
        'anime style, a cat'
    """
    prefix = prefix.strip() if prefix else ""
    prompt = prompt.strip() if prompt else ""

    if prefix and prompt:
        return f"{prefix}, {prompt}"
    elif prefix:
        return prefix
    else:
        return prompt
