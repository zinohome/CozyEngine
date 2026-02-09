"""数据库连接与会话管理"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Load environment variables
load_dotenv(".env.dev")


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    pass


class DatabaseManager:
    """数据库管理器（单例）"""

    def __init__(self) -> None:
        self._engine = None
        self._session_factory = None

    def initialize(self, database_url: str | None = None) -> None:
        """初始化数据库连接"""
        if self._engine is not None:
            return

        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            msg = "DATABASE_URL not configured"
            raise ValueError(msg)

        # 确保使用 asyncpg 驱动
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        self._engine = create_async_engine(
            url,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
            pool_pre_ping=True,  # 连接池健康检查
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话上下文管理器"""
        if not self._session_factory:
            msg = "Database not initialized. Call initialize() first."
            raise RuntimeError(msg)

        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    async def get_session(self) -> AsyncSession:
        """获取数据库会话（用于依赖注入）"""
        if not self._session_factory:
            msg = "Database not initialized. Call initialize() first."
            raise RuntimeError(msg)

        return self._session_factory()

    @property
    def engine(self):
        """获取数据库引擎"""
        return self._engine


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取数据库会话"""
    async with db_manager.session() as session:
        yield session
