import json
import re
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional, List

# 配置日志
logger = logging.getLogger("NovelProcessor")

@dataclass(slots=True)
class Chapter:
    index: int  # 章节序号
    title: str  # 章节标题
    content: str  # 章节正文内容
    word_count: int  # 字数统计

class NovelProcessor:
    """小说文本处理工具类：支持章节切分、清洗与结构化输出"""

    # 优化的正则：增加了对空格和复杂符号的容错
    CHAPTER_TITLE_PATTERN = re.compile(
        r"^\s*(?:"
        r"第[0-9零一二三四五六七八九十百千万两]+[章节回卷篇部幕]"
        r"|楔子|序章|引子|尾声|后记"
        r")"
        r"(?:\s*$|[\s:：\-—~～\.．·、,，;；!！?？\(\)（）\[\]【】<>《》]+.+$)"
    )

    def __init__(self):
        self.chapters: List[Chapter] = []

    @classmethod
    def is_chapter_title(cls, line: str) -> bool:
        """判断当前行是否是章节标题"""
        return bool(cls.CHAPTER_TITLE_PATTERN.match(line.strip()))

    def split_text(self, text: str) -> List[Chapter]:
        """
        核心逻辑：将长文本切分为章节对象列表
        """
        start_time = time.perf_counter()
        lines = text.splitlines()
        self.chapters = []

        current_title = "引言/前言"
        current_lines: List[str] = []
        chapter_index = 1

        def flush_chapter(title: str, lines_list: List[str]):
            nonlocal chapter_index
            content = "\n".join(lines_list).strip()
            if content:
                self.chapters.append(Chapter(
                    index=chapter_index,
                    title=title,
                    content=content,
                    word_count=len(content)
                ))
                chapter_index += 1

        for raw_line in lines:
            line = raw_line.strip()
            if self.is_chapter_title(line):
                # 发现新章节，保存上一章节
                if current_lines:
                    flush_chapter(current_title, current_lines)
                    current_lines = []
                current_title = line
                continue
            current_lines.append(raw_line)

        # 保存最后一章
        flush_chapter(current_title, current_lines)

        # 兜底：如果没有识别到任何章节标题
        if not self.chapters and text.strip():
            self.chapters.append(Chapter(
                index=1, title="正文", content=text.strip(), word_count=len(text.strip())
            ))

        duration = time.perf_counter() - start_time
        logger.info(f"文本切分完成: 耗时 {duration:.4f}s, 共切分 {len(self.chapters)} 章")
        return self.chapters

    def process_file(self, file_path: Path) -> List[Chapter]:
        """处理本地文件输入"""
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return []

        text = self._read_safe(file_path)
        return self.split_text(text)

    def _read_safe(self, file_path: Path) -> str:
        """多编码尝试读取"""
        for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return file_path.read_text(encoding="utf-8", errors="ignore")

    def save_to_disk(self, output_dir: Path) -> str:
        """将切分结果持久化到磁盘（可选）"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存 JSON 清单
        manifest = [asdict(c) for c in self.chapters]
        manifest_path = output_dir / "manifest.json"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        logger.info(f"结构化数据已保存至: {output_dir}")
        return str(manifest_path)