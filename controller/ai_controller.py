from http import HTTPStatus
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from ai.adapters.enums import AIProvider
from ai.ai_nexus import get_ai_nexus
from common.config.get_db import get_db, get_db_context
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.vo.ai_model_vo import AiModelResp
from dao.book_dao import BookDAO
from schemas import GenerateRequest
from service.ai_service import AiModelService
from service.usage_service import UsageService

AI = APIRouter()


@AI.get("/engineList", name="模型列表")
async def list_models(
    db=Depends(get_db),
):
    """
    获取 AI 模型列表
    """
    models = await AiModelService.list_models(
        db,
    )
    # 显式走 Pydantic v2（你当前标准做法）
    resp = [AiModelResp.model_validate(m) for m in models]

    return ResponseUtil.success(data=resp)


@AI.post("/generate", summary="根据设定生成小说片段")
async def generate(
    request: GenerateRequest,
    # db=Depends(get_db),
    user=Depends(get_login_user),
    nexus=Depends(get_ai_nexus),
):
    """
    根据设定生成小说片段（输入 / 输出全量留痕）
    """
    user_prompt = request.user_prompt
    correlation = request.correlation
    level = request.level
    temperature = request.temperature

    ai_provider = AIProvider.from_level(level)

    if not user_prompt:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="提示词不能为空")

    # --- 第一阶段：快查并立即释放 ---
    # 使用 contextmanager 确保查完瞬间连接就回池子
    async with get_db_context() as db:
        usage_service = UsageService(db=db)
        await usage_service.check_quota_or_raise(user_id=user.pkId, current_request_len=len(user_prompt))
        nodes_contents = await BookDAO.get_book_nodes_list(db, correlation, user.pkId)

    input_user_prompt = "\n".join(nodes_contents) + "\n" + user_prompt

    system_prompt, output_prompt = "", ""

    try:
        logger.info(f"[{ai_provider.name}] generate input prompt: {input_user_prompt} correlation: {request.correlation}")
        system_prompt, output_prompt = await nexus.generate_novel_text(
            provider=ai_provider,
            user_prompt=input_user_prompt,
            temperature=temperature,
        )
        result = {"content": output_prompt, "len": len(output_prompt)}
        return ResponseUtil.success(data=result)
    except Exception as e:
        # 2. 异常时将错误信息记录到 output_prompt，以便写入日志表
        output_prompt = f"Error: {str(e)}"
        logger.error(f"AI[{ai_provider.name}] Generation Error: {output_prompt}")
        # 重新抛出，交给 FastAPI 抛出 400
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    finally:
        # 3. 重新开启一个会话进行留痕记录
        # 注意：这里需要一个新的 SessionContext，或者再次调用 get_db 逻辑
        async with get_db_context() as new_db:  # 建议封装一个上下文管理器
            new_usage_service = UsageService(db=new_db)
            await new_usage_service.record(
                db=new_db,
                user_id=user.pkId,
                level=level,
                system_prompt=system_prompt,
                user_prompt=input_user_prompt,
                model_name=ai_provider.name,
                temperature=temperature,
                max_tokens=32768,
                output_content=output_prompt,
            )



