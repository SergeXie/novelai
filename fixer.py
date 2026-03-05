import asyncio
import uuid
from sqlalchemy import select, update

from common.config.get_db import get_db_context
from core.entity.do.generate_log import AiNovelGenerateLog


async def fix_request_ids():
    async with get_db_context() as db:
        # 1. 获取所有需要修复的记录 ID
        print("正在读取数据库记录...")
        result = await db.execute(select(AiNovelGenerateLog.id))
        ids = result.scalars().all()
        total = len(ids)
        print(f"共发现 {total} 条记录需要修复。")

        # 2. 分批更新，防止 4GB 内存服务器压力过大
        batch_size = 200
        for i in range(0, total, batch_size):
            batch_ids = ids[i: i + batch_size]

            for pk_id in batch_ids:
                # Python 的 uuid4().hex 保证每一行都是全新的字符串
                new_request_id = uuid.uuid4().hex

                await db.execute(
                    update(AiNovelGenerateLog)
                    .where(AiNovelGenerateLog.id == pk_id)
                    .values(requestId=new_request_id)
                )

            # 每处理一个批次提交一次，释放锁和内存
            await db.commit()
            print(f"进度: {i + len(batch_ids)}/{total} 已完成")

    print("✅ 修复完成！现在每行数据都有唯一的 requestId 了。")


if __name__ == "__main__":
    asyncio.run(fix_request_ids())