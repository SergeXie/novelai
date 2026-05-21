from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.vo.pv_vo import PVCreateRequest
from dao.pv_dao import PVDao


class PVService:
    @staticmethod
    def get_real_ip(request: Request) -> str:
        """
        Prefer proxy headers set by Nginx, then fall back to the direct client IP.
        X-Forwarded-For may contain multiple IPs; the first one is the original client.
        """
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            return x_real_ip.strip()

        return request.client.host if request.client else ""

    @staticmethod
    async def create_pv(
        db: AsyncSession,
        request: Request,
        data: PVCreateRequest,
    ):
        """Create PV record."""
        pv_data = data.dict(exclude_unset=True)
        pv_data.update({
            "ip": PVService.get_real_ip(request),
        })

        return await PVDao.create(
            db=db,
            data=pv_data,
        )
