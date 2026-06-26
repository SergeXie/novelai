from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.user_account_do import AccountLog, UserAccount
from core.entity.vo.redeem_code_vo import RedeemCodeRecordItem
from core.enums.constants import AssetType, BizType, ChargeType
from dao.redeem_code_dao import RedeemCodeDAO
from dao.user_account_dao import UserAccountDAO
from service.account_service import AccountService


class RedeemCodeService:
    STATUS_TEXT = {
        1: "已兑换",
        2: "已作废",
    }

    @staticmethod
    def normalize_code(code: str) -> str:
        return (code or "").strip().upper()

    @staticmethod
    def format_beijing_time(value: datetime | None) -> str | None:
        if not value:
            return None
        return (value + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    async def use_code(db: AsyncSession, user_id: int, code: str) -> dict:
        now = datetime.utcnow()
        normalized_code = RedeemCodeService.normalize_code(code)
        if not normalized_code:
            raise ServiceWarning("兑换码不能为空")

        redeem_code = await RedeemCodeDAO.get_by_code_for_update(db, normalized_code)
        if not redeem_code:
            raise ServiceWarning(message="兑换码不存在")
        if redeem_code.status == 1:
            raise ServiceWarning("兑换码已被使用")
        if redeem_code.status == 2:
            raise ServiceWarning("兑换码已作废")
        if redeem_code.code_expired_time < now:
            redeem_code.status = 2
            await db.commit()
            raise ServiceWarning("兑换码已过期")
        if redeem_code.token_amount <= 0:
            raise ServiceWarning("兑换码额度异常")

        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        if not account:
            account = await AccountService.init_account(db, user_id)

        account.redeem_balance += redeem_code.token_amount
        account.redeem_total_amount += redeem_code.token_amount

        redeem_code.status = 1
        redeem_code.user_id = user_id
        redeem_code.redeem_time = now
        valid_until = now + timedelta(days=redeem_code.valid_days)
        redeem_code.remaining_amount = redeem_code.token_amount
        redeem_code.token_expired_time = valid_until

        db.add(AccountLog(
            user_id=account.user_id,
            biz_id=redeem_code.code,
            biz_type=BizType.SYSTEM.value,
            change_type=ChargeType.RECHARGE.value,
            asset_type=AssetType.REDEEM.value,
            amount=redeem_code.token_amount,
            balance_after=account.redeem_balance,
            extra={
                "source": "redeem_code",
                "code_id": redeem_code.id,
                "batch_id": redeem_code.batch_id,
                "valid_days": redeem_code.valid_days,
                "valid_until": valid_until.strftime("%Y-%m-%d %H:%M:%S"),
            }
        ))

        await db.commit()
        await db.refresh(account)
        return {
            "amount": redeem_code.token_amount,
            "redeemBalance": account.redeem_balance,
        }

    @staticmethod
    async def get_user_redeem_records(
            db: AsyncSession,
            user_id: int,
            page: int,
            page_size: int,
    ) -> tuple[list[RedeemCodeRecordItem], int]:
        rows, total = await RedeemCodeDAO.list_user_redeemed_codes(db, user_id, page, page_size)
        result = []

        for item in rows:
            result.append(RedeemCodeRecordItem(
                code=item.code,
                batchId=item.batch_id,
                tokenAmount=item.token_amount or 0,
                remainingAmount=item.remaining_amount or 0,
                status=item.status,
                statusText=RedeemCodeService.STATUS_TEXT.get(item.status, "未知"),
                redeemTime=RedeemCodeService.format_beijing_time(item.redeem_time),
                tokenExpiredTime=RedeemCodeService.format_beijing_time(item.token_expired_time),
            ))

        return result, total

    @staticmethod
    async def consume_redeem_balance(
            db: AsyncSession,
            account: UserAccount,
            amount: int,
            now: datetime | None = None,
    ) -> int:
        now = now or datetime.utcnow()
        if amount <= 0 or account.redeem_balance <= 0:
            return 0

        remaining = min(amount, account.redeem_balance)
        deducted = 0
        codes = await RedeemCodeDAO.get_active_user_codes_for_update(db, account.user_id, now)

        for code in codes:
            if remaining <= 0:
                break

            deduct = min(code.remaining_amount or 0, remaining)
            if deduct <= 0:
                continue

            code.remaining_amount -= deduct
            remaining -= deduct
            deducted += deduct

        if deducted > 0:
            account.redeem_balance -= deducted
            account.total_consumed += deducted

        return deducted

    @staticmethod
    async def expire_redeem_tokens(db: AsyncSession, now: datetime | None = None) -> int:
        now = now or datetime.utcnow()
        expired_codes = await RedeemCodeDAO.get_expired_redeemed_codes_for_update(db, now)
        count = 0

        for code in expired_codes:
            account = await UserAccountDAO.get_active_account(db=db, user_id=code.user_id)
            if not account:
                code.status = 2
                code.remaining_amount = 0
                count += 1
                continue

            expired_remaining = max(code.remaining_amount or 0, 0)
            if expired_remaining > 0:
                deduct = min(account.redeem_balance or 0, expired_remaining)
                account.redeem_balance = max((account.redeem_balance or 0) - deduct, 0)

                db.add(AccountLog(
                    user_id=account.user_id,
                    biz_id=f"redeem-expire:{code.code}",
                    biz_type=BizType.SYSTEM.value,
                    change_type=ChargeType.EXPIRE.value,
                    asset_type=AssetType.REDEEM.value,
                    amount=-deduct,
                    balance_after=account.redeem_balance,
                    extra={
                        "source": "redeem_code",
                        "reason": "redeem_token_expired",
                        "code_id": code.id,
                        "batch_id": code.batch_id,
                        "token_amount": code.token_amount,
                        "remaining_amount": expired_remaining,
                        "token_expired_time": code.token_expired_time.strftime("%Y-%m-%d %H:%M:%S") if code.token_expired_time else None,
                    }
                ))

            account.redeem_total_amount = max((account.redeem_total_amount or 0) - (code.token_amount or 0), 0)
            code.remaining_amount = 0
            code.status = 2
            count += 1

        return count
