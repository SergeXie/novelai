import re


def strip_html_tags(text: str) -> str:
    """
    去除HTML标签
    """
    if not text:
        return ""

    # 去掉标签
    clean = re.sub(r"<[^>]+>", "", text)

    # 去掉多余空白
    clean = clean.strip()

    return clean