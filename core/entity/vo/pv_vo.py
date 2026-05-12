# schemas/pv_schema.py

from pydantic import BaseModel
from typing import Optional


class PVCreateRequest(BaseModel):
    """
    创建PV请求参数
    """

    # 访客ID
    visitor_id: Optional[str] = None

    # 页面路径
    page: str

    # 浏览器名称
    browser: Optional[str] = None

    # 设备类型
    device: Optional[str] = None

    # 来源页面
    referer: Optional[str] = None

    # 完整UA
    user_agent: Optional[str] = None

    # 子分类/维度
    sub: Optional[str] = None