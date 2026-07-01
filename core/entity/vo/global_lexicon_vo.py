from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_serializer


class GlobalLexiconCreateReq(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="词条名称")
    lexiconType: int = Field(
        ...,
        ge=1,
        le=4,
        validation_alias=AliasChoices("lexiconType", "lexicon_type"),
        description="1角色, 2世界观, 3功法, 4道具",
    )
    content: str | None = Field(None, description="详细设定描述")
    data: dict[str, Any] | None = Field(None, description="别名、扩展属性")
    shareLevel: int = Field(
        0,
        ge=0,
        le=2,
        validation_alias=AliasChoices("shareLevel", "share_level"),
        description="共享等级: 0私有, 1系列可见, 2全平台公开",
    )


class GlobalLexiconCreateResp(BaseModel):
    id: int
    userId: int
    title: str
    lexiconType: int
    content: str | None = None
    data: dict[str, Any] | None = None
    shareLevel: int
    createTime: datetime | None = None

    @field_serializer("createTime")
    def serialize_datetime(self, value: datetime | None):
        if value:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return None


class GlobalLexiconEditReq(BaseModel):
    id: int = Field(..., ge=1, description="词条ID")
    title: str | None = Field(None, min_length=1, max_length=100, description="词条名称")
    lexiconType: int | None = Field(
        None,
        ge=1,
        le=4,
        validation_alias=AliasChoices("lexiconType", "lexicon_type"),
        description="1角色, 2世界观, 3功法, 4道具",
    )
    content: str | None = Field(None, description="详细设定描述")
    data: dict[str, Any] | None = Field(None, description="别名、扩展属性")
    shareLevel: int | None = Field(
        None,
        ge=0,
        le=2,
        validation_alias=AliasChoices("shareLevel", "share_level"),
        description="共享等级: 0私有, 1系列可见, 2全平台公开",
    )


class GlobalLexiconDeleteReq(BaseModel):
    id: int = Field(..., ge=1, description="词条ID")


class GlobalLexiconListItem(BaseModel):
    id: int
    userId: int
    title: str
    lexiconType: int
    content: str | None = None
    data: dict[str, Any] | None = None
    shareLevel: int
    createTime: datetime | None = None

    @field_serializer("createTime")
    def serialize_datetime(self, value: datetime | None):
        if value:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return None
