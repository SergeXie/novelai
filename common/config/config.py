from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai.config_model import LLMProviderConfig


class Settings(BaseSettings):
    # Uvicorn
    APP_ENV: str = 'dev'
    UVICORN_HOST: str = '0.0.0.0'
    UVICORN_PORT: int = 8011
    UVICORN_RELOAD: bool = True

    # 中间件
    MIDDLEWARE_CORS: bool = True
    MIDDLEWARE_GZIP: bool = True
    MIDDLEWARE_ACCESS: bool = False

    # FastAPI
    API_V1_STR: str = '/novelAI'
    TITLE: str = 'FastAPI'
    VERSION: str = '2.0.0'
    DESCRIPTION: str = 'novelAI-接口文档'
    DOCS_URL: str | None = f'{API_V1_STR}/docs'
    REDOCS_URL: str | None = f'{API_V1_STR}/redocs'
    OPENAPI_URL: str | None = f'{API_V1_STR}/openapi'

    # --- 数据库配置 ---
    # 不设置默认值，强制要求环境变量中有 DATABASE_URL
    DATABASE_URL: str = Field(alias="DATABASE_URL")

    # --- 用户级别限制 ---
    USER_DAILY_TOKEN_LIMIT: int = Field(alias="USER_DAILY_TOKEN_LIMIT")
    SINGLE_REQUEST_TOKEN_LIMIT: int = Field(alias="SINGLE_REQUEST_TOKEN_LIMIT")

    # --- 平台级别限制 ---
    PLATFORM_DAILY_TOKEN_LIMIT: int = Field(alias="PLATFORM_DAILY_TOKEN_LIMIT")

    MULTIPLIER: float = Field(alias="MULTIPLIER")
    # --- 计费与模型配置 ---
    # 模型配置嵌套
    # Pydantic 会自动寻找以 DEEPSEEK_ 开头和 OPENAI_ 开头的环境变量
    deepseek: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    doubao: LLMProviderConfig = Field(default_factory=LLMProviderConfig)

    free: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    doubaoplus: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    claude: LLMProviderConfig = Field(default_factory=LLMProviderConfig)

    # 读取环境变量，设置默认值为空字符串
    ai_system_prompt: str = Field(default="", alias="AI_SYSTEM_PROMPT")

    # Jwt配置
    jwt_secret_key: str = 'b01c66dc2c58dc6a0aabfe2144256be36226de378bf87f72c0c795dda67f4d55'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 43200
    jwt_redis_expire_minutes: int = 30

    @field_validator("ai_system_prompt", mode="after")
    @classmethod
    def format_line_breaks(cls, v: str) -> str:
        """自动处理 \n 转义字符为真实换行"""
        if isinstance(v, str):
            # 将配置中的 \n 替换为实际换行符，并去除首尾空格
            return v.replace("\\n", "\n").strip()
        return v

    # 配置加载规则
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False,  # 区分大小写，通常环境变量推荐全大写
        env_nested_delimiter='__',
        extra='ignore'
    )

settings = Settings()