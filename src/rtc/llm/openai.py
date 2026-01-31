"""OpenAI LLM client implementation."""

import json
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from rtc.config import get_settings
from rtc.llm.base import BaseLLMClient

T = TypeVar("T", bound=BaseModel)


class OpenAILLMClient(BaseLLMClient):
    """OpenAI LLM client using langchain-openai."""

    # o-시리즈 모델은 temperature를 지원하지 않음
    REASONING_MODELS = ("o1", "o3", "o4", "o1-", "o3-", "o4-")

    def __init__(self, model: str | None = None):
        """Initialize OpenAI client.

        Args:
            model: Model name to use. Defaults to settings.
        """
        settings = get_settings()
        self.model = model or settings.llm_model_openai
        self._client = ChatOpenAI(
            model=self.model,
            api_key=settings.openai_api_key,
            max_tokens=4096,
        )

    def _is_reasoning_model(self) -> bool:
        """추론 모델인지 확인 (o1, o3, o4 시리즈)."""
        return any(self.model.startswith(prefix) for prefix in self.REASONING_MODELS)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a text response using OpenAI."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # 추론 모델은 temperature 지원 안 함
        kwargs = {
            "model": self.model,
            "api_key": get_settings().openai_api_key,
            "max_tokens": max_tokens,
        }
        if not self._is_reasoning_model():
            kwargs["temperature"] = temperature

        client = ChatOpenAI(**kwargs)

        response = await client.ainvoke(messages)
        return response.content

    async def generate_structured(
        self,
        prompt: str,
        output_schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> T:
        """Generate a structured response using OpenAI's JSON mode."""
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)

        structured_system = f"""You are a helpful assistant that outputs valid JSON matching the provided schema.

Output Schema:
```json
{schema_json}
```

IMPORTANT: Your response must be ONLY valid JSON matching this schema. No markdown, no explanation, just the JSON object."""

        if system_prompt:
            structured_system = f"{system_prompt}\n\n{structured_system}"

        messages = [
            SystemMessage(content=structured_system),
            HumanMessage(content=prompt),
        ]

        # 추론 모델은 temperature 지원 안 함
        kwargs = {
            "model": self.model,
            "api_key": get_settings().openai_api_key,
            "max_tokens": max_tokens,
            "model_kwargs": {"response_format": {"type": "json_object"}},
        }
        if not self._is_reasoning_model():
            kwargs["temperature"] = temperature

        client = ChatOpenAI(**kwargs)

        response = await client.ainvoke(messages)
        response_text = response.content

        # Parse JSON
        json_str = self._extract_json_from_response(response_text)
        data = json.loads(json_str)

        # Handle case where LLM returns schema-like structure with values in "properties"
        if "properties" in data and isinstance(data["properties"], dict):
            # Extract values from properties if they look like actual values (not schema definitions)
            props = data["properties"]
            first_value = next(iter(props.values()), None)
            if not isinstance(first_value, dict) or "type" not in first_value:
                # Values are directly in properties, not schema definitions
                data = props

        return output_schema.model_validate(data)

    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.model
