# --- 4. Main 测试函数 ---
import asyncio

from common.config.config import settings
from common.config.get_db import get_db_context
from common.modules.book_exporter import BookExporter
from database.db_mysql import async_engine
from service.book_service import BookService


async def main():
    bid = "07eb925abde34316929367eac46903b2"
    user_id = 41

    print("📝 数据准备就绪，开始导出...\n")

    # B. 测试导出功能
    async with get_db_context() as db:
        book_service = BookService(db)
        book = await book_service.get_book_by_bid(bid=bid, user_id=user_id)
        nodes = await book_service.get_basic_nodes(bid=bid, user_id=user_id)
        leaf_ids = [node.id for node in nodes]
        print(nodes)
        exporter = BookExporter(db)
        markdown_result = await exporter.export_to_markdown(book=book,  leaf_node_ids=leaf_ids)

    print("\n--- 导出的内容如下 ---")
    print(markdown_result)
    print("----------------------\n")


    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())