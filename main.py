import uvicorn
from common.log.log import log
from server import register_app
from common.config.conf import settings

app = register_app()


if __name__ == "__main__":
    log.info("启动")
    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.UVICORN_PORT)