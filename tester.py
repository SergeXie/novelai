# --- 4. Main 测试函数 ---
import asyncio

from common.config.config import settings
from common.config.get_db import get_db_context
from common.modules.book_exporter import BookExporter
from database.db_mysql import async_engine
from demo import fix_book_node
from demo.fix_book_node import repair_book_node_data
from service.book_service import BookService

async def main():
    """
    主入口：管理数据库上下文并调用修复函数
    """
    try:
        # 1. 使用异步上下文管理器获取 session
        async with get_db_context() as db:
            print("数据库连接成功，开始修复数据...")
            # 2. 将 db (AsyncSession) 传入修复函数
            await repair_book_node_data(db)
            print("任务执行完毕。")

        await async_engine.dispose()
    except Exception as e:
        print(f"程序运行出错: {e}")


if __name__ == "__main__":
    # 3. 使用 asyncio.run 启动顶层异步任务
    asyncio.run(main())