import logging
import os
import sys
from loguru import logger

# 日志路径配置
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def setup_logger():
    # 1. 移除默认配置
    logger.remove()

    # 2. 核心技巧：将整个格式用 <level> 标签包裹
    # 这样整行的颜色都会根据 logger.level() 定义的颜色来渲染
    custom_format = "<level>[{time:YYYY-MM-DD HH:mm:ss}][{level:7}] {message}</level>"

    # 3. 添加控制台输出
    logger.add(
        sys.stdout,
        format=custom_format,
        colorize=True,
        level="INFO"
    )

    # 4. 精准配置各个级别的整行颜色
    # WARNING 设为黄色（整行变黄）
    logger.level("WARNING", color="<yellow>")

    # ERROR 设为红色（整行变红）
    logger.level("ERROR", color="<red>")

    # INFO 设为默认颜色（"" 代表不带颜色标签，即终端默认白/灰色）
    logger.level("INFO", color="")

    # DEBUG 设为默认颜色
    logger.level("DEBUG", color="")

    # 添加文件输出
    logger.add(
        f"{LOG_DIR}/WYAI_{{time:YYYY-MM-DD}}.log",
        rotation="00:00",  # 每天零点创建一个新文件
        # retention="30 days",  <-- 删掉这一行或注释掉
        compression="zip",  # 建议保留压缩，否则长期运行磁盘压力会很大
        encoding="utf-8",
        level="DEBUG",
        enqueue=True
    )

    return logger

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# 在 main.py 启动时调用
def init_app_logging():
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)