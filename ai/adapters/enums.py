from enum import Enum, IntEnum


class AIProvider(str, Enum):
    FREE = "ollama"
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    DOUBAOPLUS = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    GPT = "gpt"
    ZHIPU = "zhipu"

    @classmethod
    def from_level(cls, level: int) -> "AIProvider":
        """
        根据用户等级或推理等级返回对应的供应商
        1: 基础模型 (豆包)
        2: 进阶模型 (DeepSeek)
        3: 旗舰模型 (OpenAI)
        """
        # 定义等级与枚举的映射关系
        # 使用字典存储不同等级对应的AI服务提供商
        level_map = {
            0: cls.FREE,        # 0级对应免费版
            1: cls.DEEPSEEK,    # 1级对应DeepSeek模型
            2: cls.DOUBAO,      # 2级对应豆包模型
            3: cls.DOUBAOPLUS,  # 3级对应豆包Plus模型
            4: cls.CLAUDE,      # 4级对应Claude模型
            5: cls.GEMINI,      # 5级Gemini模型
            6: cls.GPT,         # 6级对应GPT模型
            7: cls.ZHIPU,       # 7级对应智谱模型
        }

        # 使用 dict.get() 实现“默认返回豆包”的逻辑
        return level_map.get(level, cls.DOUBAO)

class AIAction(str, Enum):
    Unknown = "unknown"
    Generate = "generate"
    Render = "render"
    WorkFlow = "workflow"

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