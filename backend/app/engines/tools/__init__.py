"""Tools Engine - 接口定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ToolSideEffect(str, Enum):
    """工具副作用等级"""

    READ_ONLY = "read_only"  # 只读，无副作用
    WRITE = "write"  # 写入数据
    NETWORK = "network"  # 网络请求
    DANGEROUS = "dangerous"  # 危险操作（删除、系统命令等）


@dataclass
class ToolDefinition:
    """工具定义"""

    name: str
    description: str
    parameters: dict  # OpenAI function parameters schema
    side_effect: ToolSideEffect = ToolSideEffect.READ_ONLY
    requires_permission: bool = True


@dataclass
class ToolInvocationResult:
    """工具调用结果"""

    success: bool
    result: str | dict | None = None
    error: str | None = None
    execution_time: float = 0.0


class ToolsEngine(ABC):
    """Tools Engine 基类"""

    @abstractmethod
    async def initialize(self) -> None:
        """初始化引擎"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭引擎"""
        pass

    @abstractmethod
    def list_tools(self, allowed_tools: list[str] | None = None) -> list[ToolDefinition]:
        """列出可用工具"""
        pass

    @abstractmethod
    def to_openai_tools(self, tool_names: list[str]) -> list[dict]:
        """将工具转换为 OpenAI tools schema"""
        pass

    @abstractmethod
    async def invoke(
        self,
        name: str,
        arguments: dict,
        context: dict | None = None,
    ) -> ToolInvocationResult:
        """执行工具"""
        pass

    @abstractmethod
    def get_tool(self, name: str) -> ToolDefinition | None:
        """获取工具定义"""
        pass
