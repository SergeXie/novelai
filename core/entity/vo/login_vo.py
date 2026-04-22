from pydantic import BaseModel, Field


class UserLogin(BaseModel):
    account: str = Field(description='账户')
    password: str = Field(description='密码')

class CurrentUser(BaseModel):
    pkId: int
    uuid: str
    account: str
    nickname: str
