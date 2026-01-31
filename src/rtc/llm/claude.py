"""Claude LLM client implementation."""

import json
from typing import TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from rtc.config import get_settings
from rtc.llm.base import BaseLLMClient

T = TypeVar("T", bound=BaseModel)


class ClaudeLLMClient(BaseLLMClient):
    """Claude LLM client using langchain-anthropic."""

    def __init__(self, model: str | None = None):
        """Initialize Claude client.

        Args:
            model: Model name to use. Defaults to settings.
        """
        settings = get_settings()
        self.model = model or settings.llm_model_claude
        self._client = ChatAnthropic(
            model=self.model,
            api_key=settings.anthropic_api_key,
            max_tokens=4096,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a text response using Claude."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # Create a new client with the specified parameters
        client = ChatAnthropic(
            model=self.model,
            api_key=get_settings().anthropic_api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )

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
        """Generate a structured response matching a Pydantic schema."""
        # Build schema description
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

        client = ChatAnthropic(
            model=self.model,
            api_key=get_settings().anthropic_api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        response = await client.ainvoke(messages)
        response_text = response.content

        # Extract and parse JSON
        json_str = self._extract_json_from_response(response_text)
        data = json.loads(json_str)

        return output_schema.model_validate(data)

    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.model
