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
LLM 大语言模型服务 — OpenAI SDK 直连实现

支持所有 OpenAI SDK 兼容供应商：OpenAI、通义千问、Claude、DeepSeek、
Kimi、Ollama 等。提供结构化输出（Pydantic 模型反序列化）支持。
"""

import json
import re
from typing import Optional, Type, TypeVar, Union

from openai import AsyncOpenAI
from pydantic import BaseModel
from loguru import logger


T = TypeVar("T", bound=BaseModel)


class LLMService:
    """
    LLM 大语言模型服务

    基于 OpenAI SDK 的直接实现，支持文本生成和结构化输出。
    每次调用从 config_manager 动态读取配置，支持热重载。

    支持的供应商:
        - OpenAI (gpt-4o, gpt-4o-mini, gpt-3.5-turbo)
        - 阿里通义千问 (qwen-max, qwen-plus, qwen-turbo)
        - Anthropic Claude (claude-sonnet-4-5, claude-opus-4, claude-haiku-4)
        - DeepSeek (deepseek-chat)
        - Moonshot Kimi (moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k)
        - Ollama (本地免费): llama3.2, qwen2.5, mistral, codellama
        - 任意 OpenAI 兼容 API

    Requires:
        - openai (AsyncOpenAI): OpenAI SDK 异步客户端。
        - pixelle_video.config.config_manager: 全局配置单例，用于动态读取 LLM 配置。
    """

    def __init__(self, config: dict):
        """
        初始化 LLM 服务

        不再缓存配置——每次调用从 config_manager 动态读取以支持热重载。

        Args:
            config (dict): 完整应用配置字典（保留参数以兼容旧代码，实际不使用）。

        Side Effects:
            - 无。仅设置初始状态。
        """
        self._client: Optional[AsyncOpenAI] = None

    def _get_config_value(self, key: str, default=None):
        """
        从 config_manager 动态读取配置值（支持热重载）

        Args:
            key (str): llm 配置键名。如 "api_key", "base_url", "model"。
            default: 键不存在时的默认返回值。

        Returns:
            配置值。类型取决于具体配置项。

        Requires:
            - pixelle_video.config.config_manager: 全局配置单例。通过内联 import 访问。
        """
        from pixelle_video.config import config_manager
        return getattr(config_manager.config.llm, key, default)

    def _create_client(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> AsyncOpenAI:
        """
        创建 AsyncOpenAI 客户端实例

        优先级：参数 > 配置 > 默认值（Ollama 不需真实 API Key 时用 "dummy-key"）。

        Args:
            api_key (Optional[str]): API 密钥。None 时从配置读取。
            base_url (Optional[str]): API 端点地址。None 时从配置读取。

        Returns:
            AsyncOpenAI: 配置好的异步客户端实例。

        Requires:
            - openai.AsyncOpenAI: OpenAI SDK。
            - self._get_config_value: 配置读取。
        """
        final_api_key = (
            api_key
            or self._get_config_value("api_key")
            or "dummy-key"
        )

        final_base_url = (
            base_url
            or self._get_config_value("base_url")
        )

        client_kwargs = {"api_key": final_api_key}
        if final_base_url:
            client_kwargs["base_url"] = final_base_url

        return AsyncOpenAI(**client_kwargs)

    async def __call__(
        self,
        prompt: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_type: Optional[Type[T]] = None,
        **kwargs
    ) -> Union[str, T]:
        """
        调用 LLM 生成文本或结构化数据

        优先级链：参数 > 配置 > 默认值。

        Args:
            prompt (str): 提示词文本。
            api_key (Optional[str]): 覆盖配置中的 API 密钥。
            base_url (Optional[str]): 覆盖配置中的 API 端点。
            model (Optional[str]): 覆盖配置中的模型名称。
            temperature (float): 采样温度（0.0=确定性，2.0=高随机性）。默认 0.7。
            max_tokens (int): 最大生成 token 数。默认 2000。
            response_type (Optional[Type[T]]): Pydantic 模型类。提供时启用结构化输出模式，
                返回解析后的模型实例而非字符串。
            **kwargs: 传递给 OpenAI API 的额外参数。

        Returns:
            Union[str, T]: response_type 为 None 时返回字符串，否则返回 Pydantic 模型实例。

        Raises:
            Exception: LLM API 调用失败时向上抛出（包含错误上下文）。

        Requires:
            - self._create_client: 客户端创建。
            - self._call_with_structured_output: 结构化输出（response_type 非 None 时）。

        Side Effects:
            - 网络请求：调用 LLM API。
            - 写入日志（debug/error）。
        """
        client = self._create_client(api_key=api_key, base_url=base_url)

        final_model = (
            model
            or self._get_config_value("model")
            or "gpt-3.5-turbo"
        )

        logger.debug(
            f"LLM call: model={final_model}, base_url={client.base_url}, "
            f"response_type={response_type}"
        )

        try:
            if response_type is not None:
                return await self._call_with_structured_output(
                    client=client, model=final_model, prompt=prompt,
                    response_type=response_type,
                    temperature=temperature, max_tokens=max_tokens, **kwargs
                )
            else:
                response = await client.chat.completions.create(
                    model=final_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )

                result = response.choices[0].message.content
                logger.debug(f"LLM response length: {len(result)} chars")
                if not result or not result.strip():
                    logger.warning(
                        f"LLM returned empty text content "
                        f"(model={final_model}, base_url={client.base_url})"
                    )
                return result

        except Exception as e:
            logger.error(
                f"LLM call error (model={final_model}, base_url={client.base_url}): {e}"
            )
            raise

    async def _call_with_structured_output(
        self,
        client: AsyncOpenAI,
        model: str,
        prompt: str,
        response_type: Type[T],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> T:
        """
        结构化输出模式：将 JSON Schema 追加到 prompt 中引导 LLM 返回 JSON

        使用 prompt-engineering 方式实现跨供应商兼容（不使用 OpenAI 的
        response_format，因为 Qwen/DeepSeek 等不支持）。

        Args:
            client (AsyncOpenAI): 已配置的客户端。
            model (str): 模型名称。
            prompt (str): 原始提示词。
            response_type (Type[T]): 目标 Pydantic 模型类。
            temperature (float): 采样温度。
            max_tokens (int): 最大生成 token 数。
            **kwargs: 传递给 API 的额外参数。

        Returns:
            T: 解析后的 Pydantic 模型实例。

        Raises:
            ValueError: 响应内容无法解析为目标模型时抛出。

        Requires:
            - self._get_json_schema_instruction: JSON Schema 指令生成。
            - self._parse_response_as_model: 响应解析。

        Side Effects:
            - 网络请求：调用 LLM API。
            - 写入日志（debug）。
        """
        json_schema_instruction = self._get_json_schema_instruction(response_type)
        enhanced_prompt = f"{prompt}\n\n{json_schema_instruction}"

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": enhanced_prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        content = response.choices[0].message.content
        logger.debug(f"Structured output response length: {len(content)} chars")

        return self._parse_response_as_model(content, response_type)

    def _get_json_schema_instruction(self, response_type: Type[T]) -> str:
        """
        生成 JSON Schema 指令，追加到 prompt 末尾

        Args:
            response_type (Type[T]): Pydantic 模型类。

        Returns:
            str: 格式化的 JSON Schema 指令文本，告知 LLM 输出格式要求。

        Requires:
            - response_type.model_json_schema(): Pydantic 的 Schema 导出方法。

        Side Effects:
            - 无。纯文本生成。
        """
        try:
            schema = response_type.model_json_schema()
            schema_str = json.dumps(schema, indent=2, ensure_ascii=False)

            return (
                "## IMPORTANT: JSON Output Format Required\n"
                "You MUST respond with ONLY a valid JSON object (no markdown, no extra text).\n"
                "The JSON must strictly follow this schema:\n\n"
                f"```json\n{schema_str}\n```\n\n"
                "Output ONLY the JSON object, nothing else."
            )
        except Exception as e:
            logger.warning(f"Failed to generate JSON schema: {e}")
            return (
                "## IMPORTANT: JSON Output Format Required\n"
                "You MUST respond with ONLY a valid JSON object "
                "(no markdown, no extra text)."
            )

    def _parse_response_as_model(self, content: str, response_type: Type[T]) -> T:
        """
        从 LLM 响应文本中解析 Pydantic 模型

        尝试三级回退策略:
        1. 直接 JSON 解析
        2. 提取 Markdown 代码块中的 JSON
        3. 提取大括号之间的 JSON

        Args:
            content (str): LLM 原始响应文本。
            response_type (Type[T]): 目标 Pydantic 模型类。

        Returns:
            T: 解析校验后的 Pydantic 模型实例。

        Raises:
            ValueError: 三级回退均失败时抛出，包含响应前 200 字符用于调试。

        Requires:
            - json.loads: 标准库 JSON 解析。
            - response_type.model_validate: Pydantic 校验方法。

        Side Effects:
            - 无。纯文本解析，无 I/O。
        """
        # Level 1: direct JSON parse
        try:
            data = json.loads(content)
            return response_type.model_validate(data)
        except json.JSONDecodeError:
            pass

        # Level 2: extract from markdown code block
        json_pattern = r'```(?:json)?\s*([\s\S]+?)\s*```'
        match = re.search(json_pattern, content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return response_type.model_validate(data)
            except json.JSONDecodeError:
                pass

        # Level 3: find any JSON object by braces
        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                json_str = content[brace_start:brace_end + 1]
                data = json.loads(json_str)
                return response_type.model_validate(data)
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"Failed to parse LLM response as {response_type.__name__}: "
            f"{content[:200]}..."
        )

    @property
    def active(self) -> str:
        """
        获取当前活跃的模型名称

        Returns:
            str: 配置中的模型名称。未配置则返回 "gpt-3.5-turbo"。

        Requires:
            - self._get_config_value: 从 config_manager 读取。
        """
        return self._get_config_value("model", "gpt-3.5-turbo")

    def __repr__(self) -> str:
        """字符串表示：包含当前模型和端点信息"""
        model = self.active
        base_url = self._get_config_value("base_url", "default")
        return f"<LLMService model={model!r} base_url={base_url!r}>"
