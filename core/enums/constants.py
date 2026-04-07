import enum

class UserLevel(enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO_MONTHLY = "pro_monthly"
    PRO_ANNUAL = "pro_annual"
    ENTERPRISE = "enterprise"

    @classmethod
    def get_descriptions(cls):
        return {
            cls.FREE: "免费用户",
            cls.BASIC: "标准版",
            cls.PRO_MONTHLY: "专业月会员",
            cls.PRO_ANNUAL: "专业年会员",
            cls.ENTERPRISE: "企业版"
        }

class BizType(enum.Enum):
    ORDER = "ORDER"
    AI_CONSUME = "AI_CONSUME"
    REFUND = "REFUND"
    SYSTEM = "SYSTEM"

class ChargeType(enum.Enum):
    RECHARGE = "RECHARGE"
    CONSUME = "CONSUME"
    REFUND = "REFUND"
    EXPIRE = "EXPIRE"
    ADJUS = "ADJUS"

class AssetType(enum.Enum):
    MONTHLY = "MONTHLY"
    PERMANENT = "PERMANENT"

    @classmethod
    def get_descriptions(cls):
        return {
            cls.MONTHLY: "月会员",
            cls.PERMANENT: "Token包"
        }


if __name__ == '__main__':
    print(ChargeType.RECHARGE.value)