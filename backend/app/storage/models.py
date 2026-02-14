"""数据库 ORM 模型"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database import Base


class User(Base):
    """用户表"""

    __tablename__ = "users"

    # 主键
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # 基本信息
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 权限与状态
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # 元数据
    user_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="chk_user_role"),
        CheckConstraint(
            "status IN ('active', 'inactive', 'suspended')", name="chk_user_status"
        ),
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
        Index("idx_users_status", "status", postgresql_where=text("status = 'active'")),
        Index("idx_users_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
    )


class Session(Base):
    """会话表"""

    __tablename__ = "sessions"

    # 主键
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # 关联关系
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    personality_id: Mapped[str] = mapped_column(String(50), nullable=False)

    # 基本信息
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message_count: Mapped[int] = mapped_column(nullable=False, default=0)

    # 会话元数据
    session_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)  # 软删除

    __table_args__ = (
        CheckConstraint("message_count >= 0", name="chk_session_message_count"),
        Index(
            "idx_sessions_user_id",
            "user_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_sessions_personality_id", "personality_id"),
        Index(
            "idx_sessions_created_at", "created_at", postgresql_ops={"created_at": "DESC"}
        ),
        Index(
            "idx_sessions_user_personality",
            "user_id",
            "personality_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Message(Base):
    """消息表"""

    __tablename__ = "messages"

    # 主键
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # 关联关系
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # 基本信息
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 消息元数据
    message_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')", name="chk_message_role"
        ),
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_user_id", "user_id"),
        Index(
            "idx_messages_created_at", "created_at", postgresql_ops={"created_at": "DESC"}
        ),
        Index(
            "idx_messages_session_created",
            "session_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
    )


class AuditEvent(Base):
    """审计事件表"""

    __tablename__ = "audit_events"

    # 主键
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # 请求上下文
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    personality_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 事件信息
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        Index("idx_audit_request_id", "request_id"),
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_event_type", "event_type"),
        Index(
            "idx_audit_created_at", "created_at", postgresql_ops={"created_at": "DESC"}
        ),
    )
