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
Prompts package

Centralized prompt management for all LLM interactions.
"""

# Narration prompts
from pixelle_video.prompts.topic_narration import build_topic_narration_prompt
from pixelle_video.prompts.content_narration import build_content_narration_prompt
from pixelle_video.prompts.title_generation import build_title_generation_prompt

# Image prompts
from pixelle_video.prompts.image_generation import build_image_prompt_prompt
from pixelle_video.prompts.style_conversion import build_style_conversion_prompt

# Video prompts
from pixelle_video.prompts.video_generation import build_video_prompt_prompt

# Scene breakdown
from pixelle_video.prompts.scene_breakdown import build_scene_breakdown_prompt


__all__ = [
    # Narration builders
    "build_topic_narration_prompt",
    "build_content_narration_prompt",
    "build_title_generation_prompt",

    # Image builders
    "build_image_prompt_prompt",
    "build_style_conversion_prompt",

    # Video builders
    "build_video_prompt_prompt",

    # Scene breakdown
    "build_scene_breakdown_prompt",
]
