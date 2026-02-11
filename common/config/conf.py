#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from functools import lru_cache


class Settings:

    # Env MySQL
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str

    # Env Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    REDIS_DATABASE: int

    # Env Token
    TOKEN_SECRET_KEY: str  # 密钥 secrets.token_urlsafe(32)

    # FastAPI
    API_V1_STR: str = '/novelAI'
    TITLE: str = 'FastAPI'
    VERSION: str = '2.0.0'
    DESCRIPTION: str = 'novelAI-接口文档'
    DOCS_URL: str | None = f'{API_V1_STR}/docs'
    REDOCS_URL: str | None = f'{API_V1_STR}/redocs'
    OPENAPI_URL: str | None = f'{API_V1_STR}/openapi'

    # Static Server
    STATIC_FILE: bool = True

    # Limiter
    LIMITER_REDIS_PREFIX: str = 'fsm_limiter'

    # Uvicorn
    APP_ENV: str = 'dev'
    UVICORN_HOST: str = '0.0.0.0'
    UVICORN_PORT: int = 8011
    UVICORN_RELOAD: bool = True

    # DB
    DB_ECHO: bool = False
    DB_DATABASE: str = 'dql_test'
    DB_CHARSET: str = 'utf8mb4'

    # DateTime
    DATETIME_TIMEZONE: str = 'Asia/Shanghai'
    DATETIME_FORMAT: str = '%Y-%m-%d %H:%M:%S'

    # Redis
    REDIS_TIMEOUT: int = 10

    # Captcha
    CAPTCHA_EXPIRATION_TIME: int = 60 * 5  # 过期时间，单位：秒

    # Log
    LOG_STDOUT_FILENAME: str = 'lztrader_access.log'
    LOG_STDERR_FILENAME: str = 'lztrader_error.log'

    # Token
    TOKEN_ALGORITHM: str = 'HS256'
    TOKEN_URL_SWAGGER: str = f'{API_V1_STR}/auth/swagger_login'
    TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 3  # 单位：m

    # 中间件
    MIDDLEWARE_CORS: bool = True
    MIDDLEWARE_GZIP: bool = True
    MIDDLEWARE_ACCESS: bool = False

    limit_num: int = 1000

    last_limit_num: int = 3000

    prefix: str = f"http://127.0.0.1:{UVICORN_PORT}/{API_V1_STR}platform/strategy/"



@lru_cache
def get_settings():
    """读取配置优化写法"""
    return Settings()


settings = get_settings()
