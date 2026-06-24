from enum import Enum

class UserLevel(Enum):
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

class BizType(Enum):
    ORDER = "ORDER"
    AI_CONSUME = "AI_CONSUME"
    REFUND = "REFUND"
    SYSTEM = "SYSTEM"

class ChargeType(Enum):
    RECHARGE = "RECHARGE"
    CONSUME = "CONSUME"
    REFUND = "REFUND"
    EXPIRE = "EXPIRE"
    ADJUS = "ADJUS"

class AssetType(Enum):
    FREE = "FREE"
    MONTHLY = "MONTHLY"
    PERMANENT = "PERMANENT"
    BONUS = "BONUS"

    @classmethod
    def get_descriptions(cls):
        return {
            cls.MONTHLY: "月会员",
            cls.PERMANENT: "Token包",
            cls.BONUS: "补给奖励"
        }

class UserCustomPromptStatus(Enum):
    UNAVAILABLE = (-1, "不可用")
    PENDING = (0, "待审核")
    AVAILABLE = (1, "可用")
    INVALID = (2, "审核不通过")
    TOOLS = (10, "多轮对话工具")
    QUICK_TOOLS = (11, "快捷工具")

    def __init__(self, code, label):
        self.code = code
        self.label = label


class MenuModuleKey(Enum):
    CREATION_TOOLS = "CREATION_TOOLS"
    PROMT_SQUARE_LABELS = "PROMT_SQUARE_LABELS"

if __name__ == '__main__':
    print(ChargeType.RECHARGE.value)
