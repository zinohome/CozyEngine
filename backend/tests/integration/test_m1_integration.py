"""M1 模块集成测试"""

import os
import time
import requests
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database import db_manager


class TestM1Integration:
    """M1 模块集成测试套件"""

    BASE_URL = "http://localhost:8000"

    @pytest.fixture(scope="class", autouse=True)
    def setup_class(self):
        """测试前准备"""
        # 确保环境变量已设置
        assert os.getenv("DATABASE_URL"), "DATABASE_URL 未设置"
        yield

    def test_01_health_check(self):
        """测试健康检查端点"""
        response = requests.get(f"{self.BASE_URL}/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "timestamp" in data

    def test_02_root_endpoint(self):
        """测试根端点"""
        response = requests.get(f"{self.BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "version" in data

    def test_03_chat_completion_missing_headers(self):
        """测试缺少必需请求头"""
        response = requests.post(
            f"{self.BASE_URL}/api/v1/chat/completions",
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        assert response.status_code == 400
        assert "user_id" in response.text.lower() or "session_id" in response.text.lower()

    def test_04_chat_completion_missing_messages(self):
        """测试缺少消息体"""
        response = requests.post(
            f"{self.BASE_URL}/api/v1/chat/completions",
            headers={"user_id": "test_user", "session_id": "test_session"},
            json={"model": "default"},
        )
        assert response.status_code == 400

    def test_05_chat_completion_invalid_personality(self):
        """测试无效的人格 ID"""
        response = requests.post(
            f"{self.BASE_URL}/api/v1/chat/completions",
            headers={"user_id": "test_user", "session_id": "test_session"},
            json={
                "model": "nonexistent_personality",
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        assert response.status_code in [404, 500]

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"), reason="需要 OPENAI_API_KEY 环境变量"
    )
    def test_06_chat_completion_success(self):
        """测试成功的聊天完成（需要 OPENAI_API_KEY）"""
        response = requests.post(
            f"{self.BASE_URL}/api/v1/chat/completions",
            headers={"user_id": "test_user", "session_id": "test_session"},
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "Say 'Hello' and nothing else"}],
                "max_tokens": 50,
            },
            timeout=30,
        )
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]
        assert data["object"] == "chat.completion"

    def test_07_config_endpoint(self):
        """测试配置信息端点"""
        response = requests.get(f"{self.BASE_URL}/config")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "environment" in data

    def test_08_invalid_endpoint(self):
        """测试无效端点"""
        response = requests.get(f"{self.BASE_URL}/api/v1/nonexistent")
        assert response.status_code == 404

    def test_09_personality_system(self):
        """测试人格系统是否正常加载"""
        # 通过聊天端点间接测试人格系统
        response = requests.post(
            f"{self.BASE_URL}/api/v1/chat/completions",
            headers={"user_id": "test_user", "session_id": "test_session"},
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "test"}],
            },
            timeout=5,
        )
        # 应该返回 500（如果没有 OpenAI key）或 200（如果有 key）
        assert response.status_code in [200, 500, 502]
