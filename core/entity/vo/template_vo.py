from pydantic import BaseModel, ConfigDict


class TemplateListResp(BaseModel):
    """
    节点模板列表响应
    """
    id: int
    template_id: str
    tpl_name: str
    color: str

    model_config = ConfigDict(from_attributes=True)