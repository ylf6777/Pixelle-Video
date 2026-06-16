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
配置 Schema — Pydantic 模型定义

所有配置项的唯一数据源，包含默认值、类型校验和合法性约束。
每个 Pydantic Field 自带 description，可直接用于生成 JSON Schema 文档。

层级结构:
    PixelleVideoConfig
      ├── LLMConfig                  LLM 大语言模型配置
      ├── APIProvidersConfig         直连 API 供应商配置
      │     ├── APIProviderCommonConfig  通用设置（代理、调试）
      │     ├── APIKeyProviderConfig     密钥类供应商（×5）
      │     └── AccessSecretProviderConfig AK/SK 类供应商
      ├── ComfyUIConfig              ComfyUI/RunningHub 配置
      │     ├── TTSSubConfig           TTS 子配置
      │     ├── ImageSubConfig         图片子配置
      │     └── VideoSubConfig         视频子配置
      └── TemplateConfig             模板配置
"""

from typing import Optional
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """
    大语言模型配置

    用于 OpenAI SDK 兼容的 LLM 服务（通义千问、GPT-4o、DeepSeek 等）。

    Requires:
        - 无外部依赖。纯数据模型。
    """

    api_key: str = Field(default="", description="LLM API 密钥")
    base_url: str = Field(default="", description="LLM API 端点地址（兼容 OpenAI SDK 格式）")
    model: str = Field(default="", description="模型名称（如 qwen-max、gpt-4o、deepseek-chat）")


class APIProviderCommonConfig(BaseModel):
    """
    直连 API 供应商通用设置

    跨供应商共享的配置项。

    Requires:
        - 无外部依赖。
    """

    print_model_input: bool = Field(
        default=False,
        description="调试开关。开启后在终端打印发给模型的 prompt/文件名等参数"
    )
    local_proxy: str = Field(
        default="",
        description="本地 HTTP 代理地址。如 http://127.0.0.1:9090。空字符串表示不使用"
    )


class APIKeyProviderConfig(BaseModel):
    """
    基于 API Key 的供应商配置

    适用于 OpenAI、DashScope、DeepSeek、Gemini、ARK 等使用单一 API Key 的供应商。

    Requires:
        - 无外部依赖。
    """

    api_key: str = Field(default="", description="供应商 API 密钥")
    base_url: str = Field(default="", description="供应商 API 端点地址")
    use_proxy: bool = Field(
        default=False,
        description="是否通过 APIProviderCommonConfig.local_proxy 发送请求"
    )


class AccessSecretProviderConfig(BaseModel):
    """
    基于 AK/SK 的供应商配置

    适用于 Kling（可灵）等使用 Access Key + Secret Key 的供应商。

    Requires:
        - 无外部依赖。
    """

    base_url: str = Field(default="", description="供应商 API 端点地址")
    access_key: str = Field(default="", description="供应商 Access Key")
    secret_key: str = Field(default="", description="供应商 Secret Key")
    use_proxy: bool = Field(default=False, description="是否通过公共代理发送请求")


class APIProvidersConfig(BaseModel):
    """
    直连 API 供应商配置集合

    包含所有支持的供应商配置。每个供应商可独立启用/禁用（配置 API Key 即视为启用）。

    Requires:
        - 无外部依赖。
    """

    common: APIProviderCommonConfig = Field(default_factory=APIProviderCommonConfig)
    openai: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    dashscope: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    deepseek: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    gemini: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    ark: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    kling: AccessSecretProviderConfig = Field(default_factory=AccessSecretProviderConfig)


class TTSLocalConfig(BaseModel):
    """
    本地 TTS 配置（Edge-TTS）

    使用 Microsoft Edge 浏览器内置 TTS 引擎，无需 API Key。

    Requires:
        - edge-tts Python 包
    """

    voice: str = Field(
        default="zh-CN-YunjianNeural",
        description="Edge-TTS 音色 ID。中文默认：zh-CN-YunjianNeural"
    )
    speed: float = Field(
        default=1.2, ge=0.5, le=2.0,
        description="语速倍率。0.5=半速，1.0=正常，2.0=倍速"
    )


class TTSComfyUIConfig(BaseModel):
    """
    ComfyUI TTS 配置

    通过 ComfyUI 工作流调用 TTS（如 Index-TTS、Spark-TTS）。

    Requires:
        - ComfyUI 服务运行中
        - workflows/ 下存在 TTS 工作流 JSON
    """

    default_workflow: Optional[str] = Field(
        default=None,
        description="默认 TTS 工作流文件名。None 时需手动选择"
    )


class TTSSubConfig(BaseModel):
    """
    TTS 子配置（comfyui.tts 下）

    统一管理 local 和 comfyui 两种 TTS 推理模式。

    Requires:
        - 无外部依赖。纯配置聚合。
    """

    inference_mode: str = Field(
        default="local",
        description="TTS 推理模式。'local'=Edge-TTS, 'comfyui'=ComfyUI 工作流"
    )
    local: TTSLocalConfig = Field(default_factory=TTSLocalConfig)
    comfyui: TTSComfyUIConfig = Field(default_factory=TTSComfyUIConfig)

    @property
    def default_workflow(self) -> Optional[str]:
        """
        获取默认 TTS 工作流（向后兼容属性）

        Returns:
            Optional[str]: comfyui.default_workflow 的值。未配置则 None。

        Requires:
            - 无外部依赖。
        """
        return self.comfyui.default_workflow


class ImageSubConfig(BaseModel):
    """
    图片生成子配置（comfyui.image 下）

    Requires:
        - 无外部依赖。
    """

    default_workflow: Optional[str] = Field(
        default=None,
        description="默认图片生成工作流文件名。None 时需手动选择"
    )
    prompt_prefix: str = Field(
        default="",
        description="所有图片生成提示词的前缀。如 'Cute cartoon style, soft pastel colors'"
    )


class VideoSubConfig(BaseModel):
    """
    视频生成子配置（comfyui.video 下）

    Requires:
        - 无外部依赖。
    """

    default_workflow: Optional[str] = Field(
        default=None,
        description="默认视频生成工作流文件名。None 时需手动选择"
    )
    prompt_prefix: str = Field(
        default="",
        description="所有视频生成提示词的前缀"
    )


class ComfyUIConfig(BaseModel):
    """
    ComfyUI / RunningHub 总配置

    包含服务端连接信息和各子服务的默认工作流配置。

    Requires:
        - ComfyUI 服务（用于 selfhost 工作流）
        - RunningHub API 账号（用于 runninghub 工作流，可选）
    """

    comfyui_url: str = Field(
        default="http://127.0.0.1:8188",
        description="ComfyUI 服务地址"
    )
    comfyui_api_key: Optional[str] = Field(
        default=None,
        description="ComfyUI API Key。None 表示无鉴权"
    )
    runninghub_api_key: Optional[str] = Field(
        default=None,
        description="RunningHub API Key。None 表示不使用云端服务"
    )
    runninghub_concurrent_limit: int = Field(
        default=1, ge=1, le=10,
        description="RunningHub 并发执行上限。范围 1-10"
    )
    runninghub_instance_type: Optional[str] = Field(
        default=None,
        description="RunningHub 实例类型。'plus'=48GB 显存。None 使用默认"
    )
    tts: TTSSubConfig = Field(default_factory=TTSSubConfig)
    image: ImageSubConfig = Field(default_factory=ImageSubConfig)
    video: VideoSubConfig = Field(default_factory=VideoSubConfig)


class TemplateConfig(BaseModel):
    """
    模板配置

    Requires:
        - 无外部依赖。
    """

    default_template: str = Field(
        default="1080x1920/default.html",
        description="默认帧模板路径（含尺寸前缀）"
    )


class PixelleVideoConfig(BaseModel):
    """
    Pixelle-Video 根配置

    所有配置项的聚合根。提供配置校验和字典导出方法。

    Requires:
        - 无外部依赖。纯 Pydantic 模型聚合。
    """

    project_name: str = Field(default="Pixelle-Video", description="项目名称")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    api_providers: APIProvidersConfig = Field(default_factory=APIProvidersConfig)
    comfyui: ComfyUIConfig = Field(default_factory=ComfyUIConfig)
    template: TemplateConfig = Field(default_factory=TemplateConfig)

    def is_llm_configured(self) -> bool:
        """
        检查 LLM 是否已正确配置

        三个必填字段（api_key、base_url、model）均非空且非空白字符串
        才视为已配置。

        Returns:
            bool: LLM 三项必填字段均有效时返回 True。

        Requires:
            - 无外部依赖。纯内存校验。
        """
        return bool(
            self.llm.api_key and self.llm.api_key.strip() and
            self.llm.base_url and self.llm.base_url.strip() and
            self.llm.model and self.llm.model.strip()
        )

    def validate_required(self) -> bool:
        """
        验证必要配置项

        当前仅检查 LLM 配置（后续可扩展到其他必填项）。

        Returns:
            bool: 所有必要配置项均有效时返回 True。

        Requires:
            - 无外部依赖。
        """
        return self.is_llm_configured()

    def to_dict(self) -> dict:
        """
        将配置转换为字典（向后兼容）

        Returns:
            dict: 配置的扁平字典表示。

        Requires:
            - Pydantic model_dump() 方法。

        Side Effects:
            - 无。
        """
        return self.model_dump()
