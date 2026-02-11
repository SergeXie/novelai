import os
from functools import lru_cache


class UploadConfig:
    """
    上传配置
    """

    UPLOAD_PREFIX = '/profile'
    UPLOAD_PATH = 'profile/strategys/upload_path'  # 上次策略文件目录
    UPLOAD_TRADE_PATH = 'profile/strategys/trader_report'  # 策略交易报告上传目录
    UPLOAD_MACHINE = 'A'
    DEFAULT_ALLOWED_EXTENSION = [
        # 图片
        'bmp',
        'gif',
        'jpg',
        'jpeg',
        'png',
        # word excel powerpoint
        'doc',
        'docx',
        'xls',
        'xlsx',
        'ppt',
        'pptx',
        'html',
        'htm',
        'txt',
        # 压缩文件
        'rar',
        'zip',
        'gz',
        'bz2',
        # 视频格式
        'mp4',
        'avi',
        'rmvb',
        # pdf
        'pdf',
        "py"
    ]

    def __init__(self):
        if not os.path.exists(self.UPLOAD_PATH):
            os.makedirs(self.UPLOAD_PATH)

        if not os.path.exists(self.UPLOAD_TRADE_PATH):
            os.makedirs(self.UPLOAD_TRADE_PATH)


@lru_cache
def get_upload_config():
    """读取配置优化写法"""
    return UploadConfig()


upload_config = get_upload_config()
