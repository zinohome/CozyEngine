"""Tools Engine 基础实现"""

import time
from collections import defaultdict

from app.core.config.manager import get_config
from app.engines.tools import ToolDefinition, ToolInvocationResult, ToolsEngine
from app.engines.tools.built_in import BuiltInTools
from app.observability.logging import get_logger

logger = get_logger(__name__)


class BasicToolsEngine(ToolsEngine):
    """基础工具引擎实现"""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._rate_limit_tracker: dict[str, list[float]] = defaultdict(list)
        self._initialized = False

    async def initialize(self) -> None:
        """初始化引擎"""
        if self._initialized:
            return

        # 加载内置工具
        self._tools = BuiltInTools.get_definitions()

        logger.info("Tools engine initialized", tool_count=len(self._tools))
        self._initialized = True

    async def health_check(self) -> bool:
        """健康检查"""
        return self._initialized

    async def close(self) -> None:
        """关闭引擎"""
        self._tools.clear()
        self._rate_limit_tracker.clear()
        self._initialized = False

    def list_tools(self, allowed_tools: list[str] | None = None) -> list[ToolDefinition]:
        """列出可用工具"""
        if allowed_tools is None:
            return list(self._tools.values())

        return [self._tools[name] for name in allowed_tools if name in self._tools]

    def to_openai_tools(self, tool_names: list[str]) -> list[dict]:
        """将工具转换为 OpenAI tools schema"""
        tools = []
        for name in tool_names:
            if name in self._tools:
                tool_def = self._tools[name]
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_def.name,
                        "description": tool_def.description,
                        "parameters": tool_def.parameters,
                    },
                })

        return tools

    async def invoke(
        self,
        name: str,
        arguments: dict,
        context: dict | None = None,
    ) -> ToolInvocationResult:
        """执行工具"""
        # 1. 检查工具是否存在
        if name not in self._tools:
            return ToolInvocationResult(
                success=False,
                error=f"Tool not found: {name}",
            )

        tool_def = self._tools[name]

        # 2. 检查白名单
        if not self._check_whitelist(name):
            return ToolInvocationResult(
                success=False,
                error=f"Tool not in whitelist: {name}",
            )

        # 3. 检查权限
        if tool_def.requires_permission and not self._check_permission(name, context):
            return ToolInvocationResult(
                success=False,
                error=f"Permission denied for tool: {name}",
            )

        # 4. 检查速率限制
        if not self._check_rate_limit(name):
            return ToolInvocationResult(
                success=False,
                error=f"Rate limit exceeded for tool: {name}",
            )

        # 5. 执行工具
        logger.info(
            "Invoking tool",
            tool_name=name,
            side_effect=tool_def.side_effect.value,
        )

        try:
            result = await BuiltInTools.invoke(name, arguments)
            return result

        except Exception as e:
            logger.error(
                "Tool invocation failed",
                tool_name=name,
                error=str(e),
                exc_info=True,
            )
            return ToolInvocationResult(
                success=False,
                error=str(e),
            )

    def get_tool(self, name: str) -> ToolDefinition | None:
        """获取工具定义"""
        return self._tools.get(name)

    def _check_whitelist(self, tool_name: str) -> bool:
        """检查工具是否在白名单中"""
        try:
            config = get_config()
            tools_config = config.get("tools", {})
            whitelist_config = tools_config.get("whitelist", {})

            if not whitelist_config.get("enabled", True):
                return True

            mode = whitelist_config.get("mode", "strict")
            allowed_tools = whitelist_config.get("allowed_tools", [])

            if mode == "permissive" and not allowed_tools:
                return True

            return tool_name in allowed_tools

        except Exception:
            # 配置读取失败，默认允许（降级策略）
            return True

    def _check_permission(self, tool_name: str, context: dict | None) -> bool:  # noqa: ARG002
        """检查工具执行权限"""
        try:
            config = get_config()
            tools_config = config.get("tools", {})
            permissions_config = tools_config.get("permissions", {})

            if not permissions_config.get("enabled", True):
                return True

            # 简化实现：基于 side_effect 等级
            tool_def = self._tools.get(tool_name)
            if not tool_def:
                return False

            # 如果需要用户同意且是危险操作
            if permissions_config.get("require_user_consent", True):
                if tool_def.side_effect in ["dangerous", "write "]:
                    # TODO: 实现用户同意机制
                    return False

            return True

        except Exception:
            # 配置读取失败，默认拒绝（安全优先）
            return False

    def _check_rate_limit(self, tool_name: str) -> bool:
        """检查速率限制"""
        try:
            config = get_config()
            tools_config = config.get("tools", {})
            limits_config = tools_config.get("limits", {})

            max_calls_per_minute = limits_config.get("max_calls_per_minute", 10)

            # 清理 60 秒前的记录
            current_time = time.time()
            self._rate_limit_tracker[tool_name] = [
                t for t in self._rate_limit_tracker[tool_name]
                if current_time - t < 60
            ]

            # 检查限制
            if len(self._rate_limit_tracker[tool_name]) >= max_calls_per_minute:
                return False

            # 记录本次调用
            self._rate_limit_tracker[tool_name].append(current_time)
            return True

        except Exception:
            # 配置读取失败，默认允许（降级策略）
            return True
