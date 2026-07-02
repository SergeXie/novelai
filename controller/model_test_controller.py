from fastapi import APIRouter, Depends
from typing import List, Optional
from pydantic import BaseModel

from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from service.model_test_service import get_model_test_service


# 定义请求和响应模型
class SingleModelTestRequest(BaseModel):
    """单个模型测试请求"""
    level: int  # 模型等级
    timeout: float = 60.0  # 超时时间（秒）


class ModelTestRequest(BaseModel):
    """批量模型测试请求"""
    levels: Optional[List[int]] = None  # 模型等级列表，为空则测试所有模型
    timeout: float = 60.0  # 超时时间（秒）


class ModelTestResponse(BaseModel):
    """单个模型测试响应"""
    level: int
    model_name: str
    provider: str
    status: str  # "success", "failed", "timeout"
    response_time: float  # 响应时间（秒）
    error_message: Optional[str] = None
    token_usage: Optional[dict] = None
    switched: bool = False  # 是否发生了自动切换
    original_model: Optional[str] = None  # 切换前的原始模型名


class ModelTestBatchResponse(BaseModel):
    """批量模型测试响应"""
    total: int
    success: int
    failed: int
    switched: int  # 自动切换次数
    results: List[ModelTestResponse]


modelTestController = APIRouter()


@modelTestController.post("/test/single", summary="测试单个模型连通性")
async def test_single_model(
    request: SingleModelTestRequest,
    db=Depends(get_db),
):
    """
    测试单个模型的连通性
    
    Args:
        request: 包含模型等级和超时时间
        
    Returns:
        模型测试结果
    """
    service = get_model_test_service(db)
    result = await service.test_level_with_failover(level=request.level, timeout=request.timeout)

    return ResponseUtil.success(data=result)


@modelTestController.post("/test/all", summary="测试所有模型连通性")
async def test_all_models(
    request: ModelTestRequest = ModelTestRequest(),
    db=Depends(get_db),
):
    """
    测试所有模型的连通性（获取 mc_ai_models 全部模型，按 level 分组，连通失败自动切换）

    Args:
        request: 包含超时时间，默认 60 秒

    Returns:
        所有模型的测试结果
    """
    service = get_model_test_service(db)
    results = await service.test_all_models(timeout=request.timeout)

    # 统计结果
    total = len(results)
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    switched_count = sum(1 for r in results if r.switched)

    batch_response = ModelTestBatchResponse(
        total=total,
        success=success,
        failed=failed,
        switched=switched_count,
        results=results
    )

    return ResponseUtil.success(data=batch_response)


@modelTestController.post("/test/batch", summary="批量测试指定模型连通性")
async def test_batch_models(
    request: ModelTestRequest,
    db=Depends(get_db),
):
    """
    批量测试指定等级模型的连通性
    
    Args:
        request: 测试请求，包含模型等级列表和超时时间
        
    Returns:
        指定模型的测试结果
    """
    service = get_model_test_service(db)
    
    if request.levels:
        # 测试指定等级的模型
        results = await service.test_models_by_levels(
            levels=request.levels,
            timeout=request.timeout
        )
    else:
        # 测试所有模型
        results = await service.test_all_models(timeout=request.timeout)
    
    # 统计结果
    total = len(results)
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    switched_count = sum(1 for r in results if r.switched)

    batch_response = ModelTestBatchResponse(
        total=total,
        success=success,
        failed=failed,
        switched=switched_count,
        results=results
    )

    return ResponseUtil.success(data=batch_response)


@modelTestController.get("/test/levels", summary="获取可测试的模型等级")
async def get_testable_levels(
    db=Depends(get_db),
):
    """
    获取所有可测试的模型等级
    
    Returns:
        可测试的模型等级列表
    """
    from dao.ai_model_dao import AiModelDAO
    
    model_dao = AiModelDAO(db)
    models = await model_dao.list_models(only_enabled=True)
    
    levels = [
        {
            "level": model.level,
            "model_name": model.model_name,
            "provider": model.provider
        }
        for model in models
    ]
    
    return ResponseUtil.success(data=levels)