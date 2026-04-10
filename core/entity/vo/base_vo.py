from typing import Optional

from pydantic import BaseModel


class PageMeta(BaseModel):
    page: int
    pageSize: int
    total: int

class PageMetaExtra(PageMeta):

    category: Optional[str] = None