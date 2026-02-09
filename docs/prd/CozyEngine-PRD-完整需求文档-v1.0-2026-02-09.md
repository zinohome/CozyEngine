# CozyEngine 产品需求文档 (PRD)

> **文档版本**: v1.0  
> **创建日期**: 2026-02-09  
> **基于设计文档**: engine-v2 系列 (v2.0-2026-01-09)  
> **项目仓库**: CozyEngine  

---

## 一、项目概述

### 1.1 产品愿景

CozyEngine 是一个**人格化、插件式的聊天引擎**，从 CozyChat 项目中抽离并重构对话能力核心模块。它将提供：
- 独立部署的聊天引擎服务
- 可插拔的引擎架构（AI、工具、知识、画像、记忆）
- 标准化的 OpenAI Chat Completions API 兼容接口
- 为 CozyChat 前端提供稳定的业务 API

### 1.2 核心价值主张

**一句话定位**：把 CozyChat 的"对话能力"抽象成独立、可扩展、可观测的聊天引擎。

**关键特性**：
- 🔌 **可插拔架构** - AI 引擎、工具引擎、三大人格化引擎均可替换
- 🎭 **人格化驱动** - 基于人格配置（Prompt/工具/记忆策略/语音策略）支持多人格并存
- 🔄 **API 兼容性** - 对外兼容 OpenAI API，对内兼容 CozyChat 现有接口
- 👁️ **可观测性** - 结构化日志、指标、链路追踪，明确的错误码与降级策略
- ✅ **可测试性** - 分层可单测/集测，引擎可 Mock
- ⚡ **高性能** - 并行上下文组装、缓存分层、单机稳定支撑交互式 QPS

### 1.3 非目标（本期不做）

- ❌ **CozyChat 前端重写**（前端保持不变，优先后端引擎化）
- ❌ **多租户计费系统**（可预留字段，但不引入复杂计费）
- ❌ **大规模分布式调度**（先做单体可扩展，再演进）
- ❌ **全量向量知识平台统一**（允许接入 Cognee/Mem0/Memobase，但不强制单一。详见"插件化设计"章节）
- ❌ **Realtime 前端实现**（后端实现 Realtime API，前端由 CozyChat 项目负责）

---

## 二、业务需求

### 2.1 用户角色

| 角色 | 职责 | 权限 |
|------|------|------|
| **普通用户（User）** | 使用聊天服务 | 访问自己的会话、消息、人格配置 |
| **管理员（Admin）** | 系统运维管理 | 人格重载、工具发现、配置查看（脱敏）、审计查询 |
| **插件开发者** | 开发引擎插件 | 按引擎接口规范开发、注册插件 |

### 2.2 核心业务场景

#### 场景 1：标准对话流程（非流式）
**流程**：
1. 用户通过 OpenAI 兼容 API 发起对话请求
2. 系统进行鉴权、会话校验、人格加载、模型选择
3. 并行获取：知识检索 + 用户画像 + 会话记忆
4. 基于人格配置选择可用工具，生成 tools schema
5. 调用 AI 引擎生成回复（支持工具调用循环）
6. 保存消息、异步更新记忆和画像
7. 返回 OpenAI 兼容响应

**关键指标**：
- P50 延迟：< 500ms（不含模型生成时间）
- 降级率：< 5%

#### 场景 2：流式对话（SSE）
**流程**：
1-4. 同非流式准备阶段
5. AI 引擎 SSE 流式输出；遇到 tool_calls 进入工具调用循环
6. 过程中增量保存，最终落库
7. SSE 结束帧（finish_reason）

**关键指标**：
- 首 Token 延迟：< 300ms
- SSE 连接稳定性：99.5%

#### 场景 3：人格化对话增强
**需求**：
- 系统基于用户画像调整回复风格
- 检索相关知识库优化专业回答
- 利用会话记忆保持上下文连贯性

**实现**：
- 三大人格化引擎并行调用（Knowledge/UserProfile/ChatMemory）
- 超时控制（0.3-0.8s 可配置）
- 单引擎失败不影响主回答（降级策略）

#### 场景 4：工具调用
**需求**：
- 支持内置工具 + MCP 协议工具
- 工具调用符合 OpenAI tools 规范
- 有限迭代防止死循环

**约束**：
- 工具必须在人格白名单内
- 工具声明副作用等级（read-only/write/network/dangerous）
- 最大迭代次数可配置（默认 10）
- 每次工具调用记录审计事件

#### 场景 5：多人格管理
**需求**：
- 支持多个 AI 人格配置并存
- 人格配置包括：system prompt、模型选择、工具白名单、记忆策略、语音策略
- 支持人格热更新（受控，管理员权限）

#### 场景 6：语音交互（STT + TTS）
**需求**：
- 用户可以通过语音与 AI 对话
- 支持录音上传转文字（离线场景）
- 支持实时语音转文字（边说边转，在线场景）
- AI 回复可以转换成语音播放

**流程（离线模式）**：
1. 用户录制完成后上传音频文件
2. 系统通过 STT HTTP API 转换为文字
3. 文字进入标准对话流程（场景 1/2）
4. AI 文字回复通过 TTS HTTP API 生成语音
5. 返回音频文件给用户播放

**流程（在线模式/高性能）**：
1. 用户建立 WebSocket STT 连接
2. 边说边发送音频流，实时接收转录文本
3. 转录完成后进入对话流程
4. AI 回复通过 SSE TTS 流式生成音频
5. 边生成边播放，降低首字节延迟

**关键指标**：
- STT 准确率：> 95%（中文普通话）
- STT WebSocket TTFR：< 200ms
- TTS SSE TTFB：< 500ms
- 音频质量：清晰、自然、无明显机械感

#### 场景 7：Realtime 双向语音对话（CozyEngine 2.0 核心特性）
**需求**：
- 支持实时双向语音对话（类似电话通话）
- 用户可以打断 AI 说话（interrupt）
- 支持在语音对话中调用工具
- 支持语音 + 文本混合模式

**流程**：
1. 用户创建 Realtime 会话（WebSocket 连接）
2. 系统发送 `session.created` 事件
3. 用户发送音频流（`input_audio_buffer.append`）
4. 系统实时转录并理解输入
5. 用户触发生成（`response.create`）或自动触发（VAD）
6. 系统生成音频响应（`response.audio.delta` 增量返回）
7. 用户可以随时打断（`response.cancel`）
8. 如需调用工具，系统发送 `function_call_arguments` 事件
9. 会话结束或超时自动关闭

**关键指标**：
- 端到端延迟：< 300ms
- 打断响应延迟：< 100ms
- 会话稳定性：99%
- 支持工具调用：是
- 最大会话时长：1 小时（可配置）

**约束**：
- v1.0 使用 WebSocket 协议
- WebRTC 接口预留但不强制实现
- 前端由 CozyChat 项目负责
- 后端专注于 API 与会话管理

### 2.3 API 需求

#### OpenAI 兼容 API（核心）

**`POST /v1/chat/completions`**

请求字段：
```json
{
  "model": "gpt-4",
  "messages": [...],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 2000,
  "tools": [...],
  
  // CozyEngine 扩展字段（命名空间：cozy.*）
  "cozy": {
    "personality_id": "assistant-v1",
    "session_id": "uuid",
    "use_personalization": true,
    "allowed_tools": ["weather", "search"]
  }
}
```

响应（非流式）：
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  }
}
```

响应（流式 SSE）：
```
data: {"choices":[{"delta":{"content":"你好"}}]}
data: {"choices":[{"delta":{"content":"！"}}]}
data: {"choices":[{"finish_reason":"stop"}]}
data: [DONE]
```

#### CozyChat 兼容 API（业务型）

**会话管理**：
- `POST /v1/chat/sessions` - 创建会话
- `GET /v1/chat/sessions` - 会话列表
- `GET /v1/chat/sessions/{id}/messages` - 消息历史
- `DELETE /v1/chat/sessions/{id}` - 删除会话（软删）

**人格管理**：
- `GET /v1/personalities` - 列出人格
- `POST /v1/personalities/reload` - 热更新（管理员）

**工具管理**：
- `GET /v1/tools` - 列出工具
- `POST /v1/tools/refresh` - 触发 MCP 重新发现（管理员）

**语音 API（Voice Engine）**：

> CozyEngine 2.0 采用高性能协议（WebSocket/SSE）为主，HTTP POST 向下兼容

**STT (语音转文字)**：

```python
# 主方案：WebSocket 流式（实时转录）
WebSocket /v1/audio/stt/stream

# 客户端发送（二进制音频流）
<binary_audio_data>

# 服务端返回（JSON 事件流）
{"type": "transcript", "text": "你好", "is_partial": true, "timestamp": 1.2}
{"type": "transcript", "text": "你好，这是", "is_partial": true, "timestamp": 2.1}
{"type": "transcript_final", "text": "你好，这是完整的句子", "is_partial": false}
{"type": "done"}

# 兼容方案：HTTP POST（录音上传）
POST /v1/audio/stt
Content-Type: multipart/form-data

{
  "file": <audio_file>,  # 音频文件
  "language": "zh-CN",   # 可选
  "model": "whisper-1"   # 可选
}

# 响应
{
  "text": "你好，这是转录的文字",
  "language": "zh-CN",
  "duration": 3.5,
  "confidence": 0.95
}
```

**TTS (文字转语音)**：

```python
# 主方案：SSE 流式（边生成边播放）
POST /v1/audio/tts/stream
Content-Type: application/json
Accept: text/event-stream

{
  "input": "这是一段很长的文本...",
  "voice": "alloy",
  "model": "tts-1",
  "stream": true
}

# 响应（SSE 音频流）
data: {"type":"audio_chunk","data":"<base64_audio>","chunk_id":1}
data: {"type":"audio_chunk","data":"<base64_audio>","chunk_id":2}
data: {"type":"done"}

# 兼容方案：HTTP POST（完整生成）
POST /v1/audio/tts
Content-Type: application/json

{
  "input": "你好，欢迎使用 CozyEngine！",
  "voice": "alloy",
  "model": "tts-1",
  "response_format": "mp3",
  "speed": 1.0
}

# 响应
Content-Type: audio/mpeg
<binary_audio_data>
```

**Realtime (实时双向语音对话)**：

```python
# WebSocket 双向通信（v1.0 新增）
WebSocket /v1/realtime
Query: ?model=gpt-4o-realtime-preview&voice=alloy

# 客户端 → 服务端（发送音频/控制事件）
{
  "type": "input_audio_buffer.append",
  "audio": "<base64_audio>"
}

{
  "type": "response.create",
  "response": {
    "modalities": ["audio", "text"],
    "instructions": "你是一个友好的AI助手...",
    "tools": [...]
  }
}

# 服务端 → 客户端（接收响应事件）
{
  "type": "session.created",
  "session": {...}
}

{
  "type": "response.audio.delta",
  "delta": "<base64_audio>",
  "item_id": "item_xxx"
}

{
  "type": "response.audio.done",
  "item_id": "item_xxx"
}

{
  "type": "response.done",
  "response": {...}
}

# WebRTC 数据通道（可选，未来支持）
POST /v1/realtime/webrtc/session
# 创建 WebRTC 会话，返回 SDP offer
# 后续通过 WebRTC DataChannel 传输音频（更低延迟）
```

#### 错误响应规范
```json
{
  "error": {
    "code": "ENGINE_TIMEOUT",
    "message": "AI 引擎响应超时",
    "request_id": "req-xxx",
    "details": {...}  // 可选，生产环境可关闭
  }
}
```

错误码分类：
- `AUTH_*` - 认证/鉴权错误
- `VALIDATION_*` - 参数校验错误
- `RESOURCE_*` - 资源不存在/无权限
- `ENGINE_*` - 引擎调用失败/超时/限流
- `STORAGE_*` - 数据库/缓存错误
- `TOOL_*` - 工具调用失败/越权

---

## 三、技术架构需求

### 3.1 总体分层架构

```
┌─────────────────────────────────────────────┐
│         API 层 (FastAPI)                     │
│  - OpenAI 兼容 API                           │
│  - CozyChat 兼容 API                         │
│  - 鉴权、限流、性能中间件                      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         编排层 (Orchestrator)                │
│  - 请求准备、阶段调度                         │
│  - 不承载业务规则                            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         上下文层 (Context Service)           │
│  - 人格/会话/用户画像/知识/记忆组装           │
│  - Token 预算管理                            │
│  - 意图分析                                  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         引擎层 (Engines - 插件化)            │
│  ┌─────────┬─────────┬─────────┬─────────┐ │
│  │AI Engine│Tools Eng│Knowledge│UserProf.│ │
│  │(OpenAI/ │(MCP/内置│(Cognee) │(Memobase│ │
│  │Ollama)  │工具)    │         │)        │ │
│  └─────────┴─────────┴─────────┴─────────┘ │
│  ┌─────────┬─────────┐                     │
│  │ChatMemry│Voice Eng│                     │
│  │(Mem0)   │(STT/TTS)│                     │
│  └─────────┴─────────┘                     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         数据层 (Storage)                     │
│  - PostgreSQL (会话/消息/用户/审计)          │
│  - Redis (缓存/队列)                         │
│  - VectorDB (可选，按引擎需求)                │
└─────────────────────────────────────────────┘
```

### 3.2 核心技术组件

#### 3.2.1 编排器 (Orchestrator)

**职责**（只做阶段调度）：
1. **准备阶段**：鉴权、会话校验、人格选择、模型选择、参数规范化
2. **上下文阶段**：调用 ContextService 构建 ContextBundle
3. **工具阶段**：选择允许工具并生成 tools schema
4. **生成阶段**：调用 AI Engine（流式/非流式），处理工具调用循环
5. **落库/回写阶段**：保存消息、异步写入记忆、更新画像

**约束**：
- 不做具体实现细节（SQL、prompt 拼接、工具实现等）
- 单文件建议 < 400 行

#### 3.2.2 上下文服务 (Context Service)

**输入**：
- user_id, session_id, current_message
- personality_config（人格配置）
- max_tokens（上下文预算）

**输出 (ContextBundle)**：
```python
{
  "system_prompts": "...",           # 人格提示词 + 画像摘要
  "recent_messages": [...],          # 最近 N 条消息
  "summarized_history": "...",       # 历史摘要（可选）
  "retrieved_knowledge": [...],      # 知识检索结果
  "retrieved_memories": [...],       # 记忆检索结果
  "user_profile": {...},             # 画像结果
  "token_budget": {...},             # Token 使用明细
  "metadata": {                      # 观测数据
    "enabled_engines": [],
    "cache_hits": [],
    "degraded": false,
    "degrade_reasons": []
  }
}
```

**核心要求**：
- **并行调用**：Knowledge/UserProfile/ChatMemory 三引擎并行
- **超时控制**：每个引擎独立超时（0.3-0.8s 可配置）
- **降级策略**：单引擎失败返回空结果，不影响主回答
- **Token 预算**：优先级：人格 prompt > 最近消息 > 画像/记忆/知识 > 摘要

#### 3.2.3 引擎系统（插件化）

**引擎类型**：

| 引擎类型 | 职责 | 示例实现 |
|---------|------|---------|
| **AI Engine** | 聊天生成 | OpenAI, Ollama, LM Studio |
| **Tools Engine** | 工具调用 | MCP 协议工具, 内置工具 |
| **Knowledge Engine** | 知识检索/写入 | Cognee |
| **UserProfile Engine** | 画像获取/更新 | Memobase |
| **ChatMemory Engine** | 会话记忆 | Mem0 |
| **Voice Engine** | STT/TTS/Realtime | OpenAI, 腾讯云 |

**引擎接口规范（所有引擎 MUST）**：
```python
class BaseEngine:
    def initialize(self) -> None:
        """初始化连接/客户端；允许幂等"""
        
    def health_check(self) -> bool:
        """快速健康检查；不得执行重操作"""
        
    def close(self) -> None:
        """释放资源；允许幂等"""
```

**AI Engine 接口**：
```python
class AIEngine:
    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        **params
    ) -> ChatCompletion:
        """非流式生成"""
        
    def chat_stream(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        **params
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """流式生成（SSE chunk）"""
        
    @property
    def supports_tools(self) -> bool:
        """是否支持 tools/tool_calls"""
        
    @property
    def supports_vision(self) -> bool:
        """是否支持图像"""
```

**Knowledge Engine 接口**：
```python
class KnowledgeEngine:
    def search_knowledge(
        self,
        query: str,
        dataset_names: List[str],
        top_k: int = 5
    ) -> List[KnowledgeResult]:
        """知识检索"""
        
    def add_knowledge(
        self,
        content: str,
        dataset_name: str,
        metadata: dict
    ) -> str:
        """知识写入，返回 knowledge_id"""
```

**UserProfile Engine 接口**：
```python
class UserProfileEngine:
    def get_profile(
        self,
        user_id: str,
        max_token_size: int = 500
    ) -> ProfileResult:
        """获取用户画像"""
        
    def update_profile(
        self,
        user_id: str,
        messages: List[Message]
    ) -> bool:
        """更新画像"""
```

```

**Voice Engine 接口（STT/TTS/Realtime）**：

> CozyEngine 2.0 采用高性能协议优先策略，保持传统 HTTP 向下兼容

```python
from typing import AsyncGenerator, Optional, Union
from enum import Enum

class AudioFormat(Enum):
    """音频格式"""
    MP3 = "mp3"
    WAV = "wav"
    OPUS = "opus"
    AAC = "aac"
    PCM16 = "pcm16"  # 16-bit PCM
    WEBM = "webm"

class VoiceEngine:
    """Voice Engine 基类 - 支持 STT/TTS/Realtime"""
    
    # ===== STT (Speech-to-Text) =====
    
    # 方案 1: WebSocket 流式 STT（主方案，高性能）
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        sample_rate: int = 16000,
        **kwargs
    ) -> AsyncGenerator[dict, None]:
        """WebSocket 流式语音转文字
        
        Args:
            audio_stream: 音频流（字节流）
            language: 语言代码（如 "zh-CN"）
            sample_rate: 采样率
            
        Yields:
            {
                "type": "transcript",
                "text": str,              # 转录文本
                "is_partial": bool,      # 是否为部分结果
                "is_final": bool,        # 是否为最终结果
                "confidence": float,     # 置信度 0-1
                "timestamp": float,      # 时间戳
                "word_timestamps": []    # 可选，单词级时间戳
            }
        """
        pass
    
    # 方案 2: HTTP POST 同步 STT（兼容方案）
    async def transcribe(
        self,
        audio_file: bytes,
        language: Optional[str] = None,
        audio_format: AudioFormat = AudioFormat.MP3,
        **kwargs
    ) -> dict:
        """HTTP POST 同步语音转文字（向下兼容）
        
        Returns:
            {
                "text": str,
                "language": str,
                "duration": float,
                "confidence": float
            }
        """
        pass
    
    # ===== TTS (Text-to-Speech) =====
    
    # 方案 1: SSE 流式 TTS（主方案，高性能）
    async def speak_stream(
        self,
        text: str,
        voice: str = "alloy",
        audio_format: AudioFormat = AudioFormat.PCM16,
        speed: float = 1.0,
        **kwargs
    ) -> AsyncGenerator[bytes, None]:
        """SSE 流式文字转语音
        
        Args:
            text: 待转换文本
            voice: 音色（如 "alloy", "echo", "nova"）
            audio_format: 音频格式
            speed: 语速 0.25-4.0
            
        Yields:
            bytes: 音频流（二进制数据块）
        """
        pass
    
    # 方案 2: HTTP POST 同步 TTS（兼容方案）
    async def speak(
        self,
        text: str,
        voice: str = "alloy",
        audio_format: AudioFormat = AudioFormat.MP3,
        speed: float = 1.0,
        **kwargs
    ) -> bytes:
        """HTTP POST 同步文字转语音（向下兼容）
        
        Returns:
            bytes: 完整音频文件
        """
        pass
    
    # ===== Realtime 双向语音对话 =====
    
    async def create_realtime_session(
        self,
        personality_id: str,
        tools: Optional[List[dict]] = None,
        voice: str = "alloy",
        turn_detection: Optional[dict] = None,
        **kwargs
    ) -> "RealtimeSession":
        """创建 Realtime 会话
        
        Args:
            personality_id: 人格 ID
            tools: 可用工具列表
            voice: 音色
            turn_detection: 轮次检测配置（VAD）
            
        Returns:
            RealtimeSession: 实时会话对象
        """
        pass
    
    # ===== 能力声明 =====
    
    @property
    def supports_stream_stt(self) -> bool:
        """是否支持流式 STT"""
        return False
    
    @property
    def supports_stream_tts(self) -> bool:
        """是否支持流式 TTS"""
        return False
    
    @property
    def supports_realtime(self) -> bool:
        """是否支持 Realtime 双向对话"""
        return False
    
    @property
    def supports_webrtc(self) -> bool:
        """是否支持 WebRTC（可选，性能更优）"""
        return False


class RealtimeSession:
    """Realtime 会话对象
    
    支持两种传输协议：
    - WebSocket（必选）：双向事件流
    - WebRTC（可选）：更低延迟的音频传输
    """
    
    async def connect(self, protocol: str = "websocket") -> None:
        """建立连接
        
        Args:
            protocol: "websocket" | "webrtc"
        """
        pass
    
    async def send_audio(self, audio_chunk: bytes) -> None:
        """发送音频数据（用户语音）"""
        pass
    
    async def send_text(self, text: str) -> None:
        """发送文本（可选，用于文本输入）"""
        pass
    
    async def send_event(self, event: dict) -> None:
        """发送控制事件
        
        示例事件：
        - {"type": "response.create"}  # 触发生成
        - {"type": "response.cancel"}  # 取消生成
        - {"type": "input_audio_buffer.commit"}  # 提交音频缓冲
        - {"type": "input_audio_buffer.clear"}  # 清空音频缓冲
        """
        pass
    
    async def receive_events(self) -> AsyncGenerator[dict, None]:
        """接收事件流
        
        Yields:
            {
                "type": str,           # 事件类型
                "event_id": str,       # 事件 ID
                "data": dict,          # 事件数据
                "timestamp": float
            }
            
        事件类型包括：
        - "session.created"
        - "conversation.item.created"
        - "response.audio.delta"      # 音频增量
        - "response.audio.done"
        - "response.text.delta"       # 文本增量（调试用）
        - "response.text.done"
        - "response.function_call_arguments.delta"
        - "response.function_call_arguments.done"
        - "response.done"
        - "rate_limits.updated"
        - "error"
        """
        pass
    
    async def close(self) -> None:
        """关闭会话"""
        pass
    
    @property
    def is_active(self) -> bool:
        """会话是否活跃"""
        pass
    
    @property
    def protocol(self) -> str:
        """当前使用的协议"""
        pass
```

**Voice Engine 配置示例**：

```yaml
# backend/config/engines.yaml
engines:
  voice:
    provider: openai  # openai | tencent | azure | custom
    
    # 基础配置
    model: gpt-4o-realtime-preview
    api_key: ${OPENAI_API_KEY}
    base_url: ${OPENAI_BASE_URL}
    
    # STT 配置
    stt:
      primary_protocol: websocket  # websocket | http
      fallback_protocol: http
      websocket:
        endpoint: wss://api.openai.com/v1/audio/stt/stream
        sample_rate: 16000
        chunk_size: 4096
        language: auto
        timeout: 30
      http:
        endpoint: /v1/audio/stt
        max_file_size: 25MB
        supported_formats: [mp3, wav, m4a, webm]
        timeout: 30
    
    # TTS 配置
    tts:
      primary_protocol: sse  # sse | http
      fallback_protocol: http
      sse:
        endpoint: /v1/audio/tts/stream
        chunk_text_length: 200  # 每 200 字生成一个音频块
        prefetch_chunks: 2
        timeout: 30
      http:
        endpoint: /v1/audio/tts
        max_text_length: 4096
        cache_enabled: true
        cache_ttl: 3600
        timeout: 30
      voices:
        - alloy
        - echo
        - fable
        - onyx
        - nova
        - shimmer
    
    # Realtime 配置（v1.0 新增）
    realtime:
      enabled: true
      protocols:
        websocket:
          enabled: true
          endpoint: wss://api.openai.com/v1/realtime
          max_session_duration: 3600  # 1小时
          ping_interval: 30
        webrtc:
          enabled: false  # 可选，未来支持
          signaling_server: wss://signaling.example.com
          stun_servers:
            - stun:stun.l.google.com:19302
          turn_servers: []  # 如需 NAT 穿透
      
      # 模式配置
      modalities: [audio, text]  # 支持的模态
      voice: alloy
      temperature: 0.8
max_response_output_tokens: 4096
      
      # VAD (Voice Activity Detection) 配置
      turn_detection:
        type: server_vad
        threshold: 0.5
        prefix_padding_ms: 300
        silence_duration_ms: 500
      
      # 工具调用配置
      tool_choice: auto
      parallel_tool_calls: true
```

**API 端点设计**：

```python
# ===== STT API =====

# 主方案：WebSocket 流式
WebSocket /v1/audio/stt/stream
# 客户端发送: 音频二进制流
# 服务端返回: JSON 事件流（partial/final 转录结果）

# 兼容方案：HTTP POST
POST /v1/audio/stt
Content-Type: multipart/form-data
# 请求体: {"file": <audio>, "language": "zh-CN"}
# 响应: {"text": "...", "language": "zh-CN", "duration": 3.5}


# ===== TTS API =====

# 主方案：SSE 流式
POST /v1/audio/tts/stream
Content-Type: application/json
Accept: text/event-stream
# 请求: {"input": "...", "voice": "alloy", "stream": true}
# 响应: SSE 音频流

# 兼容方案：HTTP POST
POST /v1/audio/tts
Content-Type: application/json
# 请求: {"input": "...", "voice": "alloy"}
# 响应: 二进制音频文件


# ===== Realtime API =====

# WebSocket 双向通信
WebSocket /v1/realtime
# 双向事件流（JSON）
# 客户端 → 服务端: audio/text/control events
# 服务端 → 客户端: response events (audio/text/function_call)

# WebRTC 会话（可选，未来支持）
POST /v1/realtime/webrtc/session
# 创建 WebRTC 会话，返回 SDP offer
# 后续通过 WebRTC PeerConnection 传输音频
```

**插件系统设计**：

插件类型：
- **内置插件（builtin）**：随 CozyEngine 发布，默认启用
- **外置插件（package）**：以 Python 包形式安装，通过 entry-points 加载
- **远程插件（remote service）**：引擎实现为远程服务客户端

配置驱动（`backend/config/engines.yaml`）：
```yaml
engines:
  ai:
    provider: openai  # openai | ollama | lm_studio
    model: gpt-4
    base_url: https://api.openai.com/v1
    timeout: 30
    
  knowledge:
    provider: cognee
    api_url: http://localhost:8000
    timeout: 0.5
    
  userprofile:
    provider: memobase
    project_url: http://localhost:3000
    timeout: 0.3
    
  chatmemory:
    provider: mem0
    api_url: http://localhost:8080
    timeout: 0.4
    async_write: true
    
  tools:
    provider: mcp
    mcp_servers:
      - name: filesystem
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem"]
```

**插件注册与工厂模式**：
- **Registry（注册表）**：记录 provider → engine_class 映射
- **Factory（工厂）**：从配置创建 engine 实例
- **Pool（池/缓存）**：对无业务态的 engine/client 进行缓存复用

插件版本与兼容：
- 每个引擎接口都有 `api_version`（例如 `"v1"`）
- 插件必须声明支持的 `api_version`，不匹配则拒绝加载

### 3.3 数据存储需求

#### 3.3.1 数据分层
- **事务数据（PostgreSQL）**：用户、会话、消息、权限、审计事件
- **缓存与队列（Redis）**：热点缓存、限流状态、异步写入队列
- **向量/检索存储（可选）**：Knowledge/Memory 引擎自带存储

#### 3.3.2 核心数据表

**users 表**：
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',  -- user | admin
    status VARCHAR(20) DEFAULT 'active',  -- active | inactive
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**sessions 表**：
```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    personality_id VARCHAR(50) NOT NULL,
    title VARCHAR(200),
    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMP,
    deleted_at TIMESTAMP,  -- 软删
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**messages 表**：
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(20) NOT NULL,  -- system | user | assistant | tool
    content TEXT,
    message_metadata JSONB,  -- token_count, model, tool_calls, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**audit_events 表**（新增）：
```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(100),
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES sessions(id),
    personality_id VARCHAR(50),
    event_type VARCHAR(50),  -- TOOL_CALL | ENGINE_DEGRADED | AUTH_FAIL | ...
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 3.3.3 异步写入策略

ChatMemory / UserProfile 更新可异步：
- **必须可配置**：sync | async
- **必须可回压**：队列长度、批量大小、失败重试策略
- **必须可观测**：成功率、积压量、耗时

### 3.4 配置管理需求

#### 配置优先级
**YAML > 环境变量（Settings）> 代码默认值**

#### 配置拆分（命名空间）
- `app.yaml` - 应用名、环境、CORS、基础开关
- `api.yaml` - 路由前缀、OpenAI 兼容开关、SSE 参数
- `engines.yaml` - 各引擎 provider 与参数
- `context.yaml` - 上下文策略、token 预算、并行与超时
- `tools.yaml` - 工具白名单、MCP 服务发现配置
- `storage.yaml` - DB/Redis 配置（非密钥部分）
- `observability.yaml` - 日志/指标/追踪
- `security.yaml` - 鉴权策略、RBAC、审计开关

#### 环境变量（示例）
```bash
# 基础
APP_ENV=development
APP_SECRET_KEY=xxx
JWT_SECRET_KEY=xxx

# 数据库/缓存
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# AI
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OLLAMA_BASE_URL=http://localhost:11434

# 人格化引擎
COGNEE_API_URL=http://localhost:8000
COGNEE_API_TOKEN=xxx
MEMOBASE_PROJECT_URL=http://localhost:3000
MEMOBASE_API_KEY=xxx
MEM0_API_URL=http://localhost:8080
MEM0_API_KEY=xxx

# 可观测
SENTRY_DSN=https://...
SENTRY_ENABLE=true
```

#### 配置校验（启动时 MUST）
- 引擎 provider 是否存在
- 必需密钥是否缺失
- timeout/阈值是否合理
- 配置版本追踪（config_version）

---

## 四、非功能性需求

### 4.1 性能需求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| P50 延迟 | < 500ms | 不含模型生成时间 |
| P95 延迟 | < 1.5s | 包含降级场景 |
| P99 延迟 | < 3s | 极端场景 |
| 降级率 | < 5% | 三大引擎单引擎失败率 |
| SSE 首 Token | < 300ms | 流式对话首响应 |
| 并发 QPS | 50+ | 单机，交互式场景 |

**并行策略**：
- 上下文构建阶段：Knowledge/UserProfile/ChatMemory 并行
- 整体延迟 ≈ max(Tk, Tp, Tm)

**缓存分层**：
- **L1（进程内 TTLCache）**：毫秒级，适合人格配置、工具 schema
- **L2（Redis）**：跨进程共享，适合知识检索结果、用户画像摘要

**超时预算**：
- Knowledge: 0.5s
- UserProfile: 0.3s
- ChatMemory: 0.4s
- 超时后返回空结果并降级

### 4.2 可用性需求

| 指标 | 目标值 |
|------|--------|
| 服务可用性 | 99.5% |
| 降级可用性 | 100%（单引擎失败不影响主服务） |
| MTTR（平均修复时间） | < 10min |

**降级策略**：
- 单个引擎失败返回空结果
- 降级必须写入 `metadata.degraded = true`
- 降级必须写入 `metadata.degrade_reasons[]`
- 记录日志（warn）+ 指标计数

### 4.3 可观测性需求

#### 日志（必选）
**结构化 JSON 日志**，必须字段：
- `timestamp`, `level`, `request_id`
- `user_id?`, `session_id?`, `personality_id?`
- `latency_ms`, `route`, `status`
- 引擎调用：provider、耗时、是否降级、错误码

**隐私保护**：
- 默认不记录原文消息
- 如需记录必须有开关 + 脱敏策略
- Sentry/追踪不得上传 PII

#### 指标（建议）
- QPS / 延迟（P50/P95/P99）
- 引擎调用成功率/超时率/降级率
- SSE 连接数、平均持续时间
- 工具调用次数/失败率
- 队列积压量（异步写入）

#### 追踪（可选）
- request span
- context build span（并行子 span：knowledge/profile/memory）
- model generation span
- tool invocation span
- persistence span

### 4.4 安全性需求

#### 鉴权
- 默认：JWT Bearer Token
- 所有涉及 user/session/message 的接口都需鉴权
- 公开接口（`/health`, `/docs`）按环境受控

#### 授权（RBAC）
角色：
- `user` - 只能访问自己的数据
- `admin` - 可做运维级动作（人格重载、工具发现、配置查看）

规则（MUST）：
- session/messages 的读写必须校验 `session.user_id == current_user.id`
- 管理员动作必须审计（audit_events）

#### 工具权限
- 人格白名单（allowed_tools）
- 工具声明的副作用等级与服务策略匹配
- 运行时参数校验（schema）
- 工具执行必须落审计事件

#### 密钥管理
- 密钥只来自环境变量或密钥管理系统
- 不写入 YAML/代码/日志
- 所有请求日志必须脱敏

### 4.5 可测试性需求

#### 测试金字塔
- **单元测试（60%）**
  - 引擎接口适配层（mock 外部服务）
  - ContextService：token 预算、并行、降级、空结果协议
  - Orchestrator：阶段调度、工具循环边界
  
- **集成测试（30%）**
  - API → Orchestrator → Context → Engines
  - DB/Redis 读写一致性、事务与软删
  
- **端到端（10%）**
  - 登录 → 建会话 → 连续对话 → 工具调用 → SSE 流式

#### 必测场景清单
- ✅ 上下文并行：三引擎并行时总耗时≈max；单引擎超时不影响整体
- ✅ 降级可观测：降级时 metadata 与日志/指标均能反映
- ✅ 工具调用循环：工具成功/失败/多轮调用/达到最大迭代次数
- ✅ SSE 协议兼容：chunk 格式与 `[DONE]` 结尾；断线不导致资源泄漏
- ✅ 权限：用户只能访问自己的 session/messages；管理员能力受控

---

## 五、实施计划

### 5.1 总体策略

- **先"并行接管"，再"切流量"**：先在 CozyEngine 中跑通同等能力，再逐步把 CozyChat 前端切到新服务
- **保持兼容**：OpenAI 兼容 API 与 CozyChat 兼容 API 同时提供
- **主链路先行**：Orchestrator + ContextService（新）+ 三大人格化引擎优先稳定
- **旧系统受控退场**：旧 Memory API / legacy context 只作为兼容层，必须有移除计划

### 5.2 阶段划分

#### Phase 0：准备（1-2 天）
**目标**：
- 建立 CozyEngine 基础骨架
- 打通配置体系与基础中间件

**任务**：
- 在 CozyEngine 下建立 `backend/` 骨架与最小可运行 FastAPI
- 建立配置体系（YAML + env）
- 打通日志/追踪基础

**验收**：
- `GET /health` 正常
- `GET /v1/personalities` 能读取人格配置

#### Phase 1：核心聊天链路（3-5 天）
**目标**：
- 实现非流式对话核心流程

**任务**：
- 实现 v2 Orchestrator 主链路（非流式）
- 接入 AI Engine（先 OpenAI）
- 实现 `/v1/chat/completions`（非流式）
- 消息落库（session/messages）

**验收**：
- 非流式回复正确
- 会话/消息能查询

#### Phase 2：流式 + 工具（3-5 天）
**目标**：
- 支持 SSE 流式输出
- 支持工具调用

**任务**：
- 实现 SSE 流式输出
- 工具 schema 与工具调用循环
- MCP 工具发现（受控）

**验收**：
- 流式可用
- 工具可调用，最大迭代次数生效

#### Phase 3：人格化上下文（5-8 天）
**目标**：
- 实现三大人格化引擎并行调用

**任务**：
- 实现 ContextService：并行调用三大人格化引擎
- 实现 IntentAnalyzer：决定启用哪些引擎与参数
- 实现 token 预算与裁剪

**验收**：
- 三引擎并行、超时降级生效
- metadata 可观测（启用引擎、降级原因）

#### Phase 4：兼容层与切流量（3-7 天）
**目标**：
- CozyChat 前端可无感切换到 CozyEngine

**任务**：
- 补齐 CozyChat 兼容 API 最小集合
- 对比测试：新旧返回差异分析
- 灰度切换：按用户/租户/环境切流量

**验收**：
- CozyChat 前端可无感运行（或最小改动）

#### Phase 4.5：Voice Engine (STT/TTS/Realtime)（7-12 天）
**目标**：
- 实现高性能语音能力（CozyEngine 2.0 核心特性）

**任务（分阶段实施）**：

**阶段 1: STT 实现（2-3 天）**
- 实现 HTTP POST STT（兼容方案）
  - 音频文件上传与校验
  - 调用 OpenAI Whisper API
  - 结果缓存策略
- 实现 WebSocket 流式 STT（主方案）
  - WebSocket 连接管理
  - 音频流处理（chunk 接收）
  - 实时转录（partial/final 结果）
  - VAD (Voice Activity Detection) 集成（可选）

**阶段 2: TTS 实现（2-3 天）**
- 实现 HTTP POST TTS（兼容方案）
  - 文本转语音（同步）
  - 音频格式转换
  - 缓存策略（相同文本复用）
- 实现 SSE 流式 TTS（主方案）
  - 文本分块策略（200 字/块）
  - SSE 音频流输出
  - 预取优化（prefetch 2 chunks）

**阶段 3: Realtime 实现（3-6 天）**
- WebSocket 双向通信
  - 会话创建与管理
  - 音频输入缓冲（input_audio_buffer）
  - 事件驱动架构（接收/发送事件）
- Realtime 事件处理
  - 音频增量输出（response.audio.delta）
  - 文本增量输出（response.text.delta）
  - 工具调用事件（function_call_arguments）
  - 会话状态管理
- WebRTC 支持（可选，预留接口）
  - 信令服务器集成（预留）
  - SDP offer/answer 处理（预留）
  - 仅实现接口声明，实际可延后

**验收标准**：
- ✅ STT HTTP 可用（音频文件上传转文字）
- ✅ STT WebSocket 可用（实时流式转录）
- ✅ TTS HTTP 可用（文字生成音频文件）
- ✅ TTS SSE 可用（流式音频输出）
- ✅ Realtime WebSocket 可用（双向语音对话）
- ✅ Realtime 支持工具调用（function calling）
- ✅ 所有语音 API 可观测（日志/指标/错误）
- ✅ WebRTC 接口预留（`supports_webrtc = False`）

**技术风险评估**：
- WebSocket 连接管理（中等风险）→ 对策：使用 FastAPI WebSocket + 心跳机制
- 音频流处理（中等风险）→ 对策：参考 OpenAI Realtime 官方文档
- Realtime 事件复杂性（高风险）→ 对策：先实现核心事件，边缘事件可延后
- WebRTC 技术复杂度（高风险）→ 对策：v1.0 仅预留接口，不强制实现

**工作量估算**：
- STT（HTTP + WebSocket）：2-3 人天
- TTS（HTTP + SSE）：2-3 人天
- Realtime（WebSocket 事件驱动）：3-6 人天
- 测试与调优：1-2 人天
- **总计：8-14 人天（建议预留 10-12 天）**

#### Phase 5：退场与清理（持续）
**目标**：
- 移除旧系统冗余代码

**任务**：
- 标记 legacy API deprecated
- 删除旧记忆 API/旧 context builder

### 5.3 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 新旧行为不一致导致前端问题 | 高 | 对比测试 + 灰度 + 兼容层隔离 |
| 外部引擎不稳定 | 中 | 超时+降级 + 缓存 + 健康检查 + 熔断 |
| 配置复杂化 | 中 | 命名空间 + schema 校验 + config_version |
| 性能达不到目标 | 高 | 并行优化 + 缓存分层 + 性能测试 |

---

## 六、交付清单（Definition of Done）

### 6.1 功能交付
**核心对话能力**：
- ✅ OpenAI 兼容 `/v1/chat/completions`（流式/非流式）
- ✅ CozyChat 兼容 API（sessions/messages/personality/tools）
- ✅ 三大人格化引擎并行与降级
- ✅ 工具调用循环（有限迭代）
- ✅ 人格配置热更新（管理员）

**语音能力（CozyEngine 2.0 新增）**：
- ✅ STT (语音转文字)
  - HTTP POST 同步转录（兼容方案）
  - WebSocket 流式转录（主方案）
- ✅ TTS (文字转语音)
  - HTTP POST 同步生成（兼容方案）
  - SSE 流式生成（主方案）
- ✅ Realtime 双向语音对话
  - WebSocket 事件驱动架构
  - 音频增量输入/输出
  - 工具调用支持
  - WebRTC 接口预留（v1.0 不强制实现）

### 6.2 质量交付
**测试覆盖**：
- ✅ 关键链路单测/集测覆盖
- ✅ 端到端测试通过
- ✅ Voice Engine 测试
  - STT/TTS HTTP/WebSocket/SSE 协议测试
  - Realtime 会话创建/事件处理/断线重连测试
  - 音频格式转换测试

**性能指标**：
- ✅ 对话性能达标（P50/P95/P99）
- ✅ 降级率 < 5%
- ✅ Voice 性能达标
  - STT WebSocket TTFR (Time To First Result) < 200ms
  - TTS SSE TTFB (Time To First Byte) < 500ms
  - Realtime 端到端延迟 < 300ms

### 6.3 文档交付
- ✅ API 文档（OpenAPI/Swagger）
- ✅ 部署运行手册
- ✅ 插件开发指南
- ✅ 故障排查手册

### 6.4 可观测性交付
- ✅ 结构化日志可用
- ✅ 关键指标可追踪（QPS/延迟/降级率）
- ✅ 审计事件完整记录

---

## 七、技术约束与设计原则

### 7.1 设计约束（从 CozyChat 继承）

- **编排器模式已落地**：API 层保持轻薄，核心流程集中在编排层
- **异步 + 并行是核心**：上下文构建天然并行；流式输出使用 SSE
- **全局生命周期初始化**：人格注册表、工具工厂、LLM 引擎池等在应用启动时初始化
- **配置优先级明确**：YAML > 环境变量 > 代码默认值

### 7.2 架构决策记录（ADR 摘要）

- **ADR-001**：编排器模式作为唯一主入口，API 层不承载业务规则
- **ADR-002**：三大人格化引擎接口稳定化，并通过插件系统加载
- **ADR-003**：配置以 YAML 为主，环境变量为密钥/环境差异兜底
- **ADR-004**：默认 SSE 流式输出支持工具调用循环（有限迭代）

### 7.3 分层依赖规则（MUST）

- **API 层**只能依赖 orchestration/context/core 的接口，不得直接依赖具体引擎实现
- **编排层**依赖 context + engines（抽象接口）+ storage（抽象接口），不得依赖 FastAPI Request/Response
- **context 层**只能依赖 engines（抽象）与少量 core 结构；不得直接依赖数据库 ORM
- **engines 层**不得反向依赖 orchestration/context/api
- **storage 层**不得依赖 engines

### 7.4 代码质量约束

- 单文件建议 < 400 行
- 严格类型注解；公共接口必须有类型与清晰 docstring
- 异步优先：I/O（HTTP/DB/Redis）使用 async
- 结构化日志：必须包含 request_id/user_id/session_id/personality_id
- 禁止日志泄露密钥与 PII

---

## 八、术语表

| 术语 | 定义 |
|------|------|
| **User（用户）** | 鉴权主体，拥有会话与画像 |
| **Session（会话）** | 对话容器，绑定用户与人格 |
| **Message（消息）** | 对话单元，role ∈ {system,user,assistant,tool} |
| **Personality（人格）** | 驱动对话行为的配置集合 |
| **Orchestrator（编排器）** | 对话请求的"总导演"，只调度服务与引擎 |
| **Context Bundle（上下文包）** | 上下文层对外的统一输出结构 |
| **Engine（引擎）** | 对外提供稳定接口、对内可替换实现的能力模块 |
| **Plugin（插件）** | 引擎的一种加载形态 |
| **Knowledge** | 面向"知识回答"的检索/写入能力 |
| **UserProfile** | 面向"理解用户"的结构化/文本化画像能力 |
| **ChatMemory** | 面向"对话连贯"的短期/会话级记忆能力 |
| **OpenAI Compatible API** | 兼容 OpenAI Chat Completions 请求/响应结构 |
| **CozyChat Compatible API** | 为现有前端保留的业务接口 |

---

## 九、附录

### 9.1 参考文档

本 PRD 基于以下设计文档整理：
- `docs/engine-v2/INDEX-v2.0-2026-01-09.md` - 文档索引
- `docs/engine-v2/00-愿景与范围-v2.0-2026-01-09.md`
- `docs/engine-v2/01-现状分析-CozyChat后端-v2.0-2026-01-09.md`
- `docs/engine-v2/02-总体架构-v2.0-2026-01-09.md`
- `docs/engine-v2/03-核心概念与术语-v2.0-2026-01-09.md`
- `docs/engine-v2/04-目录结构与分层规范-v2.0-2026-01-09.md`
- `docs/engine-v2/05-插件系统设计-v2.0-2026-01-09.md`
- `docs/engine-v2/06-引擎接口规范-v2.0-2026-01-09.md`
- `docs/engine-v2/07-编排与上下文构建-v2.0-2026-01-09.md`
- `docs/engine-v2/08-API设计（OpenAI兼容+CozyChat兼容）-v2.0-2026-01-09.md`
- `docs/engine-v2/09-数据与存储设计-v2.0-2026-01-09.md`
- `docs/engine-v2/10-配置与环境变量-v2.0-2026-01-09.md`
- `docs/engine-v2/11-错误处理与可观测性-v2.0-2026-01-09.md`
- `docs/engine-v2/12-性能与缓存策略-v2.0-2026-01-09.md`
- `docs/engine-v2/13-测试策略-v2.0-2026-01-09.md`
- `docs/engine-v2/14-迁移与实施计划-v2.0-2026-01-09.md`
- `docs/engine-v2/15-部署与运行手册-v2.0-2026-01-09.md`
- `docs/engine-v2/16-安全与权限模型-v2.0-2026-01-09.md`
- `docs/engine-v2/17-插件开发指南-v2.0-2026-01-09.md`

参考实现：
- CozyChat 项目 - `/Users/zhangjun/CursorProjects/CozyChat`

### 9.2 目录结构

推荐的 CozyEngine 目录结构：
```
CozyEngine/
  backend/
    app/
      api/                 # API 层（OpenAI兼容/CozyChat兼容）
        v1/
          chat.py          # Chat Completions API
          sessions.py      # 会话管理 API
          personalities.py # 人格管理 API
          tools.py         # 工具管理 API
          audio.py         # 音频 API（可选）
      core/                # 领域核心
        personality.py     # 人格模型
        session.py         # 会话模型
        auth.py            # 权限模型
      orchestration/       # 编排层
        chat_orchestrator.py
      context/             # 上下文层
        context_service.py
        intent_analyzer.py
        token_budget.py
      engines/             # 引擎层（插件化）
        ai/
          base.py
          openai_engine.py
          ollama_engine.py
        tools/
          base.py
          mcp_engine.py
        knowledge/
          base.py
          cognee_engine.py
        userprofile/
          base.py
          memobase_engine.py
        chatmemory/
          base.py
          mem0_engine.py
        voice/
          base.py
      storage/             # 数据访问层
        database.py
        redis.py
        models.py
      middleware/          # 中间件
        auth.py
        rate_limit.py
        performance.py
      observability/       # 日志/指标/追踪
        logging.py
        metrics.py
        tracing.py
      utils/               # 工具库
    config/                # YAML 配置
      app.yaml
      api.yaml
      engines.yaml
      context.yaml
      tools.yaml
      storage.yaml
      observability.yaml
      security.yaml
    tests/                 # 单元/集成/端到端
      unit/
      integration/
      e2e/
    scripts/               # 运维脚本
    alembic/               # 数据库迁移
  docs/
    engine-v2/             # 设计文档
    adr/                   # 架构决策记录
    runbooks/              # 运维手册
  .cursorrules             # Cursor AI 规则
  README.md
```

---

**文档维护者**：CozyEngine Team  
**最后更新**：2026-02-09
