from html.parser import HTMLParser

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, d):
        self.result.append(d)

    def get_text(self):
        return "".join(self.result)

def quick_html_to_text(html_str: str) -> str:
    parser = HTMLTextExtractor()
    parser.feed(html_str)
    return parser.get_text()

def write_simple_txt(file_path, content):
    # 'w' 表示写入模式（会覆盖原内容）；'a' 表示追加模式
    # encoding="utf-8-sig" 是为了兼容 Windows 记事本，防止中文乱码
    with open(file_path, "w", encoding="utf-8-sig") as f:
        f.write(content)