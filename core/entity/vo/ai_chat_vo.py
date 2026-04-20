from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class ChatGroupVO(BaseModel):
    """分组信息展示对象"""
    gid: str = Field(..., description="分组唯一标识")
    name: str = Field(..., description="分组名称")
    weight: int = Field(0, description="权重")
    is_pinned: bool = Field(False, description="是否置顶")

    # 添加时间字段
    # 使用 Optional 是为了防止数据库中存在旧数据导致时间字段为 None 时报错
    created_at: datetime = Field(None, description="创建时间")
    updated_at: datetime = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('created_at', 'updated_at')
    def serialize_dt(self, dt: datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')