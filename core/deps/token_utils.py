from loguru import logger


class TokenManager:
    tokens = {}  # token -> {account, expireTime}
    heartbeats = {}  # account -> last_seen

    @classmethod
    def store_token(cls, account, access_token):
        cls.tokens[account] = access_token["accessToken"]
        logger.info(f"account:{account} token存储成功！{cls.tokens}")

    @classmethod
    def get_account_by_token(cls, account):
        accessToken = cls.tokens.get(account)
        if accessToken:
            if accessToken.startswith('Bearer'):
                accessToken = accessToken.split(' ')[1]
            return accessToken

        return None
