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