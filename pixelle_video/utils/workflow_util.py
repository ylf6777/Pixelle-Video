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
Workflow Path Resolver

Standardized workflow path resolution for all ComfyUI services.
Convention: {source}/{service}.json

Examples:
    - Image analysis: selfhost/analyse_image.json, runninghub/analyse_image.json
    - Image generation: selfhost/image.json, runninghub/image.json
    - Video generation: selfhost/video.json, runninghub/video.json
    - TTS: selfhost/tts.json, runninghub/tts.json
"""

from typing import Literal

WorkflowSource = Literal['runninghub', 'selfhost']


def resolve_workflow_path(
    service_name: str,
    source: WorkflowSource = 'runninghub'
) -> str:
    """
    根据服务名和数据源解析工作流 JSON 文件路径。

    约定格式: workflows/{source}/{service_name}.json

    Args:
        service_name: 服务标识符（如 "analyse_image", "image", "video", "tts"）
        source: 工作流来源，'runninghub'（默认）或 'selfhost'

    Returns:
        相对路径字符串，格式为 "{source}/{service_name}.json"

    Raises:
        无（纯字符串拼接函数）

    Requires:
        无（纯函数）

    Side Effects:
        无

    Examples:
        >>> resolve_workflow_path("analyse_image", "runninghub")
        'runninghub/analyse_image.json'

        >>> resolve_workflow_path("analyse_image", "selfhost")
        'selfhost/analyse_image.json'

        >>> resolve_workflow_path("image")  # 默认 runninghub
        'runninghub/image.json'
    """
    return f"{source}/{service_name}.json"


def get_default_source() -> WorkflowSource:
    """
    获取默认工作流来源。

    Returns:
        'runninghub' - 云优先策略，适合新手使用

    Raises:
        无

    Requires:
        无（纯函数）

    Side Effects:
        无
    """
    return 'runninghub'
