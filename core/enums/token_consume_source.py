import enum

class TokenConsumeSource(enum.Enum):
    FREE = "free"               # 每日免费体验 (Daily Reset)
    MEMBER_MONTHLY = "monthly"  # 会员月度额度 (Monthly Reset)
    BONUS = "bonus"             # 补给奖励额度 (Weekly Bonus)
    PERMANENT = "permanent"     # 永久充值额度 (No Expiry)
    MIXED = "mixed"             # 混合支付 (跨资产抵扣)
    SYSTEM = "system"           # 系统补偿/赠送
