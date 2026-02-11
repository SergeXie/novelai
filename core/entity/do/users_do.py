from sqlalchemy import BigInteger, String, Enum, DateTime, func, Float, Integer, DECIMAL, text
from sqlalchemy.orm import Mapped, mapped_column
import enum
from database.db_mysql import Base


class AccountStatus(enum.Enum):
    ACTIVE = "ACTIVE"         # 正常激活状态
    DISABLED = "DISABLED"     # 管理员或系统禁用
    PENDING = "PENDING"       # 待审核/待激活状态
    SUSPENDED = "SUSPENDED"   # 暂时冻结，比如违规
    DELETED = "DELETED"       # 用户主动或系统删除
    BANNED = "BANNED"         # 被封禁，不能恢复的那种


class OnlineStatus(enum.Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"


class User(Base):
    __tablename__ = "users"

    pkId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, comment="唯一标识符")
    account: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="账户")
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, comment="昵称")

    password: Mapped[str] = mapped_column(String(128), nullable=False, comment="密码")
    onlineStatus: Mapped[OnlineStatus] = mapped_column(Enum(OnlineStatus), nullable=False,
                                                        default=OnlineStatus.OFFLINE, comment="在线状态")
    createTime: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(),
                                                  comment="创建时间")

    updateTime: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(),
                                                  onupdate=func.current_timestamp(), comment="更新时间")


