from datetime import datetime
from typing import Union, Optional

from pydantic import BaseModel, Field, ConfigDict

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




