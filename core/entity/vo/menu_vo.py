from pydantic import BaseModel, Field


class MenuCategoryItem(BaseModel):
    name: str = Field(..., description="分类显示名称")
    tool_key: str = Field(..., description="工具分类唯一标识")
