from datetime import datetime
from typing import Union, Optional, List, Dict
from pydantic import ConfigDict, field_serializer
from pydantic import BaseModel, Field
from core.entity.do.users_do import OnlineStatus

class UpdateNicknameRequest(BaseModel):
    """
    修改昵称请求
    """

    nickname: str = Field(..., min_length=1, max_length=20, description="用户昵称")


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


class AssetUsageItem(BaseModel):
    key: str
    name: str
    total: int = 0
    available: int = 0
    used: int = 0
    usedPercent: int = 0


class UsageOverview(BaseModel):
    availableAmount: int = 0
    totalAmount: int = 0
    usedAmount: int = 0
    usedPercent: int = 0
    status: str = "normal"
    totalItems: List[AssetUsageItem] = Field(default_factory=list)


class AccountInfoResponse(BaseModel):
    """
    我的资产信息
    """

    level: str
    level_name: str
    expire_at: Optional[datetime] = None
    availableAmount: int = 0
    totalAmount: int = 0
    usedAmount: int = 0
    usedPercent: int = 0
    status: str = "normal"
    totalItems: List[AssetUsageItem] = Field(default_factory=list)

    @field_serializer('expire_at')
    def serialize_paid_at(self, expire_at: Optional[datetime], _info):
        if expire_at is None:
            return None
        # 这里定义你想要的格式，例如：2026-03-31 11:05:22
        return expire_at.strftime('%Y-%m-%d %H:%M:%S')


class BonusGrantItem(BaseModel):
    id: int
    orderNo: str
    cycleNo: int
    periodNo: int
    amount: int
    date: str
    scheduledAt: str
    issuedAt: Optional[str] = None
    status: str
    rawStatus: str
    canClaim: bool = False


class BonusGrantListResponse(BaseModel):
    availableAmount: int = 0
    weeklyAmount: int = 0
    list: List[BonusGrantItem] = Field(default_factory=list)

