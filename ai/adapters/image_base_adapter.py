from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI


class BaseImageAdapter(ABC):
    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        size: str = "2K",
        n: int = 1,
        watermark: bool = False,
        response_format: str = "url",
        extra_body: Optional[dict] = None,
    ) -> str:
        """所有图片适配器必须实现的文生图方法"""
        pass


class OpenAIBaseImageAdapter(BaseImageAdapter):
    def __init__(self, name: str, api_key: str, base_url: str, model_name: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model_name = model_name
        self.name = name

    async def generate_image(
        self,
        prompt: str,
        size: str = "4K",
        n: int = 1,
        watermark: bool = False,
        response_format: str = "url",
        extra_body: Optional[dict] = None,
    ) -> str:
        try:
            response = await self.client.images.generate(
                model=self.model_name,
                prompt=prompt,
                size=size,
                n=n,
                response_format=response_format,
                extra_body={
                    "watermark": watermark,
                    **(extra_body or {}),
                },
            )

            image_data = getattr(response, "data", []) or []
            if not image_data or not getattr(image_data[0], "url", None):
                raise ValueError("文生图未返回可用图片地址")

            return image_data[0].url
        except Exception as exc:
            info = f"{self.name}[{self.model_name}] 文生图异常: {str(exc)}"
            logger.error(info)
            raise Exception(info)