from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class MembershipItem(BaseModel):
    """
    单个会员产品返回结构
    """
    level_code: str
    level_name: str
    description: str
    price: float
    duration_days: int
    monthly_token_allowance: int

    # 解锁模型（如 GPT-4）
    unlocked_models: Optional[List[str]]

    # 扩展权益（并发数/优先级等）
    extra_privileges: Optional[Dict[str, Any]]


class TokenPackageItem(BaseModel):
    """
    单个Token包返回结构
    """
    package_code: str
    package_name: str
    description: str
    token_amount: int
    price: float
    expire_days: int


class ProductListResponse(BaseModel):
    """
    产品列表统一返回结构
    """
    memberships: List[MembershipItem]
    token_packages: List[TokenPackageItem]