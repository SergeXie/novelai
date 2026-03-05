import datetime
from dateutil import parser


def object_format_datetime(obj):
    """
    :param obj: 输入一个对象
    :return:对目标对象所有datetime类型的属性格式化
    """
    for attr in dir(obj):
        value = getattr(obj, attr)
        if isinstance(value, datetime.datetime):
            setattr(obj, attr, value.strftime('%Y-%m-%d %H:%M:%S'))
    return obj


def list_format_datetime(lst):
    """
    :param lst: 输入一个嵌套对象的列表
    :return: 对目标列表中所有对象的datetime类型的属性格式化
    """
    for obj in lst:
        for attr in dir(obj):
            value = getattr(obj, attr)
            if isinstance(value, datetime.datetime):
                setattr(obj, attr, value.strftime('%Y-%m-%d %H:%M:%S'))
    return lst


def format_datetime_dict_list(dicts):
    """
    递归遍历嵌套字典，并将 datetime 值转换为字符串格式

    :param dicts: 输入一个嵌套字典的列表
    :return: 对目标列表中所有字典的datetime类型的属性格式化
    """
    result = []

    for item in dicts:
        new_item = {}
        for k, v in item.items():
            if isinstance(v, dict):
                # 递归遍历子字典
                new_item[k] = format_datetime_dict_list([v])[0]
            elif isinstance(v, datetime.datetime):
                # 如果值是 datetime 类型，则格式化为字符串
                new_item[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # 否则保留原始值
                new_item[k] = v
        result.append(new_item)

    return result


def parse_and_format_date(date_input=None, date_format='%Y-%m-%d %H:%M:%S'):
    """
    解析日期字符串并格式化为指定格式的日期字符串。

    :param date_input: 接受 datetime 或 字符串，格式化为指定格式的日期字符串。
    :param date_format: 输出日期字符串的格式。
    :return: 格式化后的日期字符串。
    """
    if date_input is None:
        date_obj = datetime.datetime.now()
    elif isinstance(date_input, datetime.datetime):
        date_obj = date_input
    else:
        date_obj = parser.parse(str(date_input))  # 确保能处理数字/其他类型

    return date_obj.strftime(date_format)
