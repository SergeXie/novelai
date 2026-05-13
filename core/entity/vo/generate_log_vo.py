from datetime import datetime

from pydantic import BaseModel, field_serializer


class BookDeconstructItemVO(BaseModel):
    requestId: str

    title: str

    status: int

    createdAt: datetime

    @field_serializer("createdAt")
    def serialize_created_at(self, value: datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")