"""测试日志脱敏"""

from app.utils.sanitize import sanitize_log_data, sanitize_pii


def test_sanitize_sensitive_keys():
    """测试敏感字段脱敏"""
    data = {
        "username": "alice",
        "password": "secret123",
        "api_key": "sk-abc123",
        "email": "alice@example.com",
    }

    sanitized = sanitize_log_data(data)

    assert sanitized["username"] == "alice"
    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["email"] == "alice@example.com"


def test_sanitize_nested_dict():
    """测试嵌套字典脱敏"""
    data = {
        "user": {
            "name": "alice",
            "credentials": {
                "password": "secret",
                "token": "abc123",
            }
        }
    }

    sanitized = sanitize_log_data(data)

    assert sanitized["user"]["name"] == "alice"
    assert sanitized["user"]["credentials"]["password"] == "***REDACTED***"
    assert sanitized["user"]["credentials"]["token"] == "***REDACTED***"


def test_sanitize_openai_key():
    """测试 OpenAI API key 脱敏"""
    data = {
        "config": "Using key: sk-proj-abc123def456ghi789jkl012mno345pqr678stu901"
    }

    sanitized = sanitize_log_data(data)

    assert sanitized["config"] == "***REDACTED***"


def test_sanitize_bearer_token():
    """测试 Bearer token 脱敏"""
    data = {
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    }

    sanitized = sanitize_log_data(data)

    assert sanitized["authorization"] == "***REDACTED***"


def test_sanitize_pii_phone():
    """测试手机号脱敏"""
    text = "请联系我：13812345678"
    sanitized = sanitize_pii(text)
    assert "138****5678" in sanitized


def test_sanitize_pii_email():
    """测试邮箱脱敏"""
    text = "发送到：alice@example.com"
    sanitized = sanitize_pii(text)
    assert "al***@example.com" in sanitized


def test_sanitize_list_values():
    """测试列表值脱敏"""
    data = {
        "users": [
            {"name": "alice", "password": "secret1"},
            {"name": "bob", "api_key": "sk-test123"},
        ]
    }

    sanitized = sanitize_log_data(data)

    assert sanitized["users"][0]["name"] == "alice"
    assert sanitized["users"][0]["password"] == "***REDACTED***"
    assert sanitized["users"][1]["api_key"] == "***REDACTED***"
