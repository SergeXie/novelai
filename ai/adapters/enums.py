from enum import Enum, IntEnum
from enum import IntEnum

class AIProvider(IntEnum):
    FREE = 0
    DEEPSEEK = 1
    DOUBAO = 2
    DOUBAOPLUS = 3
    CLAUDE = 4
    GEMINI = 5
    GPT = 6
    ZHIPU = 7
    CLAUDETHINKING = 8

    @classmethod
    def parse(cls, value: int | None) -> "AIProvider":
        """
        将整数转化为 AIProvider 实例
        如果输入为 None 或未在枚举中定义，则默认为 DOUBAO (2)
        """
        if value is None:
            return cls.DOUBAO

        try:
            return cls(value)
        except ValueError:
            # 当 value 不在 0-8 范围内时，返回默认供应商
            return cls.DOUBAO

class AIAction(str, Enum):
    Unknown = "unknown"
    Generate = "generate"
    Render = "render"
    WorkFlow = "workflow"
    Execute = "execute",
    Chat = "chat"

    @classmethod
    def _missing_(cls, value):
        """
        当传入的值不在定义范围内时（不区分大小写），默认返回 Unknown
        """
        if isinstance(value, str):
            # 兼容性处理：转为小写后再匹配
            normalized_value = value.lower()
            for item in cls:
                if item.value == normalized_value:
                    return item
        return cls.Unknown

class AIGenerateStatus(IntEnum):
    PENDING = 0      # 待处理（任务已创建，等待进入队列）
    PROCESSING = 1   # 生成中（AI 正在推理，此时 Token 已预冻结）
    SUCCESS = 2      # 成功（内容已回填，Token 实际扣除）
    FAILED = 3       # 失败（记录错误信息，触发自动退费/回滚）
    TIMEOUT = 4      # 超时（长耗时任务超过 5 分钟未返回）
    CANCELLED = 5    # 已取消（用户手动中止或客户端断开）