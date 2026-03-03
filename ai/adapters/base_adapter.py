from abc import ABC, abstractmethod

class BaseAIAdapter(ABC):
    @abstractmethod
    async def generate_text(self, system_prompt: str, user_prompt: str, temperature:float, max_tokens: int = None) -> str:
        """
        所有适配器必须实现的文本生成方法
        """
        pass