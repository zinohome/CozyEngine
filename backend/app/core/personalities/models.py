"""人格系统 - 模型、加载器、注册表"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PersonalityAI:
    """AI 配置"""

    provider: str  # openai, anthropic, ollama
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0


@dataclass
class PersonalityTools:
    """工具配置"""

    enabled: bool = False
    allowed_tools: list[str] = field(default_factory=list)


@dataclass
class PersonalityMemory:
    """记忆配置"""

    enabled: bool = False
    recall_top_k: int = 5


@dataclass
class Personality:
    """人格定义"""

    id: str
    name: str
    description: str
    system_prompt: str
    ai: PersonalityAI
    tools: PersonalityTools = field(default_factory=PersonalityTools)
    memory: PersonalityMemory = field(default_factory=PersonalityMemory)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Personality":
        """从字典创建 Personality"""
        try:
            ai_config = data.get("ai", {})
            ai = PersonalityAI(
                provider=ai_config.get("provider", "openai"),
                model=ai_config.get("model", "gpt-4"),
                temperature=ai_config.get("temperature", 0.7),
                max_tokens=ai_config.get("max_tokens", 2000),
                top_p=ai_config.get("top_p", 1.0),
            )

            tools_config = data.get("tools", {})
            tools = PersonalityTools(
                enabled=tools_config.get("enabled", False),
                allowed_tools=tools_config.get("allowed_tools", []),
            )

            memory_config = data.get("memory", {})
            memory = PersonalityMemory(
                enabled=memory_config.get("enabled", False),
                recall_top_k=memory_config.get("recall_top_k", 5),
            )

            return cls(
                id=data.get("id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                system_prompt=data.get("system_prompt", ""),
                ai=ai,
                tools=tools,
                memory=memory,
                metadata=data.get("metadata", {}),
            )
        except KeyError as e:
            msg = f"Missing required field in personality config: {e}"
            raise ValueError(msg) from e

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "ai": {
                "provider": self.ai.provider,
                "model": self.ai.model,
                "temperature": self.ai.temperature,
                "max_tokens": self.ai.max_tokens,
                "top_p": self.ai.top_p,
            },
            "tools": {
                "enabled": self.tools.enabled,
                "allowed_tools": self.tools.allowed_tools,
            },
            "memory": {
                "enabled": self.memory.enabled,
                "recall_top_k": self.memory.recall_top_k,
            },
            "metadata": self.metadata,
        }


class PersonalityRegistry:
    """人格注册表 - 管理所有人格配置"""

    def __init__(self):
        self._personalities: dict[str, Personality] = {}

    def register(self, personality: Personality) -> None:
        """注册人格"""
        self._personalities[personality.id] = personality
        logger.info(
            f"Personality registered: {personality.id}", personality_name=personality.name
        )

    def get(self, personality_id: str) -> Personality | None:
        """获取人格"""
        return self._personalities.get(personality_id)

    def list_all(self) -> list[Personality]:
        """列出所有人格"""
        return list(self._personalities.values())

    def exists(self, personality_id: str) -> bool:
        """检查人格是否存在"""
        return personality_id in self._personalities


class PersonalityLoader:
    """从 YAML 加载人格配置"""

    def __init__(self, personality_dir: str | Path):
        self.personality_dir = Path(personality_dir)
        if not self.personality_dir.exists():
            logger.warning(f"Personality directory not found: {self.personality_dir}")

    def load_all(self, registry: PersonalityRegistry) -> None:
        """加载目录中的所有人格"""
        if not self.personality_dir.exists():
            logger.warning(f"Personality directory not found: {self.personality_dir}")
            return

        yaml_files = sorted(self.personality_dir.glob("*.yaml"))
        if not yaml_files:
            logger.warning(f"No personality YAML files found in {self.personality_dir}")
            return

        for yaml_file in yaml_files:
            try:
                self.load_file(yaml_file, registry)
            except Exception as e:
                logger.error(
                    f"Failed to load personality from {yaml_file}: {e}",
                    personality_file=yaml_file.name,
                )
                raise

    def load_file(self, yaml_file: Path, registry: PersonalityRegistry) -> Personality:
        """从单个 YAML 文件加载人格"""
        with open(yaml_file) as f:
            data = yaml.safe_load(f)

        if not data:
            msg = f"Empty or invalid YAML file: {yaml_file}"
            raise ValueError(msg)

        try:
            personality = Personality.from_dict(data)
            registry.register(personality)
            return personality
        except ValueError as e:
            msg = f"Invalid personality config in {yaml_file}: {e}"
            raise ValueError(msg) from e


# 全局人格注册表
personality_registry = PersonalityRegistry()

def get_personality_registry() -> PersonalityRegistry:
    """获取全局人格注册表"""
    return personality_registry


def initialize_personality_registry() -> PersonalityRegistry:
    """初始化人格注册表 - 从配置目录加载所有人格"""
    import os

    personality_dir = os.getenv(
        "PERSONALITY_CONFIG_DIR",
        "config/personalities"
    )

    loader = PersonalityLoader(personality_dir)
    loader.load_all(personality_registry)

    total = len(personality_registry.list_all())
    logger.info(f"Personality registry initialized with {total} personalities")

    return personality_registry
