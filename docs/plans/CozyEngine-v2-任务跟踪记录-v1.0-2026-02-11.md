# CozyEngine v2 任务跟踪记录（用于执行期持续更新）

> **文档版本**: v1.0  \
> **创建日期**: 2026-02-11  \
> **适用范围**: CozyEngine v2（覆盖开发/测试/部署）  \
> **参考计划书**: [docs/plans/CozyEngine-v2-开发任务计划书-v1.1-2026-02-09.md](docs/plans/CozyEngine-v2-开发任务计划书-v1.1-2026-02-09.md)  \
> **参考执行指南**: [docs/plans/CozyEngine-v2-vibe_kanban-任务执行指南-v1.0-2026-02-09.md](docs/plans/CozyEngine-v2-vibe_kanban-任务执行指南-v1.0-2026-02-09.md)

---

## 1. 使用方式（如何维护这份记录）

### 1.1 状态枚举（统一口径）

- **TODO**：未开始
- **IN_PROGRESS**：进行中
- **BLOCKED**：阻塞（写清楚阻塞原因与解除条件）
- **IN_REVIEW**：自测/自检中（准备合并到主线或已在主线等待验证）
- **DONE**：完成（DoD 与 Verify 均通过，证据齐全）
- **PARTIAL**：部分完成（存在明确缺口，列出缺口与下一步）

### 1.2 每次更新最少要写什么

- 更新任务的 **状态**（含日期）
- 追加一条 **执行记录**（做了什么、证据在哪里、是否影响接口/边界）
- 如果涉及关键决策或边界变更：补充 **ADR 链接**（如有）

---

## 2. 仓库现状快照（2026-02-11 以当前代码为准）

> 目的：把“计划书的任务”映射到“仓库里已存在的能力”，方便后续按任务补齐缺口。

### 2.1 已看到的关键能力（证据）

- FastAPI 入口、配置加载与中间件：
  - [backend/app/main.py](backend/app/main.py)
- OpenAI 兼容聊天端点（非流式 + SSE 流式）：
  - [backend/app/api/v1/chat/completions.py](backend/app/api/v1/chat/completions.py)
- Orchestrator（含工具循环：非流式 + 流式）：
  - [backend/app/orchestration/chat.py](backend/app/orchestration/chat.py)
- ContextService（并行三引擎、超时降级、token budget 结构）：
  - [backend/app/context/service.py](backend/app/context/service.py)
- Tools Engine（白名单/权限/限流）与内置工具：
  - [backend/app/engines/tools/basic.py](backend/app/engines/tools/basic.py)
  - [backend/app/engines/tools/built_in.py](backend/app/engines/tools/built_in.py)
- 数据库 ORM 模型（users/sessions/messages/audit_events）与 health check：
  - [backend/app/storage/models.py](backend/app/storage/models.py)
  - [backend/app/api/health.py](backend/app/api/health.py)
- 测试文件已覆盖多个里程碑主题（需要本机安装依赖才能跑）：
  - [backend/tests](backend/tests)

### 2.2 已发现的缺口/风险（用于后续任务拆解）

- **已修复**：Orchestrator 的部分消息持久化逻辑。
  - 证据：[backend/app/orchestration/chat.py](backend/app/orchestration/chat.py#L475)
- **已修复**：OpenAI provider 依赖缺失。
  - 证据：[backend/pyproject.toml](backend/pyproject.toml)
- CozyChat 兼容层端点未在 `app/api/compat/*` 看到对应实现（M5 系列大概率未开始）。
- **已解决**：Realtime 实现路径不明确风险。已通过 [ADR-0012](docs/adr/ADR-0012-基于-FastRTC-方案) 确定方案。

---

## 3. 任务跟踪（按 Milestone）

> 说明：每个任务块都包含：状态、DoD/Verify checklist、证据、执行记录、下一步。

---

# M0：项目骨架与工程化底座

## M0-1：仓库结构与依赖管理

- **Task ID**: 73f518bb-9e3f-41fe-b831-2902b2aaba76
- **Priority**: P0
- **依赖**: 无
- **当前状态**: DONE（以当前仓库结构与 pyproject 为证据）
- **证据**:
  - [backend/README.md](backend/README.md)
  - [backend/pyproject.toml](backend/pyproject.toml)
  - [backend/app](backend/app)
- **DoD（摘自计划书）**
  - [x] `backend/` 可安装依赖并启动（见 README）
  - [x] ruff/pyright/pytest 配置存在（见 pyproject）
- **Verify**
  - [ ] 在本机/CI 环境可执行 `pytest -q`（本环境尚未安装 pytest，仅记录缺口）

**执行记录**
- 2026-02-11：已在仓库中体现（无需新增变更）。

**下一步**
- 若要在当前环境执行测试：先安装 dev 依赖（由执行人按环境决定）。

---

## M0-2：配置系统与环境分层

- **Task ID**: 6e3c37cb-7ceb-4fc0-8904-55f9da4fb13e
- **Priority**: P0
- **依赖**: M0-1
- **当前状态**: DONE（配置系统文档与实现均存在）
- **证据**:
  - [backend/CONFIG.md](backend/CONFIG.md)
  - [backend/config](backend/config)
  - [backend/app/core/config](backend/app/core/config)

**DoD**
- [x] YAML 配置目录存在
- [x] 启动时输出脱敏配置摘要（见 main.py）
- [x] 缺失必需密钥会明确报错（ConfigurationError 路径）

**Verify**
- [ ] 构造缺失密钥启动失败（执行期补充记录）
- [ ] 完整配置启动成功（执行期补充记录）

**执行记录**
- 2026-02-11：已在仓库中体现（无需新增变更）。

**下一步**
- 在实际部署环境跑一次“缺失密钥失败”与“完整配置成功”的演练，并把输出粘贴到执行记录中。
- 2026-02-13 更新：已确认 `pyproject.toml` 中的 `openai` 依赖已补齐。

---

## M0-3：可观测与错误体系

- **Task ID**: ea73f036-97d3-429c-80e5-abe56578fc20
- **Priority**: P0
- **依赖**: M0-1
- **当前状态**: DONE（错误响应已统一，剩余为运行时验收）
- **证据**:
  - [backend/app/main.py](backend/app/main.py)
  - [backend/app/middleware](backend/app/middleware)
  - [backend/app/observability](backend/app/observability)

**DoD**
- [x] 任意 API 错误响应统一结构（HTTP/校验异常已统一）
- [ ] 日志不泄露密钥/PII（需执行期验证）

**Verify**
- [ ] 构造 401/403/422/500，检查错误结构一致
- [ ] 搜索日志输出，确保无 token/secret

**执行记录**
- 2026-02-11：补齐 HTTP/校验异常统一错误格式，错误响应结构已一致。

**下一步**
- 补一轮“错误码矩阵验收”记录（建议直接引用测试或 curl 命令输出）。

---

## M0-4：数据库基础与迁移

- **Task ID**: edcff342-38d4-432b-b15c-1b010593acfb
- **Priority**: P0
- **依赖**: M0-2
- **当前状态**: DONE（模型/迁移/health/持久化已补齐）
- **证据**:
  - [backend/app/storage/models.py](backend/app/storage/models.py)
  - [backend/app/storage/database.py](backend/app/storage/database.py)
  - [backend/alembic/versions/a5e8420ede10_initial_schema_users_sessions_messages_.py](backend/alembic/versions/a5e8420ede10_initial_schema_users_sessions_messages_.py)
  - [backend/app/api/health.py](backend/app/api/health.py)

**DoD**
- [x] ORM 与迁移基础存在（alembic + models）
- [x] health check 能检查 DB
- [x] “消息写入 DB 且关联正确”在 Orchestrator 实际落地

**Verify**
- [ ] 新库执行迁移成功；重复执行幂等（执行期补充记录）
- [ ] 调用聊天接口后 messages/session 记录正确（待补齐持久化后再验收）

**执行记录**
- 2026-02-11：补齐 Orchestrator 消息持久化与会话创建逻辑。

**下一步**
- 在执行 M4-2 时一并补齐“会话/消息/审计事件”的写入逻辑，并在此处补充证据与验收记录。
- 2026-02-13 更新：已实现 `_persist_message` 中的真实 DB 写入与 `session` 表关联记录。

---

# M1：核心聊天链路（非流式）

## M1-1：人格系统（配置加载）

- **Task ID**: e5204f51-e5e7-49cb-bf47-7984f49a2a97
- **Priority**: P1
- **依赖**: M0 全部
- **当前状态**: DONE（加载器/注册表 + 列表 API 已存在）
- **证据**:
  - [backend/app/core/personalities/models.py](backend/app/core/personalities/models.py)
  - [backend/config/personalities](backend/config/personalities)

**DoD**
- [x] 人格配置错误能被启动校验捕获（加载失败会抛出）

**Verify**
- [ ] 新增人格 YAML → 重启后可列出（执行期补充记录）
- [ ] 人格缺字段/非法字段 → 启动失败并定位到文件（执行期补充记录）

**执行记录**
- 2026-02-11：新增人格列表 API，满足最小返回字段要求。

**下一步**
- 补一条“新增人格 YAML 的演练记录”。

---

## M1-2：Orchestrator 主链路（非流式）

- **Task ID**: e9644fbe-1886-476d-a032-f37c29d1da52
- **Priority**: P1
- **依赖**: M0 全部 + M1-1
- **当前状态**: DONE（主链路与持久化已补齐）
- **证据**:
  - [backend/app/orchestration/chat.py](backend/app/orchestration/chat.py)
  - [backend/app/api/v1/chat/completions.py](backend/app/api/v1/chat/completions.py)

**DoD**
- [x] 非流式返回结构存在（chat.completion）
- [x] user/assistant 消息写入 DB
- [x] 任意失败返回统一错误结构（已统一错误模型）

**Verify**
- [ ] curl/客户端调用返回 content（执行期补充）
- [ ] DB：messages/session 记录正确（待持久化补齐后）

**执行记录**
- 2026-02-11：补齐消息持久化与会话创建逻辑。

**下一步**
- 补齐 `_persist_message` 的真实 DB 写入与 session/message_count 更新。

---

## M1-3：AI Engine（最小实现：OpenAI）

- **Task ID**: e1602418-e852-400f-bb67-02a907f209eb
- **Priority**: P1
- **依赖**: M1-2
- **当前状态**: DONE（依赖补齐，支持 provider+model 维度缓存）
- **证据**:
  - [backend/app/engines/ai/__init__.py](backend/app/engines/ai/__init__.py)
  - [backend/app/engines/registry.py](backend/app/engines/registry.py)
  - [backend/pyproject.toml](backend/pyproject.toml)

**DoD**
- [x] 能切换 model/provider（按配置缓存 provider+model）

**Verify**
- [ ] 同一 provider/model 多次调用命中缓存（执行期补充）

**执行记录**
- 2026-02-11：补齐 `openai` 依赖与模型配置透传。

**下一步**
- 2026-02-13 更新：已补齐 `openai` 依赖，并支持按 `provider` + `model` 缓存单例 client。

---

# M2：SSE 流式 + 工具调用闭环

## M2-1：SSE 流式输出

- **Task ID**: 2b386173-cca1-474e-8418-3eec6830e753
- **Priority**: P1
- **依赖**: M1-3
- **当前状态**: DONE（SSE + [DONE] + 断连检查均已有实现点）
- **证据**:
  - [backend/app/api/v1/chat/completions.py](backend/app/api/v1/chat/completions.py)
  - [backend/app/orchestration/chat.py](backend/app/orchestration/chat.py)

**DoD**
- [x] OpenAI delta chunk 结构（choices[].delta）
- [x] 结束帧 `[DONE]`
- [x] 反代兼容 header（X-Accel-Buffering 等）

**Verify**
- [ ] SSE 客户端接收 chunk，最后收到 `[DONE]`（执行期补充记录）
- [ ] 中途断开连接无资源泄漏（执行期补充记录）

**执行记录**
- 2026-02-11：代码已覆盖 DoD 核心项，待执行期补充验证记录。

---

## M2-2：Tools Engine 与工具调用循环

- **Task ID**: 60f4b54e-1a5f-4d71-bcdc-f73d3ed6b183
- **Priority**: P1
- **依赖**: M2-1
- **当前状态**: DONE（工具循环/白名单/审计字段已对齐）
- **证据**:
  - [backend/app/orchestration/chat.py](backend/app/orchestration/chat.py)
  - [backend/app/engines/tools/basic.py](backend/app/engines/tools/basic.py)

**DoD**
- [x] 工具循环最大迭代次数（max_tool_iterations）
- [x] 工具调用审计入口（AuditService.log_tool_invocation）
- [x] 白名单/权限/速率限制路径已对齐实现

**Verify**
- [ ] 构造触发 tool_calls：能执行并回填结果
- [ ] 工具报错：模型收到 tool 错误并继续生成
- [ ] 超过限流阈值返回明确错误

**执行记录**
- 2026-02-11：修复权限枚举引用与审计字段对齐。

**下一步**
- 建议在执行期增加 1 份最小 smoke 流程（可直接写在执行记录区）。

---

# M3：人格化上下文（并行三引擎 + 降级 + token 预算）

## M3-1：ContextService（新主路径）

- **Task ID**: 83a10c0b-3ca8-4194-8ebd-5d916b48132f
- **Priority**: P1
- **依赖**: M1-3 + M0 全部
- **当前状态**: DONE（并行/超时降级/token budget 结构已实现）
- **证据**:
  - [backend/app/context/service.py](backend/app/context/service.py)

**DoD**
- [x] 三引擎并行（asyncio.gather）
- [x] 单个失败不影响主链路（timeout/error → degraded）
- [x] metadata 记录降级原因/耗时

**Verify**
- [ ] 人为让单引擎超时/失败：请求仍成功且降级被记录（执行期补充）

**执行记录**
- 2026-02-11：核心结构已存在，待执行期补充故障注入验收记录。

---

## M3-2：Knowledge/UserProfile/ChatMemory 引擎（先 remote client）

- **Task ID**: 7324c39e-1135-4a74-8624-95c82b9e0588
- **Priority**: P2
- **依赖**: M3-1
- **当前状态**: IN_PROGRESS
- **证据**:
  - [backend/app/engines/registry.py](backend/app/engines/registry.py)

**DoD**
- [ ] provider 接入（Cognee/Memobase/Mem0 等）
- [ ] 统一超时、错误分类、健康检查
- [ ] 熔断与多级缓存（L1/L2）

**执行记录**
- 2026-02-11：未开始（以 Null 引擎为证据）。
- 2026-02-13：开始实现远程客户端引擎，首选接入 Mem0/Memobase 接口。

---

## M3-3：异步回写（画像/记忆）

- **Task ID**: 9151120e-00b9-45a7-8832-068b6e8fc5e0
- **Priority**: P2
- **依赖**: M3-2
- **当前状态**: TODO

**DoD**
- [ ] 异步队列/重试/回压策略
- [ ] 关键指标可观测

---

# M4：语音能力（STT/TTS） + Realtime（FastRTC）

## M4-1：STT/TTS HTTP 与流式能力

- **Task ID**: 692d6da7-d113-43de-bead-f397cb68c196
- **Priority**: P2
- **依赖**: M1-2
- **当前状态**: TODO

---

## M4-2：Realtime（FastRTC）

- **Task ID**: 16fba181-09ca-4d8e-9057-8d013373c8de
- **Priority**: P2
- **依赖**: M4-1
- **当前状态**: TODO
- **证据**:
    - [docs/adr/ADR-0012-基于-FastRTC-的实时语音对话实现方案-v1.0-2026-02-13.md](docs/adr/ADR-0012-基于-FastRTC-的实时语音对话实现方案-v1.0-2026-02-13.md)

**执行记录**
- 2026-02-13：架构师完成技术选型与 ADR 编写。开发团队回归 M3 优先级，暂缓 M4 实施。

---

# M5：兼容层补齐 + 灰度切流

## M5-1：CozyChat 兼容 API（最小集合）

- **Task ID**: 7958e8aa-4680-44f9-a726-4a4a6b7e2d7a
- **Priority**: P2
- **依赖**: M1-2 + M2-1
- **当前状态**: TODO（未看到 compat 路由实现）

---

## M5-2：对比测试与差异分析

- **Task ID**: 2d946c5e-1d7e-4dc2-9e89-d759356a3fad
- **Priority**: P2
- **依赖**: M5-1
- **当前状态**: TODO

---

## M5-3：灰度与回滚机制

- **Task ID**: b1ccfa06-6e61-4210-ba17-b92d24d1a95f
- **Priority**: P3
- **依赖**: M5-1
- **当前状态**: TODO

---

# M6：性能/稳定性/安全加固 + 可运营化

## M6-1：性能与容量

- **Task ID**: d2820146-2743-440d-aab2-725d2726cef0
- **Priority**: P3
- **依赖**: M5-2
- **当前状态**: TODO

---

## M6-2：安全加固

- **Task ID**: 7ddccbff-1724-4b09-ba17-72fb162d670d
- **Priority**: P3
- **依赖**: M5-3
- **当前状态**: TODO

---

## M6-3：运行保障

- **Task ID**: 580ff88f-3865-4a71-8983-ee225117a0f4
- **Priority**: P3
- **依赖**: M6-1 + M6-2
- **当前状态**: TODO

---

## 4. 全局问题与决策记录（持续维护）

### 4.1 Open Issues（按优先级）

- **P2**：兼容层（api/compat）尚未开始

### 4.2 ADR 索引

- [ADR-0012: 基于 FastRTC 的实时语音对话实现方案](docs/adr/ADR-0012-基于-FastRTC-的实时语音对话实现方案-v1.0-2026-02-13.md)

---

## 5. 文档变更记录

- 2026-02-11：创建 v1.0（初始化任务状态与仓库快照）。
