"""人格系统测试"""

import pytest
import tempfile
from pathlib import Path

from app.core.personalities.models import (
    Personality,
    PersonalityAI,
    PersonalityTools,
    PersonalityMemory,
    PersonalityRegistry,
    PersonalityLoader,
)


class TestPersonality:
    """Personality 数据类测试"""

    def test_personality_creation(self):
        """Test creating a Personality object"""
        personality = Personality(
            id="test",
            name="Test Personality",
            description="A test personality",
            system_prompt="You are a test assistant",
            ai=PersonalityAI(provider="openai", model="gpt-4"),
        )
        assert personality.id == "test"
        assert personality.name == "Test Personality"

    def test_personality_from_dict(self):
        """Test creating Personality from dictionary"""
        data = {
            "id": "test",
            "name": "Test",
            "description": "Test description",
            "system_prompt": "You are a test",
            "ai": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.5,
            },
            "tools": {"enabled": True, "allowed_tools": ["search"]},
            "memory": {"enabled": True, "recall_top_k": 10},
        }
        personality = Personality.from_dict(data)
        assert personality.id == "test"
        assert personality.ai.temperature == 0.5
        assert personality.tools.enabled is True
        assert personality.memory.recall_top_k == 10

    def test_personality_to_dict(self):
        """Test converting Personality to dictionary"""
        personality = Personality(
            id="test",
            name="Test",
            description="Test",
            system_prompt="You are a test",
            ai=PersonalityAI(provider="openai", model="gpt-4", temperature=0.5),
            tools=PersonalityTools(enabled=True, allowed_tools=["search"]),
            memory=PersonalityMemory(enabled=True, recall_top_k=10),
        )
        data = personality.to_dict()
        assert data["id"] == "test"
        assert data["ai"]["temperature"] == 0.5
        assert data["tools"]["enabled"] is True


class TestPersonalityRegistry:
    """PersonalityRegistry 注册表测试"""

    def test_register_personality(self):
        """Test registering a personality"""
        registry = PersonalityRegistry()
        personality = Personality(
            id="test",
            name="Test",
            description="Test",
            system_prompt="Test",
            ai=PersonalityAI(provider="openai", model="gpt-4"),
        )
        registry.register(personality)
        assert registry.get("test") == personality

    def test_get_personality(self):
        """Test getting a personality"""
        registry = PersonalityRegistry()
        personality = Personality(
            id="test",
            name="Test",
            description="Test",
            system_prompt="Test",
            ai=PersonalityAI(provider="openai", model="gpt-4"),
        )
        registry.register(personality)
        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.id == "test"

    def test_get_nonexistent_personality(self):
        """Test getting a personality that doesn't exist"""
        registry = PersonalityRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all_personalities(self):
        """Test listing all personalities"""
        registry = PersonalityRegistry()
        p1 = Personality(
            id="test1",
            name="Test 1",
            description="Test",
            system_prompt="Test",
            ai=PersonalityAI(provider="openai", model="gpt-4"),
        )
        p2 = Personality(
            id="test2",
            name="Test 2",
            description="Test",
            system_prompt="Test",
            ai=PersonalityAI(provider="openai", model="gpt-4"),
        )
        registry.register(p1)
        registry.register(p2)
        personalities = registry.list_all()
        assert len(personalities) == 2

    def test_exists(self):
        """Test checking if personality exists"""
        registry = PersonalityRegistry()
        personality = Personality(
            id="test",
            name="Test",
            description="Test",
            system_prompt="Test",
            ai=PersonalityAI(provider="openai", model="gpt-4"),
        )
        registry.register(personality)
        assert registry.exists("test") is True
        assert registry.exists("nonexistent") is False


class TestPersonalityLoader:
    """PersonalityLoader 加载器测试"""

    def test_load_personality_from_file(self):
        """Test loading personality from YAML file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test YAML file
            yaml_path = Path(tmpdir) / "test.yaml"
            yaml_path.write_text(
                """
id: test
name: Test Personality
description: A test personality
system_prompt: You are a test assistant
ai:
  provider: openai
  model: gpt-4
  temperature: 0.7
"""
            )

            loader = PersonalityLoader(tmpdir)
            registry = PersonalityRegistry()
            personality = loader.load_file(yaml_path, registry)
            assert personality.id == "test"
            assert personality.name == "Test Personality"
            assert registry.get("test") is not None

    def test_load_all_personalities(self):
        """Test loading all personalities from directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple test YAML files
            for i in range(2):
                yaml_path = Path(tmpdir) / f"test{i}.yaml"
                yaml_path.write_text(
                    f"""
id: test{i}
name: Test {i}
description: Test personality {i}
system_prompt: You are personality {i}
ai:
  provider: openai
  model: gpt-4
"""
                )

            loader = PersonalityLoader(tmpdir)
            registry = PersonalityRegistry()
            loader.load_all(registry)

            personalities = registry.list_all()
            assert len(personalities) == 2

    def test_load_from_nonexistent_directory(self):
        """Test loading from non-existent directory"""
        loader = PersonalityLoader("/nonexistent/directory")
        registry = PersonalityRegistry()
        # Should not raise, just log warning
        loader.load_all(registry)
        assert len(registry.list_all()) == 0
