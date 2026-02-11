"""审计事件服务"""

import uuid

from app.observability.logging import get_logger
from app.storage.database import db_manager
from app.storage.models import AuditEvent

logger = get_logger(__name__)


class AuditService:
    """审计服务 - 记录工具调用等关键操作"""

    @staticmethod
    def _normalize_uuid(value: str | None, namespace: uuid.UUID) -> uuid.UUID | None:
        if not value:
            return None
        try:
            return uuid.UUID(value)
        except ValueError:
            return uuid.uuid5(namespace, value)

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
        personality_id: str | None = None,
    ) -> str:
        """记录工具调用审计事件"""
        try:
            normalized_user_id = AuditService._normalize_uuid(user_id, uuid.NAMESPACE_DNS)
            normalized_session_id = AuditService._normalize_uuid(session_id, uuid.NAMESPACE_URL)

            async with db_manager.session() as session:
                audit_event = AuditEvent(
                    id=uuid.uuid4(),
                    event_type="tool_invocation",
                    user_id=normalized_user_id,
                    session_id=normalized_session_id,
                    request_id=request_id,
                    personality_id=personality_id,
                    payload={
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": result if success else {"error": result.get("error")},
                        "success": success,
                        "execution_time": execution_time,
                    },
                )

                session.add(audit_event)
                await session.commit()

                logger.debug(
                    "Tool invocation audit logged",
                    audit_id=audit_event.id,
                    tool_name=tool_name,
                    success=success,
                )

                return str(audit_event.id)

        except Exception as e:
            logger.error(
                "Failed to log tool invocation audit",
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            # 审计失败不应阻塞主流程
            return ""
