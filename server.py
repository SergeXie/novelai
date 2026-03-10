#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from common.config.config import settings
from common.exception.handle import handle_exception
from controller.ai_controller import aiController
from controller.book_controller import bookController
from controller.login_controller import loginController
from controller.prompt_controller import promptController
from controller.template_controller import templateController
from controller.user_controller import userController


@asynccontextmanager
async def register_init(app: FastAPI):
    """
    启动初始化

    :return:
    """
    print("初始化")

def register_app():
    # FastAPI
    app = FastAPI(
        title=settings.TITLE,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        # docs_url=settings.DOCS_URL,
        # redoc_url=settings.REDOCS_URL,
        openapi_url=settings.OPENAPI_URL,
        # lifespan=register_init,
    )
    # 中间件
    register_middleware(app)
    # 路由
    register_router(app)
    # 加载全局异常处理方法
    handle_exception(app)

    return app


def register_middleware(app) -> None:
    # 添加gzip压缩中间件
    if settings.MIDDLEWARE_GZIP:
        app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=9)

    # 跨域
    if settings.MIDDLEWARE_CORS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=['*'],
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*'],
        )


def register_router(app: FastAPI):
    """
    路由

    :param app: FastAPI
    :return:
    """
    controller_list = [
        {'router': loginController, 'tags': ['登录接口']},
        {'router': aiController, 'tags': ['AI']},
        {'router': promptController, 'tags': ['提示词']},
        {'router': bookController, 'tags': ['作品服务接口']},
        {'router': userController, 'tags': ['用户相关接口']},
        {'router': templateController, 'tags': ['书籍模板类型（作品类型）']}
    ]

    for controller in controller_list:
        app.include_router(prefix=settings.API_V1_STR, router=controller.get('router'), tags=controller.get('tags'))


