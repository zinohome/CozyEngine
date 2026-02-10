"""审计事件服务"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.logging import get_logger
from app.storage.database import db_manager
from app.storage.models import AuditEvent

logger = get_logger(__name__)


class AuditService:
    """审计服务 - 记录工具调用等关键操作"""

    @staticmethod
    async def log_tool_invocation(
        user_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict,
        result: dict,
        success: bool,
        execution_time: float,
        request_id: str | None = None,
    ) -> str:
        """记录工具调用审计事件"""
        try:
            async with db_manager.session() as session:
                audit_event = AuditEvent(
                    id=str(uuid.uuid4()),
                    event_type="tool_invocation",
                    user_id=user_id,
                    session_id=session_id,
                    request_id=request_id,
                    resource_type="tool",
                    resource_id=tool_name,
                    action="invoke",
                    metadata={
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": result if success else {"error": result.get("error")},
                        "success": success,
                        "execution_time": execution_time,
                    },
                    created_at=datetime.now(),  # noqa: DTZ005
                )

                session.add(audit_event)
                await session.commit()

                logger.debug(
                    "Tool invocation audit logged",
                    audit_id=audit_event.id,
                    tool_name=tool_name,
                    success=success,
                )

                return audit_event.id

        except Exception as e:
            logger.error(
                "Failed to log tool invocation audit",
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            # 审计失败不应阻塞主流程
            return ""
