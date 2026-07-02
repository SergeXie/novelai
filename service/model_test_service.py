import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider
from ai.ai_nexus import get_ai_nexus
from dao.ai_model_dao import AiModelDAO


@dataclass
class ModelTestResult:
    """模型测试结果"""
    level: int
    model_name: str
    provider: str
    status: str  # "success", "failed", "timeout"
    response_time: float  # 响应时间（秒）
    error_message: Optional[str] = None
    token_usage: Optional[Dict] = None
    switched: bool = False  # 是否发生了自动切换
    original_model: Optional[str] = None  # 切换前的原始模型名


class ModelTestService:
    """模型连通性测试服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_nexus = get_ai_nexus()

    async def _do_test(self, model_config, timeout: float) -> tuple:
        """
        执行单次模型调用测试

        Returns:
            (success: bool, response_time: float, result_or_error, token_usage: dict|None)
        """
        start_time = time.time()
        provider = AIProvider.parse(model_config.level)

        test_prompt = "回复p即可"
        system_prompt = "直接回复。"

        try:
            result = await asyncio.wait_for(
                self.ai_nexus.generate_novel_text(
                    provider=provider,
                    user_prompt=test_prompt,
                    system_prompt=system_prompt,
                    temperature=0.1,
                    max_tokens=50,
                    model_config=model_config,
                ),
                timeout=timeout
            )
            response_time = time.time() - start_time
            token_usage = None
            if result.usage:
                token_usage = {
                    "prompt_tokens": result.usage.prompt_tokens,
                    "completion_tokens": result.usage.completion_tokens,
                    "total_tokens": result.usage.total_tokens,
                }
            return True, round(response_time, 2), result, token_usage

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return False, round(response_time, 2), f"模型响应超时（{timeout}秒）", None

        except Exception as e:
            response_time = time.time() - start_time
            return False, round(response_time, 2), str(e), None

    async def test_single_model(self, level: int, timeout: float = 60.0) -> ModelTestResult:
        """
        测试单个模型的连通性（测试该 level 下 status=1 的启用模型）

        Args:
            level: 模型等级
            timeout: 超时时间（秒）

        Returns:
            ModelTestResult: 测试结果
        """
        model_dao = AiModelDAO(self.db)
        model_config = await model_dao.get_model_by_level(level)

        if not model_config:
            logger.warning(f"[模型测试] level={level} 未找到模型配置")
            return ModelTestResult(
                level=level,
                model_name="未知",
                provider="未知",
                status="failed",
                response_time=0,
                error_message=f"未找到等级为 {level} 的模型配置",
            )

        provider_name = AIProvider.parse(model_config.level).name
        logger.info(
            f"[模型测试] 开始测试 level={level} model={model_config.model_name} provider={provider_name}"
        )

        success, response_time, detail, token_usage = await self._do_test(model_config, timeout)

        if success:
            logger.info(
                f"[模型测试] level={level} model={model_config.model_name} "
                f"status=success response_time={response_time}s"
            )
            return ModelTestResult(
                level=model_config.level,
                model_name=model_config.model_name,
                provider=provider_name,
                status="success",
                response_time=response_time,
                token_usage=token_usage,
            )
        else:
            logger.warning(
                f"[模型测试] level={level} model={model_config.model_name} "
                f"status=failed response_time={response_time}s error={detail}"
            )
            return ModelTestResult(
                level=model_config.level,
                model_name=model_config.model_name,
                provider=provider_name,
                status="failed",
                response_time=response_time,
                error_message=str(detail),
            )

    async def test_level_with_failover(self, level: int, timeout: float = 60.0) -> ModelTestResult:
        """
        测试指定 level 的模型，连通失败时自动切换同 level 下的其他模型

        流程:
        1. 找到该 level 下 status=1 的启用模型，优先测试
        2. 若启用模型连通失败，按 weight 降序依次尝试同 level 下其他模型
        3. 第一个连通成功的模型会被返回，若全部失败则返回最后一个错误结果

        Args:
            level: 模型等级
            timeout: 超时时间（秒）

        Returns:
            ModelTestResult: 测试结果
        """
        model_dao = AiModelDAO(self.db)
        all_models = await model_dao.get_all_models_by_level(level)

        if not all_models:
            logger.warning(f"[模型测试] level={level} 未找到任何模型配置")
            return ModelTestResult(
                level=level,
                model_name="未知",
                provider="未知",
                status="failed",
                response_time=0,
                error_message=f"未找到等级为 {level} 的模型配置",
            )

        # 分离启用模型和禁用模型，启用模型排最前
        enabled = [m for m in all_models if m.status == 1]
        disabled = [m for m in all_models if m.status != 1]
        ordered = enabled + disabled

        original_model = enabled[0].model_name if enabled else ordered[0].model_name
        last_result = None

        for idx, model_config in enumerate(ordered):
            provider_name = AIProvider.parse(model_config.level).name
            switched = idx > 0

            if switched:
                logger.info(
                    f"[模型测试] level={level} 自动切换: {ordered[idx - 1].model_name} -> "
                    f"{model_config.model_name} (provider={provider_name})"
                )

            success, response_time, detail, token_usage = await self._do_test(model_config, timeout)

            if success:
                logger.info(
                    f"[模型测试] level={level} model={model_config.model_name} "
                    f"status=success response_time={response_time}s"
                    f"{' ( switched from ' + original_model + ')' if switched else ''}"
                )

                # 发生切换时，同步更新数据库 status
                if switched and enabled:
                    failed_model = enabled[0]
                    # 禁用原来连通失败的模型
                    await model_dao.update_model_status(model_id=failed_model.id, new_status=0)
                    # 启用当前连通成功的模型
                    await model_dao.update_model_status(model_id=model_config.id, new_status=1)
                    # 刷新内存缓存
                    await model_dao.refresh_models_cache()
                    logger.info(
                        f"[模型测试] level={level} 已切换启用模型: "
                        f"{failed_model.model_name}(0) -> {model_config.model_name}(1)"
                    )

                return ModelTestResult(
                    level=level,
                    model_name=model_config.model_name,
                    provider=provider_name,
                    status="success",
                    response_time=response_time,
                    token_usage=token_usage,
                    switched=switched,
                    original_model=original_model if switched else None,
                )
            else:
                logger.warning(
                    f"[模型测试] level={level} model={model_config.model_name} "
                    f"status=failed response_time={response_time}s error={detail}"
                )
                last_result = ModelTestResult(
                    level=level,
                    model_name=model_config.model_name,
                    provider=provider_name,
                    status="failed",
                    response_time=response_time,
                    error_message=str(detail),
                    switched=switched,
                    original_model=original_model if switched else None,
                )

        # 所有模型都失败
        logger.error(
            f"[模型测试] level={level} 全部 {len(ordered)} 个模型连通失败，"
            f"最后测试: {last_result.model_name}"
        )
        return last_result

    async def test_all_models(self, timeout: float = 60.0) -> List[ModelTestResult]:
        """
        测试所有模型的连通性（获取 mc_ai_models 全部模型，按 level 分组，连通失败自动切换）

        Args:
            timeout: 每个模型的超时时间（秒）

        Returns:
            List[ModelTestResult]: 每个 level 的测试结果
        """
        model_dao = AiModelDAO(self.db)
        all_models = await model_dao.list_models(only_enabled=False)

        if not all_models:
            logger.warning("[模型测试] 没有找到任何模型配置")
            return []

        # 按 level 分组，获取所有不同的 level
        levels = sorted(set(m.level for m in all_models))
        total_models = len(all_models)

        logger.info(
            f"[模型测试] 开始批量测试，共 {total_models} 个模型，{len(levels)} 个等级: {levels}"
        )

        # 并发测试每个 level（每个 level 内部有 failover 逻辑）
        tasks = [
            self.test_level_with_failover(level=lv, timeout=timeout)
            for lv in levels
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        test_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                test_results.append(ModelTestResult(
                    level=levels[i],
                    model_name="未知",
                    provider="未知",
                    status="failed",
                    response_time=0,
                    error_message=str(result),
                ))
            else:
                test_results.append(result)

        # 统计
        success_count = sum(1 for r in test_results if r.status == "success")
        failed_count = sum(1 for r in test_results if r.status == "failed")
        switched_count = sum(1 for r in test_results if r.switched)

        logger.info(
            f"[模型测试] 批量测试完成：共 {len(test_results)} 个等级，"
            f"成功 {success_count}，失败 {failed_count}，自动切换 {switched_count}"
        )

        return test_results

    async def test_models_by_levels(self, levels: List[int], timeout: float = 60.0) -> List[ModelTestResult]:
        """
        测试指定等级模型的连通性（带自动切换）

        Args:
            levels: 模型等级列表
            timeout: 每个模型的超时时间（秒）

        Returns:
            List[ModelTestResult]: 指定等级模型的测试结果
        """
        tasks = [
            self.test_level_with_failover(level=lv, timeout=timeout)
            for lv in levels
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        test_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                test_results.append(ModelTestResult(
                    level=levels[i],
                    model_name="未知",
                    provider="未知",
                    status="failed",
                    response_time=0,
                    error_message=str(result),
                ))
            else:
                test_results.append(result)

        return test_results


def get_model_test_service(db: AsyncSession) -> ModelTestService:
    """获取模型测试服务实例"""
    return ModelTestService(db)