from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from common.exception.lzsd_exception import BusinessException
from common.utils.generator import LZSDGenerator
from core.entity.do.ai_chat_do import AIChatGroupDO
from core.entity.do.users_do import User
from core.entity.vo.ai_chat_vo import ChatGroupVO


class AIChatService:
    @staticmethod
    async def get_groups(db: AsyncSession, current_user: User) -> List[ChatGroupVO]:
        """
        获取当前用户的所有对话分组
        排序逻辑：置顶优先 > 权重从高到低 > 创建时间倒序
        """
        # 1. 构建查询语句
        stmt = (
            select(AIChatGroupDO)
            .filter(AIChatGroupDO.user_id == current_user.pkId)
            .order_by(
                AIChatGroupDO.is_pinned.desc(),  # 置顶的在最前
                AIChatGroupDO.weight.desc(),  # 权重大的在前面
                AIChatGroupDO.updated_at.desc()
            )
        )

        # 2. 执行异步查询
        result = await db.execute(stmt)
        group_dos = result.scalars().all()

        # 3. 将 DO 对象转换为 VO 对象
        # 使用 Pydantic 的 model_validate (Pydantic v2) 或 from_orm (Pydantic v1)
        return [ChatGroupVO.model_validate(group) for group in group_dos]

    @staticmethod
    async def delete_group(db: AsyncSession, gid: str, current_user: User):
        """
        删除分组
        逻辑：
        1. 校验分组是否存在且属于当前用户
        2. 执行删除操作
        3. 数据库会自动处理关联对话的 group_id (设为 NULL)
        """
        # 1. 查找目标分组
        stmt = select(AIChatGroupDO).filter(
            AIChatGroupDO.gid == gid,
            AIChatGroupDO.user_id == current_user.pkId
        )
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()

        # 2. 权限与存在性校验
        if not group:
            raise BusinessException(code=404, message="分组不存在或无权操作")

        # 3. 执行删除
        # 注意：由于我们在数据库定义了 FOREIGN KEY ... ON DELETE SET NULL
        # 这里的 delete 操作会自动将 ai_conversations 表中关联的 group_id 更新为 NULL
        await db.delete(group)

        # 4. 提交事务
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise e

    @staticmethod
    async def completions(
            db: AsyncSession,
            current_user: User,
            content: str,
            gid: str = None
    ) -> str:
        """
        AI 对话核心实现
        :param gid: 分组业务ID，如果为空则创建新分组
        :param content: 用户首条消息内容（用于提取标题）
        """
        target_group_id = None  # 数据库内部自增ID

        user_id = current_user.pkId

        # --- 1. 处理分组逻辑 ---
        if not gid:
            # A. GID为空：创建新分组
            # 提取前20个字作为名称
            group_name = content[:20] if content else "新对话分组"
            target_group_id = LZSDGenerator.generate_chat_group_id()
            new_group = AIChatGroupDO(
                gid=target_group_id,
                user_id=user_id,
                name=group_name,
                weight=0
            )
            db.add(new_group)
            await db.flush()
            print(f"已自动创建分组: {group_name}")

        else:
            target_group_id = gid
            # B. GID不为空：查询是否存在并属于该用户
            stmt = select(AIChatGroupDO).filter(
                AIChatGroupDO.gid == gid,
                AIChatGroupDO.user_id == user_id
            )
            result = await db.execute(stmt)
            group = result.scalar_one_or_none()

            if not group:
                raise BusinessException(
                    code=status.HTTP_404_NOT_FOUND,
                    message="指定的分组不存在或无权访问"
                )
        await db.commit()
        return target_group_id


