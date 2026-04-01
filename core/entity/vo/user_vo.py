from datetime import datetime
from typing import Union, Optional, List, Dict

from pydantic import BaseModel, Field, ConfigDict, field_serializer

from core.entity.do.users_do import OnlineStatus


class CurrentUserModel(BaseModel):

    user: Optional[Union[str, None]] = Field(description='用户信息')


class TokenData(BaseModel):
    """
    token解析结果
    """

    uuid: Union[str, None] = Field(default=None, description='用户ID')


class UserInfoModel(BaseModel):

    """
    用户信息模型
    """
    model_config = ConfigDict(from_attributes=True)

    onlineStatus: Optional[str] = Field(default=OnlineStatus.ONLINE.value, description='在线状态')
    lastLoginTime: Optional[datetime] = Field(default=datetime.now(), description='在线状态')


class AccountInfoResponse(BaseModel):
    """
    我的资产信息
    """

    level: str
    level_name: str
    expire_at: Optional[datetime] = None
    monthly_balance: Optional[int] = 0
    permanent_balance: Optional[int] = 0
    total_balance: Optional[int] = 0
    unlocked_models: Optional[List[str]] = []
    extra_privileges: Optional[Dict] = {}


    @field_serializer('expire_at')
    def serialize_paid_at(self, expire_at: Optional[datetime], _info):
        if expire_at is None:
            return None
        # 这里定义你想要的格式，例如：2026-03-31 11:05:22
        return expire_at.strftime('%Y-%m-%d %H:%M:%S')

