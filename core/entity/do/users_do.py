import enum
from datetime import datetime

from sqlalchemy import BigInteger, String, Enum, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column

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
    __tablename__ = "mc_users"

    pkId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, comment="唯一标识符")
    account: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="账户")
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, comment="昵称")
    avatar: Mapped[str] = mapped_column(String(64), nullable=False, comment="头像")

    password: Mapped[str] = mapped_column(String(128), nullable=False, comment="密码")
    onlineStatus: Mapped[OnlineStatus] = mapped_column(Enum(OnlineStatus), nullable=False,
                                                        default=OnlineStatus.OFFLINE, comment="在线状态")

    status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE,
                                                  comment="帐号状态")

    wechatOpenid: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        comment="微信开放平台openid"
    )

    wechatUnionid: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="微信unionid"
    )

    isBindWechat: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否绑定微信"
    )

    loginType: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="account",
        comment="登录方式 account/wechat"
    )

    lastLoginTime: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=True,
        comment="最后登录时间"
    )

    createTime: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(),
                                                  comment="创建时间")

    updateTime: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(),
                                                  onupdate=func.current_timestamp(), comment="更新时间")


class WechatLoginState(Base):
    __tablename__ = "mc_wechat_login_state"

    # 主键ID
    pkId: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )

    # 本次二维码唯一标识
    state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="二维码唯一state"
    )

    # waiting / success / register / expired
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="waiting",
        index=True,
        comment="状态"
    )

    # 微信身份信息（未注册时使用）
    openid: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="微信openid"
    )

    unionid: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="微信unionid"
    )

    nickname: Mapped[str] = mapped_column(String(64), nullable=True, comment="昵称")

    # 登录成功后给前端
    token: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="登录token"
    )

    # 用户ID
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        comment="用户ID"
    )

    # 创建时间
    createTime: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间"
    )

    # 过期时间（建议5分钟）
    expireTime: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="过期时间"
    )


