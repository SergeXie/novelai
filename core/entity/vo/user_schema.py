from pydantic import BaseModel


class ChangePasswordReq(BaseModel):
    """
    修改密码请求
    """
    account: str
    password: str
    newPassword: str