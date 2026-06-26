from pydantic import BaseModel, Field
from typing import Optional


class RedeemCodeUseRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, description="兑换码")


class RedeemCodeUseResponse(BaseModel):
    amount: int
    redeemBalance: int


class RedeemCodeRecordItem(BaseModel):
    code: str
    batchId: Optional[str] = None
    tokenAmount: int
    remainingAmount: int
    status: int
    statusText: str
    redeemTime: Optional[str] = None
    tokenExpiredTime: Optional[str] = None
