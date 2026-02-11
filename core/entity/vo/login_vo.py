from pydantic import BaseModel, Field, model_validator


class UserLogin(BaseModel):
    account: str = Field(description='账户')
    password: str = Field(description='密码')

