from loguru import logger
from abc import ABC, abstractmethod


class BasePayment(ABC):
    """
    支付抽象基类

    所有支付方式必须实现：
    - generate_pay_url
    - （后续）handle_callback
    """

    @abstractmethod
    def generate_pay_url(self, order):
        """
        生成支付链接

        :param order: 订单对象
        :return: pay_url
        """
        pass