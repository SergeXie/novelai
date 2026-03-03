import logging
import os
import sys
from loguru import logger

# 日志路径配置
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def setup_logger():
    # 1. 移除默认控制台输出（为了自定义格式）
    logger.remove()

    # 2. 添加控制台输出 (彩色)
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
        level="INFO"
    )

    # 3. 添加文件输出 (模拟 Log4j2 的 RollingFileAppender)
    logger.add(
        f"{LOG_DIR}/novel_ai.log",
        rotation="500 MB",    # 文件满 500MB 自动切分
        retention="30 days",  # 保留最近 30 天日志
        compression="zip",    # 旧日志压缩存储
        encoding="utf-8",
        level="DEBUG",
        enqueue=True          # 核心：开启异步写入，不阻塞主线程（类似 Log4j2 的 AsyncAppender）
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