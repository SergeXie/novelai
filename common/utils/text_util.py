import re
import hashlib

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


def generate_text_sha256_id(text: str) -> str:
    # 预处理：标准化处理防止因为微小差异导致哈希不同
    clean_text = text.strip().encode('utf-8')
    return hashlib.sha256(clean_text).hexdigest()