from loguru import logger


class AccountService:
    """
    账户服务（发权益）
    """

    @staticmethod
    async def grant_order_benefits(db, order):
        """
        根据订单发放权益
        """

        logger.info(f"[权益] 开始发放 order_no={order.order_no}")

        snapshot = order.snapshot_content

        if order.order_type == "MEMBERSHIP":
            await AccountService._grant_membership(db, order.uid, snapshot)

        elif order.order_type == "TOKEN_PACKAGE":
            await AccountService._grant_token(db, order.uid, snapshot)

    @staticmethod
    async def _grant_membership(db, uid, snapshot):
        """
        发会员
        """
        logger.info(f"[权益] 发会员 uid={uid}")

        # TODO: 你后面接 mc_user_accounts
        # level_code + expire_at
        pass

    @staticmethod
    async def _grant_token(db, uid, snapshot):
        """
        发Token
        """
        logger.info(f"[权益] 发Token uid={uid}")

        token = snapshot.get("token_amount", 0)

        # TODO: 更新 permanent_balance
        pass