from pydantic import BaseModel, Field

from ai.adapters.enums import AIProvider


class ImageGenerateRequest(BaseModel):
    """文生图请求参数"""

    prompt: str = Field(..., description="图片生成提示词")
    level: int = Field(default=AIProvider.DOUBAOIMAGE.value, description="模型等级/供应商")
    size: str = Field(default="2K", description="图片尺寸")
    n: int = Field(default=1, ge=1, le=10, description="生成图片张数")
    watermark: bool = Field(default=False, description="是否添加水印")
