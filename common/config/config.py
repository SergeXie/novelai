from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai.config_model import LLMProviderConfig


class Settings(BaseSettings):
    # Uvicorn
    APP_ENV: str = 'dev'
    UVICORN_HOST: str = '0.0.0.0'
    UVICORN_PORT: int = Field(alias="PORT")
    UVICORN_RELOAD: bool = True

    # 中间件
    MIDDLEWARE_CORS: bool = True
    MIDDLEWARE_GZIP: bool = True

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

    ENV_MODE: str = Field(alias="ENV_MODE")

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
    claudethinking: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    gemini: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    gpt: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    zhipu: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    mimo: LLMProviderConfig = Field(default_factory=LLMProviderConfig)

    # 读取环境变量，设置默认值为空字符串
    ai_system_prompt: str = Field(default="", alias="AI_SYSTEM_PROMPT")
    ai_temperature: float = Field(default=0.7, alias="AI_DEFAULT_TEMPERATURE")
    ai_max_tokens: int = Field(default=4096, alias="AI_MAX_TOKENS")

    # Jwt配置
    jwt_secret_key: str = 'b01c66dc2c58dc6a0aabfe2144256be36226de378bf87f72c0c795dda67f4d55'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 43200
    jwt_redis_expire_minutes: int = 30

    # ==================== 支付配置：支付宝 ====================

    ALIPAY_APP_ID: str = Field(alias="ALIPAY_APP_ID")
    ALIPAY_PRIVATE_KEY: str = Field(alias="ALIPAY_PRIVATE_KEY")
    ALIPAY_PUBLIC_KEY: str = Field(alias="ALIPAY_PUBLIC_KEY")

    ALIPAY_NOTIFY_URL: str = Field(alias="ALIPAY_NOTIFY_URL")
    ALIPAY_RETURN_URL: str = Field(alias="ALIPAY_RETURN_URL")
    ALIPAY_GATEWAY: str = Field(alias="ALIPAY_GATEWAY")

    # ==================== 支付配置：微信 ====================
    WECHATPAY_MCHID: str = Field(alias="WECHATPAY_MCHID", default="")
    WECHATPAY_PRIVATE_KEY_PATH: str = Field(alias="WECHATPAY_PRIVATE_KEY_PATH", default="")
    WECHATPAY_CERT_SERIAL_NO: str = Field(alias="WECHATPAY_CERT_SERIAL_NO", default="")
    WECHATPAY_APPID: str = Field(alias="WECHATPAY_APPID", default="")
    WECHATPAY_APIV3_KEY: str = Field(alias="WECHATPAY_APIV3_KEY", default="")
    WECHATPAY_NOTIFY_URL: str = Field(alias="WECHATPAY_NOTIFY_URL", default="")
    WECHATPAY_CERT_DIR: str = Field(alias="WECHATPAY_CERT_DIR", default="")
    WECHATPAY_PARTNER_MODE: str = Field(alias="WECHATPAY_PARTNER_MODE", default="False")
    WECHATPAY_TYPE: str = Field(alias="WECHATPAY_TYPE", default="")
    PUBLIC_KEY: str = Field(alias="PUBLIC_KEY", default="")
    PUBLIC_KEY_ID: str = Field(alias="PUBLIC_KEY_ID", default="")

    CLOUD_ADDRESS: str = Field(alias="CLOUD_ADDRESS", default="")
    IMAGE_DOWNLOAD_URL: str = Field(alias="IMAGE_DOWNLOAD_URL", default="http://8.138.95.62:8000/downloadFile")

    UPLOAD_USERS_DIR: str = Field(alias="UPLOAD_USERS_DIR", default="")
    WEB_SEARCH_API_KEY: str = Field(alias="WEB_SEARCH_API_KEY", default="")
    WEB_SEARCH_URL: str = Field(alias="WEB_SEARCH_URL", default="https://open.feedcoopapi.com/search_api/web_search")

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

    # 封装判断逻辑
    @property
    def is_dev(self) -> bool:
        return self.ENV_MODE.lower() in ("development", "dev", "local")

    @property
    def is_prod(self) -> bool:
        return self.ENV_MODE.lower() in ("production", "prod")

settings = Settings()