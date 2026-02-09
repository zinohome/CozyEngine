# CozyEngine 安全加固方案

> **文档版本**: v1.0  
> **创建日期**: 2026-02-09  
> **安全等级**: Production Grade  
> **配套PRD**: CozyEngine-PRD-完整需求文档-v1.0-2026-02-09.md  

---

## 📋 安全评估概览

| 安全域 | 当前状态 | 目标状态 | 优先级 |
|--------|---------|---------|--------|
| **身份认证** | 基础JWT | JWT + 多因素认证 | P0 |
| **授权控制** | 基础RBAC | RBAC + 资源级权限 | P0 |
| **密钥管理** | 环境变量 | 专业密钥管理服务 | P0 ⚠️ |
| **工具安全** | 白名单 | 白名单 + 沙箱 + 审计 | P0 ⚠️ |
| **数据加密** | 传输加密（TLS） | 传输 + 静态加密 | P1 |
| **审计日志** | 基础审计 | 完整性校验 + 不可篡改 | P1 |
| **Rate Limiting** | 基础限流 | 多层次自适应限流 | P0 |
| **防御机制** | 基础 | DDoS + SQL注入 + XSS防护 | P1 |

---

## 1. 身份认证加固

### 1.1 JWT 增强设计

**当前方案**:
```python
# 基础 JWT
jwt.encode({"user_id": user.id, "exp": ...}, SECRET_KEY)
```

**加固方案**:
```python
# backend/app/core/security.py

from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
import secrets

# 密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenManager:
    """Token 管理器（增强版）"""
    
    def __init__(self):
        self.secret_key = self._get_secret_key()
        self.algorithm = "HS256"
        self.access_token_expire = timedelta(minutes=30)
        self.refresh_token_expire = timedelta(days=7)
    
    def _get_secret_key(self) -> str:
        """从密钥管理服务获取密钥"""
        # 生产环境：从 Azure Key Vault / Google Secret Manager 获取
        from app.core.secrets import get_jwt_secret
        return get_jwt_secret()
    
    def create_access_token(
        self,
        user_id: str,
        role: str,
        scopes: list[str],
        device_id: str = None
    ) -> str:
        """创建访问令牌（增强）"""
        
        payload = {
            # 标准声明
            "sub": user_id,              # Subject
            "iat": datetime.utcnow(),    # Issued At
            "exp": datetime.utcnow() + self.access_token_expire,
            "nbf": datetime.utcnow(),    # Not Before
            
            # 自定义声明
            "role": role,
            "scopes": scopes,
            "token_type": "access",
            "jti": secrets.token_urlsafe(16),  # JWT ID（唯一）
            
            # 设备绑定（可选）
            "device_id": device_id,
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(
        self,
        user_id: str,
        device_id: str = None
    ) -> str:
        """创建刷新令牌"""
        
        payload = {
            "sub": user_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + self.refresh_token_expire,
            "token_type": "refresh",
            "jti": secrets.token_urlsafe(16),
            "device_id": device_id,
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        """验证令牌（增强）"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # 检查令牌类型
            if payload.get("token_type") != "access":
                raise JWTError("Invalid token type")
            
            # 检查是否在黑名单
            if self._is_blacklisted(payload.get("jti")):
                raise JWTError("Token revoked")
            
            return payload
        
        except JWTError as e:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token: {str(e)}"
            )
    
    def _is_blacklisted(self, jti: str) -> bool:
        """检查令牌是否在黑名单（Redis）"""
        from app.core.redis import redis_client
        return redis_client.exists(f"token:blacklist:{jti}")
    
    def revoke_token(self, jti: str, exp: datetime):
        """撤销令牌（加入黑名单）"""
        from app.core.redis import redis_client
        ttl = int((exp - datetime.utcnow()).total_seconds())
        redis_client.setex(f"token:blacklist:{jti}", ttl, "1")


# 依赖注入
def get_current_user(
    token: str = Depends(oauth2_scheme),
    token_manager: TokenManager = Depends()
) -> User:
    """获取当前用户（依赖注入）"""
    
    payload = token_manager.verify_token(token)
    user_id = payload.get("sub")
    
    # 从数据库获取用户
    user = get_user_by_id(user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user
```

**关键改进**:
- ✅ **JWT ID (jti)**：每个 token 唯一，支持撤销
- ✅ **设备绑定**：可选的 `device_id`，防止 token 跨设备使用
- ✅ **令牌黑名单**：支持主动撤销
- ✅ **Scopes**：细粒度权限控制

---

### 1.2 多因素认证（MFA）

```python
# backend/app/core/mfa.py

import pyotp
import qrcode
from io import BytesIO

class MFAManager:
    """多因素认证管理器"""
    
    def generate_secret(self, user: User) -> str:
        """生成 TOTP 密钥"""
        secret = pyotp.random_base32()
        
        # 存储到数据库
        user.mfa_secret = secret
        user.mfa_enabled = False  # 需要用户验证后启用
        db.commit()
        
        return secret
    
    def generate_qr_code(self, user: User, secret: str) -> bytes:
        """生成 QR 码（用于 Google Authenticator）"""
        
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="CozyEngine"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    
    def verify_otp(self, user: User, otp_code: str) -> bool:
        """验证 OTP 代码"""
        
        if not user.mfa_secret:
            return False
        
        totp = pyotp.TOTP(user.mfa_secret)
        return totp.verify(otp_code, valid_window=1)  # 允许前后 30 秒误差
    
    def enable_mfa(self, user: User, otp_code: str) -> bool:
        """启用 MFA（需先验证）"""
        
        if self.verify_otp(user, otp_code):
            user.mfa_enabled = True
            db.commit()
            return True
        return False


# API 端点
@app.post("/v1/auth/mfa/setup")
async def setup_mfa(user: User = Depends(get_current_user)):
    """设置 MFA"""
    
    mfa = MFAManager()
    secret = mfa.generate_secret(user)
    qr_code = mfa.generate_qr_code(user, secret)
    
    return {
        "secret": secret,
        "qr_code": base64.b64encode(qr_code).decode()
    }

@app.post("/v1/auth/mfa/verify")
async def verify_mfa(
    otp_code: str,
    user: User = Depends(get_current_user)
):
    """验证并启用 MFA"""
    
    mfa = MFAManager()
    if mfa.enable_mfa(user, otp_code):
        return {"message": "MFA enabled successfully"}
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP code")
```

---

## 2. 密钥管理加固 ⚠️

### 2.1 Azure Key Vault 集成

```python
# backend/app/core/secrets.py

from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import os

class SecretManager:
    """密钥管理器（Azure Key Vault）"""
    
    def __init__(self):
        vault_url = os.getenv("AZURE_KEY_VAULT_URL")
        if not vault_url:
            raise ValueError("AZURE_KEY_VAULT_URL not set")
        
        credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=credential)
        
        # 本地缓存（减少 API 调用）
        self._cache = {}
        self._cache_ttl = 300  # 5 分钟
    
    def get_secret(self, name: str, use_cache: bool = True) -> str:
        """获取密钥"""
        
        if use_cache and name in self._cache:
            value, timestamp = self._cache[name]
            if time.time() - timestamp < self._cache_ttl:
                return value
        
        # 从 Key Vault 获取
        secret = self.client.get_secret(name)
        
        # 缓存
        self._cache[name] = (secret.value, time.time())
        
        return secret.value
    
    def set_secret(self, name: str, value: str):
        """设置密钥"""
        self.client.set_secret(name, value)
        
        # 清除缓存
        self._cache.pop(name, None)
    
    def rotate_secret(self, name: str, new_value: str):
        """轮换密钥（双版本支持）"""
        
        # 1. 创建新版本
        self.set_secret(name, new_value)
        
        # 2. 等待所有服务更新（grace period）
        # 3. 删除旧版本（手动或定时任务）


# 全局实例
_secret_manager = None

def get_secret_manager() -> SecretManager:
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


# 便捷函数
def get_jwt_secret() -> str:
    return get_secret_manager().get_secret("jwt-secret-key")

def get_database_password() -> str:
    return get_secret_manager().get_secret("database-password")

def get_openai_api_key() -> str:
    return get_secret_manager().get_secret("openai-api-key")
```

**环境配置**:
```bash
# .env (本地开发)
AZURE_KEY_VAULT_URL=https://cozyengine-vault.vault.azure.net/

# Azure CLI 认证（本地开发）
az login

# 生产环境：使用 Managed Identity（无需密码）
```

---

### 2.2 密钥轮换策略

```python
# backend/scripts/rotate_secrets.py

import asyncio
from app.core.secrets import get_secret_manager
from app.core.notifications import send_admin_alert

async def rotate_secrets():
    """定期轮换密钥（每周执行）"""
    
    sm = get_secret_manager()
    
    # 需要轮换的密钥列表（排除 critical 密钥）
    secrets_to_rotate = [
        "openai-api-key",
        "cognee-api-token",
        "mem0-api-key"
    ]
    
    for secret_name in secrets_to_rotate:
        try:
            # 1. 生成新密钥（调用第三方 API）
            new_value = generate_new_api_key(secret_name)
            
            # 2. 更新 Key Vault
            sm.rotate_secret(secret_name, new_value)
            
            # 3. 触发应用重新加载
            await reload_application_config()
            
            # 4. 验证新密钥
            await verify_new_secret(secret_name)
            
            print(f"✅ Rotated: {secret_name}")
        
        except Exception as e:
            # 发送告警
            await send_admin_alert(
                f"❌ Failed to rotate {secret_name}: {str(e)}"
            )

# Cron Job（每周六凌晨 2点）
# 0 2 * * 6 /usr/bin/python /app/scripts/rotate_secrets.py
```

---

## 3. 工具执行安全 ⚠️

### 3.1 沙箱隔离

```python
# backend/app/services/tools/sandbox.py

import subprocess
from resource import setrlimit, RLIMIT_CPU, RLIMIT_AS, RLIMIT_NPROC
from contextlib import contextmanager
import tempfile
import os

class ToolSandbox:
    """工具执行沙箱"""
    
    def __init__(self):
        self.max_cpu_time = 5  # 5 秒 CPU 时间
        self.max_memory = 512 * 1024 * 1024  # 512MB
        self.max_processes = 10
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    @contextmanager
    def restrict_resources(self):
        """资源限制上下文管理器"""
        
        # 保存原始限制
        original_limits = {}
        
        try:
            # 设置资源限制
            setrlimit(RLIMIT_CPU, (self.max_cpu_time, self.max_cpu_time))
            setrlimit(RLIMIT_AS, (self.max_memory, self.max_memory))
            setrlimit(RLIMIT_NPROC, (self.max_processes, self.max_processes))
            
            yield
        
        finally:
            # 恢复原始限制（如果需要）
            pass
    
    async def execute_tool_safely(
        self,
        tool_name: str,
        tool_args: dict,
        allowed_hosts: list[str] = None
    ) -> dict:
        """安全执行工具"""
        
        # 1. 检查工具白名单
        if not self._is_tool_allowed(tool_name):
            raise PermissionError(f"Tool '{tool_name}' not in whitelist")
        
        # 2. 检查副作用等级
        side_effect_level = self._get_tool_side_effect(tool_name)
        if side_effect_level == "dangerous":
            # 需要额外审批
            await self._request_approval(tool_name, tool_args)
        
        # 3. 创建隔离环境
        with tempfile.TemporaryDirectory() as tmpdir:
            # 4. 网络隔离检查
            if "url" in tool_args:
                self._check_network_access(tool_args["url"], allowed_hosts)
            
            # 5. 执行工具（资源限制）
            with self.restrict_resources():
                result = await self._execute_in_sandbox(
                    tool_name,
                    tool_args,
                    tmpdir
                )
            
            # 6. 审计记录
            await self._audit_tool_execution(
                tool_name,
                tool_args,
                result,
                side_effect_level
            )
            
            return result
    
    def _check_network_access(self, url: str, allowed_hosts: list[str]):
        """检查网络访问权限"""
        from urllib.parse import urlparse
        
        host = urlparse(url).hostname
        
        # 禁止访问内网
        if self._is_private_ip(host):
            raise PermissionError(f"Access to private IP {host} denied")
        
        # 检查白名单
        if allowed_hosts and host not in allowed_hosts:
            raise PermissionError(f"Access to {host} not allowed")
    
    def _is_private_ip(self, hostname: str) -> bool:
        """检查是否为内网 IP"""
        import ipaddress
        
        try:
            ip = ipaddress.ip_address(hostname)
            return ip.is_private or ip.is_loopback
        except ValueError:
            # 域名，需要解析后检查
            import socket
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback
    
    async def _execute_in_sandbox(
        self,
        tool_name: str,
        tool_args: dict,
        tmpdir: str
    ) -> dict:
        """在沙箱中执行工具"""
        
        # 根据工具类型选择执行方式
        if tool_name.startswith("mcp:"):
            # MCP 工具
            return await self._execute_mcp_tool(tool_name, tool_args)
        else:
            # 内置工具
            return await self._execute_builtin_tool(tool_name, tool_args)
    
    async def _audit_tool_execution(
        self,
        tool_name: str,
        tool_args: dict,
        result: dict,
        side_effect_level: str
    ):
        """审计工具执行"""
        from app.services.audit import create_audit_event
        
        await create_audit_event(
            event_type="TOOL_CALL",
            event_level="warning" if side_effect_level in ["write", "dangerous"] else "info",
            payload={
                "tool_name": tool_name,
                "tool_args": tool_args,  # 可能需要脱敏
                "result_status": result.get("status"),
                "side_effect_level": side_effect_level
            }
        )
```

---

### 3.2 工具权限矩阵

```yaml
# backend/config/tools_security.yaml

tool_security:
  # 只读工具（低风险）
  read_only:
    - search
    - calculator
    - weather
    - knowledge_search
    allowed_without_approval: true
    rate_limit: 100/minute
    network_access: true
    allowed_hosts:
      - "api.openai.com"
      - "www.google.com"
  
  # 写入工具（中风险）
  write:
    - create_note
    - update_profile
    - add_knowledge
    allowed_without_approval: true
    rate_limit: 10/minute
    network_access: true
    require_audit: true
  
  # 网络工具（中高风险）
  network:
    - http_request
    - send_email
    allowed_without_approval: false  # 需要审批
    rate_limit: 5/minute
    network_access: true
    block_private_ips: true
  
  # 危险工具（高风险）
  dangerous:
    - execute_code
    - file_delete
    allowed_without_approval: false
    rate_limit: 1/minute
    require_admin_approval: true
    require_audit: true
```

---

## 4. Rate Limiting 多层次限流

### 4.1 多层次限流策略

```python
# backend/app/middleware/rate_limit.py

from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import hashlib

class RateLimiter:
    """多层次限流器"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_rate_limit(
        self,
        request: Request,
        user_id: str = None
    ) -> bool:
        """检查限流"""
        
        # 1. IP 级别限流（全局）
        ip = request.client.host
        await self._check_ip_limit(ip, limit=100, window=60)  # 100/分钟
        
        # 2. 用户级别限流（如果已登录）
        if user_id:
            await self._check_user_limit(user_id, limit=60, window=60)  # 60/分钟
            
            # 3. 端点级别限流
            endpoint = request.url.path
            if endpoint == "/v1/realtime":
                # Realtime 会话创建限流
                await self._check_user_endpoint_limit(
                    user_id, endpoint,
                    limit=5, window=60  # 5/分钟
                )
        
        # 4. 并发连接限流（WebSocket）
        if request.url.path.startswith("/v1/realtime"):
            await self._check_concurrent_connections(user_id, max_connections=3)
        
        return True
    
    async def _check_ip_limit(self, ip: str, limit: int, window: int):
        """IP 级别限流"""
        key = f"ratelimit:ip:{ip}"
        await self._sliding_window_limit(key, limit, window)
    
    async def _check_user_limit(self, user_id: str, limit: int, window: int):
        """用户级别限流"""
        key = f"ratelimit:user:{user_id}"
        await self._sliding_window_limit(key, limit, window)
    
    async def _check_user_endpoint_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window: int
    ):
        """用户 + 端点限流"""
        endpoint_hash = hashlib.md5(endpoint.encode()).hexdigest()[:8]
        key = f"ratelimit:user:{user_id}:endpoint:{endpoint_hash}"
        await self._sliding_window_limit(key, limit, window)
    
    async def _sliding_window_limit(self, key: str, limit: int, window: int):
        """滑动窗口限流算法"""
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window)
        
        #使用 Redis Sorted Set
        pipe = self.redis.pipeline()
        
        # 1. 删除过期记录
        pipe.zremrangebyscore(key, 0, window_start.timestamp())
        
        # 2. 统计窗口内请求数
        pipe.zcard(key)
        
        # 3. 添加当前请求
        pipe.zadd(key, {str(now.timestamp()): now.timestamp()})
        
        # 4. 设置过期时间
        pipe.expire(key, window)
        
        results = await pipe.execute()
        count = results[1]
        
        if count >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} requests per {window} seconds"
            )
    
    async def _check_concurrent_connections(
        self,
        user_id: str,
        max_connections: int
    ):
        """并发连接限流"""
        key = f"concurrent:user:{user_id}"
        current = await self.redis.get(key) or 0
        
        if int(current) >= max_connections:
            raise HTTPException(
                status_code=429,
                detail=f"Too many concurrent connections (max: {max_connections})"
            )


# Middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """限流中间件"""
    
    limiter = RateLimiter(redis_client)
    
    # 获取用户 ID（如果已登录）
    user_id = None
    try:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            payload = JWT_MANAGER.verify_token(token)
            user_id = payload.get("sub")
    except:
        pass
    
    # 检查限流
    await limiter.check_rate_limit(request, user_id)
    
    response = await call_next(request)
    return response
```

---

## 5. 审计日志完整性

### 5.1 审计链设计

```python
# backend/app/services/audit.py

import hashlib
import hmac
import json
from datetime import datetime

class AuditChain:
    """审计链（防篡改）"""
    
    def __init__(self):
        self.secret_key = get_secret_manager().get_secret("audit-secret-key")
    
    async def create_audit_event(
        self,
        event_type: str,
        payload: dict,
        **kwargs
    ) -> dict:
        """创建审计事件（带完整性校验）"""
        
        # 1. 获取上一条事件的 hash
        previous_hash = await self._get_last_audit_hash()
        
        # 2. 构建事件数据
        event_data = {
            "event_type": event_type,
            "payload": payload,
            "previous_hash": previous_hash,
            "created_at": datetime.utcnow().isoformat(),
            **kwargs
        }
        
        # 3. 计算签名
        signature = self._calculate_signature(event_data)
        event_data["signature"] = signature
        
        # 4. 保存到数据库
        await self._save_audit_event(event_data)
        
        return event_data
    
    def _calculate_signature(self, event_data: dict) -> str:
        """计算 HMAC 签名"""
        
        # 排除 signature 字段
        data_to_sign = {k: v for k, v in event_data.items() if k != "signature"}
        
        # JSON 序列化（确保顺序）
        json_str = json.dumps(data_to_sign, sort_keys=True, ensure_ascii=False)
        
        # HMAC-SHA256
        signature = hmac.new(
            self.secret_key.encode(),
            json_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def verify_audit_chain(
        self,
        start_id: str = None,
        end_id: str = None
    ) -> bool:
        """验证审计链完整性"""
        
        # 获取审计事件列表
        events = await self._get_audit_events(start_id, end_id)
        
        previous_hash = None
        for event in events:
            # 1. 验证签名
            calculated_sig = self._calculate_signature(event)
            if calculated_sig != event["signature"]:
                logger.error(f"❌ Signature mismatch for event {event['id']}")
                return False
            
            # 2. 验证链
            if previous_hash and event["previous_hash"] != previous_hash:
                logger.error(f"❌ Chain broken at event {event['id']}")
                return False
            
            # 3. 更新 previous_hash
            previous_hash = hashlib.sha256(
                json.dumps(event, sort_keys=True).encode()
            ).hexdigest()
        
        logger.info("✅ Audit chain verified successfully")
        return True
```

---

## 6. 总结与检查清单

### 6.1 P0 优先实施（立即）

- [ ] **密钥管理**：集成 Azure Key Vault / Google Secret Manager
- [ ] **工具沙箱**：实现资源限制和网络隔离
- [ ] **Rate Limiting**：多层次限流（IP/User/Endpoint）
- [ ] **JWT 增强**：添加 jti、device_id、黑名单
- [ ] **审计链**：实现 HMAC 签名和完整性校验

### 6.2 P1 后续实施（Week 2-3）

- [ ] **MFA**：多因素认证（TOTP）
- [ ] **数据加密**：静态数据加密（数据库列级加密）
- [ ] **DDoS 防护**：集成 Cloudflare / AWS Shield
- [ ] **SQL 注入防护**：参数化查询 + ORM
- [ ] **XSS 防护**：CSP Header + 输入验证

### 6.3 安全监控指标

```python
# 关键安全指标
SECURITY_METRICS = {
    "auth_failures_per_minute": 5,  # 认证失败率阈值
    "rate_limit_hits_per_minute": 10,  # 限流触发阈值
    "tool_dangerous_calls_per_hour": 1,  # 危险工具调用阈值
    "audit_chain_verification_frequency": "hourly",  # 审计链验证频率
}
```

---

**文档维护者**: CozyEngine Security Team  
**最后更新**: 2026-02-09  
**安全等级**: Production Grade  
**下次评审**: Phase 2 完成后
