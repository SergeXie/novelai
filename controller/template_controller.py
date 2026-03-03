from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.vo.template_vo import TemplateListResp
from service.template_service import TemplateService


templateController = APIRouter()


@templateController.get("/book/templateList", name="书籍作品类型节点模板列表")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
):
    """
    获取节点模板列表（仅返回 id + tpl_name）
    """
    templates = await TemplateService.list_templates(db)

    resp = [TemplateListResp.model_validate(t) for t in templates]

    return ResponseUtil.success(data=resp)