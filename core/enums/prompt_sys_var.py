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