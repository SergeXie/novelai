from ai.adapters.base_adapter import BaseAIAdapter
import asyncio

from openai import OpenAI
from loguru import logger

from common.config.config import settings


class DoubaoPlusAdapter(BaseAIAdapter):
	def __init__(self):
		self.client = OpenAI(
			api_key=settings.doubaoplus.api_key,
			base_url=settings.doubaoplus.base_url
		)
		self.model_name = settings.doubaoplus.model_name
		self.max_tokens = settings.doubaoplus.max_tokens
		self.temperature = settings.doubaoplus.temperature
		self.multiplier = settings.doubaoplus.multiplier

	async def generate_text(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int = None) -> str:
		try:
			response = await asyncio.to_thread(
				self.client.chat.completions.create,
				model=self.model_name,
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt}
				],
				temperature=temperature or self.temperature,
				max_tokens=max_tokens or self.max_tokens
			)
			return response.choices[0].message.content
		except Exception as e:
			info = f"豆包Plus 响应异常: {str(e)}"
			logger.error(info)
			raise Exception(info)

