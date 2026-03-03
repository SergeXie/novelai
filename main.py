import uvicorn
from loguru import logger

from common.config.config import settings
from common.log.logger import setup_logger, init_app_logging
from server import register_app

# 1. 立即执行日志配置
setup_logger()

# 2. 如果你写了拦截 Uvicorn 日志的逻辑，在这里执行
init_app_logging()

app = register_app()


if __name__ == "__main__":
    logger.info("启动")
    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.UVICORN_PORT)