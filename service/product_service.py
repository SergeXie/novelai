from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.vo.product_schema_vo import MembershipItem, TokenPackageItem, ProductListResponse
from dao.product_dao import ProductDAO


class ProductService:
    """
    产品服务层

    职责：
    - 聚合数据
    - 做结构转换
    - 不直接操作数据库（通过DAO）
    """

    @staticmethod
    async def get_product_list(db: AsyncSession) -> ProductListResponse:
        """
        获取产品列表（会员 + Token包）

        流程：
        1. 查询会员配置
        2. 查询Token包配置
        3. 转换为前端结构
        """

        memberships = await ProductDAO.get_memberships(db)
        packages = await ProductDAO.get_token_packages(db)

        # ===== 构建会员列表 =====
        membership_list = []
        for m in memberships:
            membership_list.append(
                MembershipItem(
                    level_code=m.level_code,
                    level_name=m.level_name,
                    description=m.description,
                    price=float(m.price),  # Decimal -> float
                    duration_days=m.duration_days,
                    monthly_token_allowance=m.monthly_token_allowance,
                    unlocked_models=m.unlocked_models,
                    extra_privileges=m.extra_privileges
                )
            )

        # ===== 构建Token包列表 =====
        package_list = []
        for p in packages:
            package_list.append(
                TokenPackageItem(
                    package_code=p.package_code,
                    package_name=p.package_name,
                    description=p.description,
                    token_amount=p.token_amount,
                    price=float(p.price),
                    expire_days=p.expire_days
                )
            )

        return ProductListResponse(
            memberships=membership_list,
            token_packages=package_list
        )