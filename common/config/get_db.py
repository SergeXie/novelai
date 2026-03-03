from database.db_mysql import AsyncSessionLocal


async def get_db():
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接

    :return:
    """
    async with AsyncSessionLocal() as current_db:
        try:
            yield current_db
            await current_db.commit()

        except Exception as se:
            await current_db.rollback()
            raise se
        finally:
            await current_db.close()

from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_context():
    """
    手动控制的异步上下文管理器
    用于 AI 生成等长耗时操作，确保查完即关，不占用连接等 AI
    """
    async with AsyncSessionLocal() as current_db:
        try:
            yield current_db
            # 注意：这里是否 commit 取决于你是否有写操作
            # 如果只是查询，这行不执行也没关系
            await current_db.commit()
        except Exception as se:
            await current_db.rollback()
            raise se
        finally:
            # 退出 with 块时立即关闭连接
            await current_db.close()