from enum import Enum, IntEnum
from typing import Dict

# 等级与供应商值的映射
_LEVEL_MAP: Dict[int, str] = {
    0: "ollama",
    1: "deepseek",
    2: "doubao",
    3: "doubaoplus",
    4: "claude",
    5: "gemini",
    6: "gpt",
    7: "zhipu",
    8: "claudethinking",
}

class AIProvider(str, Enum):
    FREE = "ollama"
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    DOUBAOPLUS = "doubaoplus"
    CLAUDE = "claude"
    GEMINI = "gemini"
    GPT = "gpt"
    ZHIPU = "zhipu"
    CLAUDETHINKING = "claudethinking"


    @classmethod
    def get_provider(cls, value: str | int | None) -> "AIProvider":
        """
        [核心函数] 将多种输入转化为 AIProvider 实例
        支持输入:
        1. 字符串 (如 "deepseek") -> 直接匹配
        2. 整数 (如 1) -> 按等级匹配
        3. None -> 返回默认供应商
        """
        if value is None:
            return cls.DOUBAO

        # 如果输入是整数，走 level 匹配逻辑
        if isinstance(value, int):
            provider_str = _LEVEL_MAP.get(value, cls.DOUBAO.value)
            return cls(provider_str)

        # 如果输入是字符串，尝试直接实例化
        try:
            return cls(value)
        except ValueError:
            # 如果字符串不匹配任何枚举值，返回默认值或抛出异常
            return cls.DOUBAO

    @classmethod
    def from_level(cls, level: int | None) -> "AIProvider":
        """保留原有函数，内部调用 to_provider 以保持逻辑统一"""
        return cls.to_provider(level)

    def to_provider(self) -> "AIProvider":
        """根据当前供应商获取对应的等级"""
        # 反转映射表
        inv_map = {v: k for k, v in _LEVEL_MAP.items()}
        return self.get_provider(inv_map.get(self.value, 2))

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