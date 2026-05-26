from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from loguru import logger
from common.config.get_db import get_db
from core.entity.do.user_account_do import AccountLog
from core.enums.constants import BizType, ChargeType, AssetType
from dao.membership_token_grant_plan_dao import MembershipTokenGrantPlanDAO
from dao.user_account_dao import UserAccountDAO
from service.account_service import AccountService
from service.order_service import OrderService

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=1, minute=0)
async def membership_expire_job():
    """
    会员过期处理任务（最终稳定版）

    功能：
    - 会员降级 FREE
    - 清空月度额度
    - 同步 total_amount
    - 写流水（幂等 + 正确金额）
    """
    logger.info("[定时任务] 开始执行会员过期检查")

    async for db in get_db():
        now = datetime.utcnow()

        # 查询需要处理的用户
        users = await UserAccountDAO.get_expired_memberships(db)

        for account in users:

            # =========================
            # 1. 并发保护（防止刚续费）
            # =========================
            expire_at = AccountService._as_utc_naive(account.expire_at) if account.expire_at else None
            if expire_at and expire_at > now:
                continue

            # =========================
            # 2. 幂等保护（防重复执行）
            # =========================
            if not account.level_code or account.level_code == "free":
                continue

            old_level = account.level_code

            # =========================
            # 3. 记录旧值（必须在修改前）
            # =========================
            old_monthly = account.monthly_balance or 0
            old_monthly_total = account.monthly_total_amount or 0
            old_bonus = account.bonus_balance or 0

            # =========================
            # 4. 降级会员
            # =========================
            account.level_code = "free"

            # =========================
            # 5. 清空月度额度
            # =========================
            account.monthly_balance = 0
            account.monthly_total_amount = 0
            account.bonus_balance = 0
            account.bonus_total_amount = 0

            # =========================
            # 6. 同步总额度（防负数）
            # =========================
            account.total_amount = max(
                (account.total_amount or 0) - old_monthly_total,
                0
            )

            # =========================
            # 7. 更新时间
            # =========================
            account.last_reset_at = now

            logger.info(
                f"[会员过期] user={account.user_id}, {old_level} → free, "
                f"清除月度额度={old_monthly}"
            )

            # =========================
            # 8. 写流水（仅在有额度时）
            # =========================
            if old_monthly > 0:
                log = AccountLog(
                    user_id=account.user_id,

                    # 唯一业务ID（避免重复）
                    biz_id=f"expire_{account.user_id}_{int(now.timestamp())}",

                    biz_type=BizType.SYSTEM.value,
                    change_type=ChargeType.EXPIRE.value,
                    asset_type=AssetType.MONTHLY.value,

                    # 扣减必须是负数
                    amount=-old_monthly,

                    # 写变更后的余额（此时为0）
                    balance_after=account.monthly_balance,

                    extra={
                        "old_level": old_level,
                        "new_level": "free",
                        "reason": "membership_expired"
                    }
                )

                db.add(log)

            if old_bonus > 0:
                log = AccountLog(
                    user_id=account.user_id,
                    biz_id=f"expire_bonus_{account.user_id}_{int(now.timestamp())}",
                    biz_type=BizType.SYSTEM.value,
                    change_type=ChargeType.EXPIRE.value,
                    asset_type=AssetType.BONUS.value,
                    amount=-old_bonus,
                    balance_after=account.bonus_balance,
                    extra={
                        "old_level": old_level,
                        "new_level": "free",
                        "reason": "membership_bonus_expired"
                    }
                )

                db.add(log)

        # =========================
        # 9. 提交事务
        # =========================
        await db.commit()

    logger.info("[定时任务] 会员过期检查完成")


@scheduler.scheduled_job("cron", hour=1, minute=10)
async def membership_token_grant_job():
    """
    会员月度 Token 分期发放任务。
    """
    logger.info("[定时任务] 开始执行会员Token分期发放")

    async for db in get_db():
        now = datetime.utcnow()
        # BASE/RESET 是系统计划，可以自动执行；BONUS 必须等用户登录/上线后领取。
        plans = await MembershipTokenGrantPlanDAO.get_due_system_plans(db, now)

        for plan in plans:
            account = await UserAccountDAO.get_active_account(db=db, user_id=plan.user_id)
            if not account:
                plan.status = "FAILED"
                plan.issued_at = now
                plan.extra = {
                    **(plan.extra or {}),
                    "failed_reason": "account_not_found",
                }
                logger.error(f"[会员Token发放] 账户不存在 user_id={plan.user_id}, plan_id={plan.id}")
                continue

            try:
                await AccountService.issue_membership_token_plan(db, account, plan, now)
            except Exception as e:
                plan.status = "FAILED"
                plan.issued_at = now
                plan.extra = {
                    **(plan.extra or {}),
                    "failed_reason": str(e),
                }
                logger.exception(f"[会员Token发放] 执行失败 plan_id={plan.id}: {e}")

        await db.commit()

    logger.info("[定时任务] 会员Token分期发放完成")

@scheduler.scheduled_job("interval", hour=1, minute=15)
async def order_expire_job():
    """
    Cancel unpaid orders after the 30-minute payment window.
    """
    logger.info("[定时任务] 开始执行订单过期检查")

    async for db in get_db():
        count = await OrderService.cancel_expired_pending_orders(db)
        await db.commit()

        if count:
            logger.info(f"[定时任务] 订单过期检查完成，关闭订单数={count}")

    logger.info("[定时任务] 订单过期检查结束")


def start_scheduler():
    scheduler.start()
    logger.info("Scheduler started")



def shutdown_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler stopped")
