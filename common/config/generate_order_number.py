import datetime
import random


def generate_order_no():
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


# 测试生成
if __name__ == "__main__":
    for _ in range(5):
        print(generate_order_no())