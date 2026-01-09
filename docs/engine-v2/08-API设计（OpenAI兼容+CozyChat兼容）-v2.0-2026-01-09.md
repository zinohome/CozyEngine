## 08. API 设计（OpenAI 兼容 + CozyChat 兼容）

> **文档版本**: v2.0  
> **更新日期**: 2026-01-09  


### 8.1 API 分区原则

- **OpenAI 兼容 API**：对外提供标准化接口，方便接入任意客户端/代理。
- **CozyChat 兼容 API**：服务现有前端；逐步收敛到 OpenAI 兼容 API + 少量业务 API。

### 8.2 OpenAI 兼容：Chat Completions

#### 8.2.1 `POST /v1/chat/completions`

**请求**（关键字段）：

- `model`: string
- `messages`: array[{role, content, name?, tool_calls?, ...}]
- `stream`: bool（默认 false）
- `temperature`, `max_tokens`, `top_p`（可选）
- `tools`: array（可选）

**扩展字段（CozyEngine 自定义，必须在命名空间内）**：

- `cozy.personality_id`: string（人格 ID）
- `cozy.session_id`: string（会话 ID）
- `cozy.use_personalization`: bool（是否启用三大人格化引擎）
- `cozy.allowed_tools`: list[string]（受控白名单）

**响应**：

- 非流式：标准 ChatCompletion 结构（choices[0].message.content）
- 流式：SSE，事件体遵循 OpenAI delta 格式

#### 8.2.2 SSE 事件约定

- `data: {choices:[{delta:{content? tool_calls?}, finish_reason?}]}`（兼容）
- `data: [DONE]`（结束）

要求：

- 必须携带 `request_id`（header 或 metadata）
- 必须记录 `usage`（若 provider 不返回，则至少返回 total_tokens=0 并标记 unknown）

### 8.3 CozyChat 兼容 API（建议保留的最小集合）

#### 会话

- `POST /v1/chat/sessions`：创建会话（绑定人格）
- `GET /v1/chat/sessions`：会话列表
- `GET /v1/chat/sessions/{id}/messages`：消息历史
- `DELETE /v1/chat/sessions/{id}`：删除会话（软删）

#### 人格

- `GET /v1/personalities`：列出人格
- `POST /v1/personalities/reload`：受控热更新（管理员）

#### 工具

- `GET /v1/tools`：列出工具
- `POST /v1/tools/refresh`：触发 MCP 重新发现（管理员）

#### 音频（可选）

- `POST /v1/audio/stt`
- `POST /v1/audio/tts`

### 8.4 错误响应规范（统一）

所有 API 错误必须返回统一结构：

- `error.code`：稳定错误码（例如 `AUTH_INVALID_TOKEN` / `ENGINE_TIMEOUT`）
- `error.message`：面向开发者的简短信息
- `error.request_id`：请求追踪 ID
- `error.details`：可选，调试字段（生产可关闭）

### 8.5 兼容性策略

- **不破坏 CozyChat 前端**：通过保留 CozyChat 兼容 API 作为过渡。
- **逐步收敛**：前端与客户端逐步改用 OpenAI 兼容 API，业务 API 仅保留“会话/人格/工具/音频”等必要能力。

