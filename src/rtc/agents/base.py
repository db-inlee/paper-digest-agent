"""에이전트 기본 클래스."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """에이전트 기본 추상 클래스.

    모든 에이전트는 이 클래스를 상속받아 구현합니다.
    """

    name: str = "base"
    uses_llm: bool = False

    @abstractmethod
    async def run(self, input: InputT) -> OutputT:
        """에이전트 실행.

        Args:
            input: 에이전트 입력

        Returns:
            에이전트 출력
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} uses_llm={self.uses_llm}>"
