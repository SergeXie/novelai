from common.config.config import settings

from ai.adapters.image_base_adapter import OpenAIBaseImageAdapter


class DoubaoImageAdapter(OpenAIBaseImageAdapter):
    def __init__(self):
        super().__init__(
            name="豆包文生图",
            api_key=settings.doubao.api_key,
            base_url=settings.doubao.base_url,
            model_name="doubao-seedream-4-0-250828",
        )