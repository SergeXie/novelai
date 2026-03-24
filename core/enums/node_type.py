from enum import Enum

class BookNodeCategory(Enum):
    NORMAL = (0, "自定义")
    CONTENT = (1, "正文")
    ROLES = (2, "角色卡")
    WORLDVIEW = (3, "世界观")
    WRITING_STYLE = (4, "写作手法")

    def __init__(self, code, key):
        self.code = code
        self.key = key

    @classmethod
    def from_code(cls, code: int):
        """
        根据 int 值解析枚举，不存在则返回 BOOK_NAME
        """
        for item in cls:
            if item.code == code:
                return item
        # 如果循环结束未找到，返回默认值
        return cls.NORMAL