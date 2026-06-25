from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider, AIAction
from ai.ai_nexus import get_ai_nexus
from common.config.config import settings
from common.utils.generator import LZSDGenerator
from common.config.get_db import get_db_context
from core.entity.do.users_do import User
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from service.usage_service import UsageService

from service.ai_service import AIService


class WorkflowService(AIService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def list_models(self, only_enabled: bool = True):
        """
        获取模型列表
        """
        aimodel_dao = AiModelDAO(self.db)
        return await aimodel_dao.list_models(
            only_enabled=only_enabled,
        )

    async def delete_history(self, uid: int, request_ids: list):
        await AILogDAO.logic_delete(
            db=self.db,
            uid=uid,
            request_ids=request_ids
        )

        return True

    async def prepare_and_record_request(
            self,
            user: User,
            bid: str,
            origin_prompt: str,
            user_prompt: str,
            level: int,
            temperature: float,
            action_type: str,
            correlation=None,
            background_tasks=None
    ) -> str:
        """
        第一阶段：校验、记录、生成请求ID (同步执行，快速返回)
        """
        user_id = user.pkId

        request_id = LZSDGenerator.generate_request_id()
        if correlation is None:
            correlation = []

        input_user_prompt = user_prompt

        usage_service = UsageService(self.db)
        # 3. 初始存证（此时 output_content 为空）
        await usage_service.record(
            user_id=user_id,
            request_id=request_id,
            level=level,
            node_ids=correlation,
            bid=bid,
            origin_prompt=origin_prompt,
            system_prompt="",  # 初始为空
            user_prompt=input_user_prompt,
            temperature=temperature,
            output_content="",
            action_type=AIAction(action_type),
        )

        # 4. 第二阶段：将耗时的 AI 生成丢入后台任务，不阻塞当前响应
        if background_tasks is not None:
            background_tasks.add_task(
                async_generate_task,  # 具体的执行函数
                level,
                input_user_prompt,
                temperature=temperature,
                request_id=request_id,
            )

        return request_id

async def async_generate_task(level, input_user_prompt, temperature, request_id):
    """后台异步执行 AI 调用并更新结果"""
    system_prompt, output_prompt = "", ""
    ai_provider = AIProvider.parse(level)
    try:
        # 真正的 AI 耗时操作
        nexus = get_ai_nexus()
        system_prompt = settings.ai_system_prompt

        system_prompt, output_prompt = await nexus.generate_novel_text(
            system_prompt=system_prompt,
            provider=ai_provider,
            user_prompt=input_user_prompt,
            temperature=temperature
        )
        status = 1  # 成功
    except Exception as e:
        output_prompt = f"Error: {str(e)}"
        status = 0  # 失败
        logger.error(f"Async Generation Error for {request_id}: {output_prompt}")

    # 使用新的数据库上下文更新结果
    async with get_db_context() as db:
        usage_service = UsageService(db=db)
        await usage_service.update_output_content_by_request_id(request_id, output_prompt)
