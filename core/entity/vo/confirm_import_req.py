from pydantic import BaseModel, Field
from typing import List

class ConfirmImportRequest(BaseModel):
    taskId: str = Field(..., description="预解析任务ID")
    bookName: str = Field(..., min_length=1, max_length=100, description="书名")
    selectedIndices: List[int] = Field(..., min_items=1, description="选中的章节索引列表")