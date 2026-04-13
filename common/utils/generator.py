import datetime
import random
import secrets
import string

class LZSDGenerator:
    def __init__(self):
        pass

    @staticmethod
    def generate_user_uid(size:int = 36)->str:
        # 生成 12 位包含字母和数字的随机字符串
        alphabet = string.ascii_letters + string.digits
        return ("UID" + ''.join(secrets.choice(alphabet) for _ in range(size))).upper()

    @staticmethod
    def generate_order_no()->str:
        """
        生成订单号：100 + 2位年+2位月+2位日+2位时+2位分+2位秒 + 6位随机数字
        格式：100YYMMDDHHMMSSRRRRRR
        """
        # 1. 前缀
        prefix = "100"

        # 2. 获取当前时间并格式化为 2位单位
        # %y 是两位年份, %m 月, %d 日, %H 时, %M 分, %S 秒
        now_str = datetime.datetime.now().strftime("%y%m%d%H%M%S")

        # 3. 生成 6 位随机数字 (000000 - 999999)
        # 使用 zfill 确保不满 6 位时前面补 0
        random_str = str(random.randint(0, 999999)).zfill(6)

        # 4. 拼接
        order_no = f"{prefix}{now_str}{random_str}"

        return order_no

    @staticmethod
    def generate_request_id(sign:str = None)->str:
        # 1. 获取当前时间，格式化为微秒级（或秒级，看需求）
        # 格式：年月日-时分秒
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # 2. 生成一小段随机字符串，防止同一秒内碰撞
        # 使用 secrets 模块比 random 更安全
        random_suffix = secrets.token_hex(6).upper()  # 生成 12 位 16 进制字符

        base = f"REQ-{timestamp}-{random_suffix}"
        return f"{base}-{sign}" if sign else base

    @staticmethod
    def generate_book_id() -> str:
        # 1. 获取当前时间，格式化为微秒级（或秒级，看需求）
        # 格式：年月日-时分秒
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")

        # 2. 生成一小段随机字符串，防止同一秒内碰撞
        # 使用 secrets 模块比 random 更安全
        random_suffix = secrets.token_hex(6).upper()  # 生成 12 位 16 进制字符

        return f"BID{timestamp}{random_suffix}"

    @staticmethod
    def generate_template_id(length:int=16)->str:
        """
                        生成全大写字母的提示词模板 ID
                        :param length: 随机字母的长度（不含前缀）
                        :return: 示例: TPLABCDE...
                        """
        # 定义前缀
        prefix = "PRMT"

        # 从 A-Z 中随机挑选指定数量的字符
        # secrets.choice 比 random.choice 更适用于生成唯一标识
        letters = string.ascii_uppercase
        random_str = ''.join(secrets.choice(letters) for _ in range(length))

        return f"{prefix}{random_str}"


# 测试生成
if __name__ == "__main__":
    for _ in range(20):
        print(LZSDGenerator.generate_template_id())