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
视频生成流水线包

层次结构:
    BasePipeline (abstract)
      └── LinearVideoPipeline (模板方法, 8 步生命周期)
            ├── StandardPipeline   — 标准视频生成（主题→文案→图片→视频）
            ├── CustomPipeline     — 自定义模板（固定脚本+参数）
            └── AssetBasedPipeline — 基于用户素材（图片/视频→分析→脚本→合成）

使用方式:
    result = await pipeline_instance(text="...", progress_callback=fn, **params)
"""

from pixelle_video.pipelines.base import BasePipeline
from pixelle_video.pipelines.linear import LinearVideoPipeline, PipelineContext
from pixelle_video.pipelines.standard import StandardPipeline
from pixelle_video.pipelines.custom import CustomPipeline
from pixelle_video.pipelines.asset_based import AssetBasedPipeline

__all__ = [
    "BasePipeline",
    "LinearVideoPipeline",
    "PipelineContext",
    "StandardPipeline",
    "CustomPipeline",
    "AssetBasedPipeline",
]
