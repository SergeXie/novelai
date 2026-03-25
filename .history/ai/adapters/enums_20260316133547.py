from enum import Enum

class AIProvider(str, Enum):
    FREE = "ollama"
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    DOUBAOPLUS = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"

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
        }

        # 使用 dict.get() 实现“默认返回豆包”的逻辑
        return level_map.get(level, cls.DOUBAO)
