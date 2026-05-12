from typing import Union, List


class LoginException(Exception):
    """
    自定义登录异常LoginException
    """

    def __init__(self, data: Union[str, List[str], None] = None, message: str = None):
        self.data = data
        self.message = message


class AuthException(Exception):
    """
    自定义令牌异常AuthException
    """

    def __init__(self, data: Union[str, List[str], None] = None, message: str = None):
        self.data = data
        self.message = message


class PermissionException(Exception):
    """
    自定义权限异常PermissionException
    """

    def __init__(self, data: Union[str, List[str], None] = None, message: str = None):
        self.data = data
        self.message = message


class ServiceException(Exception):
    """
    自定义服务异常ServiceException
    """

    def __init__(self, data: Union[str, List[str], None] = None, message: str = None):
        self.data = data
        self.message = message


class ServiceWarning(Exception):
    """
    自定义服务警告ServiceWarning
    """

    def __init__(self, data: Union[str, List[str], None] = None, message: str = None):
        self.data = data
        self.message = message


class ServiceWarningSpecial(Exception):
    """
    自定义特殊服务警告ServiceWarning
    """

    def __init__(self, data: Union[str, List[str], None] = None, message: str = None):
        self.data = data
        self.message = message


class ModelValidatorException(Exception):
    """
    自定义模型校验异常ModelValidatorException
    """

    def __init__(self, data: Union[str, List[str], None] = None, message: str = None):
        self.data = data
        self.message = message

class BusinessException(Exception):
    """所有业务异常的基类"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(self.message)

class InsufficientTokenException(BusinessException):
    def __init__(self, message: str = "余额不足请充值", code: int = 666):
        super().__init__(message, code)

class IllegalBookAccessException(BusinessException):
    def __init__(self, message: str = "无权访问该书籍", code: int = 403):
        super().__init__(message, code)

class SensitiveWordException(BusinessException):
    def __init__(self, message: str = "内容包含敏感词，请修改后重试", code: int = 400):
        super().__init__(message, code)