from pydantic import BaseModel, Field


class MenuCategoryItem(BaseModel):
    id: int = Field(...)
    name: str = Field(..., description="分类显示名称")
    key: str = Field(..., description="工具分类唯一标识")
    interaction_type: int = Field(..., description="交互类型(1: 续写、2 扩写、3 润色、4 去AI味、5审稿, 6 写作)")
