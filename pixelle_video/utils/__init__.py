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
ylf_Video Utilities

Utility functions and helpers for content generation, LLM interaction,
file/path management, TTS, templates, and workflow resolution.

Submodules:
    - content_generators: Async content generation via LLM (titles, narrations, prompts)
    - llm_util: LLM connection testing and model discovery
    - os_util: File system, path, task directory, and resource management
    - prompt_helper: Prompt construction helpers
    - template_util: Template size parsing, listing, filtering, and path resolution
    - tts_util: Edge TTS (text-to-speech) with retry and rate limiting
    - workflow_util: Workflow JSON path resolution (runninghub/selfhost)

Requires:
    - Python 3.10+

Side Effects:
    - None (pure module, no imports trigger side effects)
"""