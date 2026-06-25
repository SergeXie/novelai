import textwrap
from typing import Optional

import httpx
from fastapi import BackgroundTasks
from loguru import logger

from ai.adapters.enums import AIProvider, AIAction, AIGenerateStatus
from ai.ai_nexus import get_ai_nexus
from common.config.config import settings
from common.config.get_db import get_db_context
from common.utils.generator import LZSDGenerator
from core.deps.auth import check_user_quota_or_raise
from core.entity.do.generate_log import AiNovelGenerateLog
from core.entity.do.users_do import User
from service.ai_service import AIService
from service.usage_service import UsageService


class AIImageService(AIService):

    async def generate_image(
            self,
            user: User,
            prompt: str,
            size: str = "2K",
            n: int = 1,
            watermark: bool = False,
            provider: AIProvider = AIProvider.DOUBAOIMAGE,
            response_format: str = "url",
            extra_body: dict | None = None,
            background_tasks: Optional[BackgroundTasks] = None,
    ) -> tuple[str, str | None]:
        cleaned_prompt = (prompt or "").strip()
        if not cleaned_prompt:
            raise ValueError("提示词不能为空")

        await check_user_quota_or_raise(frozen_token_length=settings.IMAGE_GENERATE_TOKEN_COST, level=10)

        request_id = LZSDGenerator.generate_request_id()
        log = await UsageService(self.db).record(
            user_id=user.pkId,
            request_id=request_id,
            level=provider.value,
            bid=request_id,
            origin_prompt=cleaned_prompt,
            system_prompt="",
            user_prompt=cleaned_prompt,
            temperature=0,
            output_content="",
            action_type=AIAction.Image,
            promptTokens=len(cleaned_prompt),
            completionTokens=settings.IMAGE_GENERATE_TOKEN_COST,
        )

        task_kwargs = {
            "request_id": request_id,
            "prompt": cleaned_prompt,
            "size": size,
            "n": n,
            "watermark": watermark,
            "provider": provider,
            "response_format": response_format,
            "extra_body": extra_body,
            "log": log,
        }

        if background_tasks is not None:
            background_tasks.add_task(self.async_generate_image_task, **task_kwargs)
            logger.info(f"图片任务 {request_id} 已加入后台队列")
            return request_id, None

        try:
            logger.info(f"图片任务 {request_id} 正在同步执行...")
            result = await self._run_image_generation(
                prompt=cleaned_prompt,
                size=size,
                n=n,
                watermark=watermark,
                provider=provider,
                response_format=response_format,
                extra_body=extra_body,
            )
        except Exception as exc:
            await UsageService(self.db).update_request_result_by_request_id(
                request_id=request_id,
                status=AIGenerateStatus.FAILED,
                error_msg=str(exc),
            )
            raise

        await UsageService(self.db).update_image_output_by_request_id(
            request_id=request_id,
            image_url=result,
        )
        return request_id, result

    @staticmethod
    async def _run_image_generation(
            prompt: str,
            size: str,
            n: int,
            watermark: bool,
            provider: AIProvider,
            response_format: str,
            extra_body: dict | None = None,
    ) -> str:
        raw_image_url = await get_ai_nexus().generate_image(
            provider=provider,
            prompt=prompt,
            size=size,
            n=n,
            watermark=watermark,
            response_format=response_format,
            extra_body=extra_body,
        )

        return await AIImageService.download_and_store_image_url(raw_image_url)

    async def async_generate_image_task(
            self,
            request_id: str,
            prompt: str,
            size: str,
            n: int,
            watermark: bool,
            provider: AIProvider,
            response_format: str,
            log: AiNovelGenerateLog,
            extra_body: dict | None = None,
    ) -> str | None:
        """后台异步执行图片生成并更新结果"""
        logger.info(
            f"[{provider.name}] req:{request_id} 开始生成图片 提示词:{textwrap.shorten(prompt, width=32, placeholder='...')} size:{size}"
        )

        try:
            async with get_db_context() as db:
                result = await AIImageService(db=db)._run_image_generation(
                    prompt=prompt,
                    size=size,
                    n=n,
                    watermark=watermark,
                    provider=provider,
                    response_format=response_format,
                    extra_body=extra_body,
                )

                await UsageService(db).update_image_output_by_request_id(
                    request_id=request_id,
                    image_url=result,
                    status=AIGenerateStatus.SUCCESS,
                )
                logger.info(
                    f"[{provider.name}] req:{request_id} 图片生成结束 返回:{textwrap.shorten(result, width=48, placeholder='...')}")
                return result
        except Exception as exc:
            logger.error(f"[{provider.name}] req:{request_id} 图片生成异常 {exc}")
            async with get_db_context() as db:
                await UsageService(db).update_request_result_by_request_id(
                    request_id=request_id,
                    status=AIGenerateStatus.FAILED,
                    error_msg=str(exc),
                )
            return None

    @staticmethod
    async def download_and_store_image_url(image_url: str, file_type: str = "avatar") -> str:
        if not image_url or not image_url.strip():
            raise ValueError("图片地址不能为空")

        request_body = {
            "url": image_url.strip(),
            "type": file_type,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.post(settings.IMAGE_DOWNLOAD_URL, json=request_body)
                response.raise_for_status()
        except httpx.RequestError as exc:
            logger.error(f"图片转存请求失败: {exc}")
            raise RuntimeError("图片转存服务请求失败") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"图片转存响应异常: {exc.response.status_code} - {exc.response.text}")
            raise RuntimeError(f"图片转存失败: HTTP {exc.response.status_code}") from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            logger.error(f"图片转存返回非 JSON: {response.text}")
            raise RuntimeError("图片转存服务返回格式异常") from exc

        stored_url = (((response_data or {}).get("data") or {}).get("url") or "").strip()
        if response_data.get("code") != 200 or not stored_url:
            error_msg = response_data.get("msg") or "图片转存失败"
            logger.error(f"图片转存业务失败: {response_data}")
            raise RuntimeError(error_msg)

        return stored_url
