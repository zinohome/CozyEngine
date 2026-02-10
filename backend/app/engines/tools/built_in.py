"""内置工具集合"""

import time
from datetime import datetime

from app.engines.tools import ToolDefinition, ToolInvocationResult, ToolSideEffect


class BuiltInTools:
    """内置工具集合（read-only 示例）"""

    @staticmethod
    def get_definitions() -> dict[str, ToolDefinition]:
        """获取所有内置工具定义"""
        return {
            "get_current_time": ToolDefinition(
                name="get_current_time",
                description="Get the current date and time",
                parameters={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "description": "Time format (iso, timestamp, human)",
                            "enum": ["iso", "timestamp", "human"],
                        }
                    },
                    "required": [],
                },
                side_effect=ToolSideEffect.READ_ONLY,
                requires_permission=False,
            ),
            "calculate": ToolDefinition(
                name="calculate",
                description="Perform basic arithmetic calculations",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate (e.g., '2 + 2', '10 * 5')",
                        }
                    },
                    "required": ["expression"],
                },
                side_effect=ToolSideEffect.READ_ONLY,
                requires_permission=False,
            ),
        }

    @staticmethod
    async def invoke(name: str, arguments: dict) -> ToolInvocationResult:
        """执行内置工具"""
        start_time = time.time()

        try:
            if name == "get_current_time":
                result = BuiltInTools._get_current_time(arguments.get("format", "human"))
            elif name == "calculate":
                result = BuiltInTools._calculate(arguments.get("expression", ""))
            else:
                return ToolInvocationResult(
                    success=False,
                    error=f"Unknown built-in tool: {name}",
                    execution_time=time.time() - start_time,
                )

            return ToolInvocationResult(
                success=True,
                result=result,
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            return ToolInvocationResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    @staticmethod
    def _get_current_time(format_type: str) -> str:
        """获取当前时间"""
        now = datetime.now()  # noqa: DTZ005

        if format_type == "iso":
            return now.isoformat()
        elif format_type == "timestamp":
            return str(int(now.timestamp()))
        else:  # human
            return now.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _calculate(expression: str) -> str:
        """执行简单计算（安全沙箱）"""
        # 安全检查：只允许数字、运算符、括号和空格
        allowed_chars = set("0123456789+-*/().  ")
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Invalid characters in expression")

        # 使用 eval 执行（已做安全检查）
        try:
            result = eval(expression)  # noqa: S307
            return str(result)
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}") from e
