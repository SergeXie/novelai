from enum import Enum

class PromptSysVar(str, Enum):
    """
    文源系统内置提示词变量
    前缀 sys_ 表示该变量由后端逻辑自动提取并替换
    """
    BOOK_NAME = "sys_book_name"        # 作品名称
    BOOK_INTRO = "sys_book_intro"      # 作品简介
    CHAR_LIST = "sys_role_list"        # 角色列表设定
    WORLD_VIEW = "sys_world_view"      # 世界观设定
    STYLE = "sys_style"                # 写作手法/口吻
    CUR_CHAPTER = "sys_cur_chapter"    # 当前章节标题
    LAST_CONTENT = "sys_last_content"  # 上一章摘要（用于保持连贯性）


class PromptEngineType(str, Enum):
    """渲染引擎类型枚举"""
    JINJA2 = "jinja2"
    FSTRING = "fstring"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """校验值是否在枚举范围内"""
        return value in cls._value2member_map_

    @classmethod
    def from_str(cls, value: str) -> "PromptEngineType":
        """
        将字符串转换为枚举，不存在则返回 JINJA2
        """
        try:
            # 尝试根据 value 实例化枚举
            return cls(value.lower())
        except ValueError:
            # 转换失败则返回默认值
            return cls.JINJA2

class PromptTopCategory(str, Enum):
    """系统顶级分类枚举"""
    CREATION = ("CREATION", "创作类")
    SCENARIO = ("SCENARIO", "专项类")
    UTILITY = ("UTILITY", "快捷工具")

    def __new__(cls, code: str, label: str):
        # 继承 str 时，需要用 __new__ 来正确初始化枚举的值
        obj = str.__new__(cls, code)
        obj._value_ = code
        obj.code = code
        obj.label = label
        return obj
