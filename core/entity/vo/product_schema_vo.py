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