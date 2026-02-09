## CozyEngine v2 开发任务计划书（覆盖开发/测试/部署）

> **文档版本**: v1.1  
> **更新日期**: 2026-02-09  

### 0. 目的与范围

本计划书用于指导将 CozyChat 后端能力抽离并重构为 **CozyEngine v2（人格化、插件式聊天引擎）** 的全流程交付，覆盖：

- 开发：核心链路、插件系统、三大人格化引擎、兼容层
- 测试：单元/集成/端到端、性能、回归
- 部署：容器化、配置、可观测、灰度、回滚

设计依据（必须遵循）：

- `docs/engine-v2/INDEX-v2.0-2026-01-09.md`（及该目录下所有 v2.0 设计文档）
- `docs/prd/CozyEngine-PRD-完整需求文档-v1.0-2026-02-09.md`
- `docs/reports/CozyEngine-架构评审报告-v1.0-2026-02-09.md`
- `docs/reports/CozyEngine-需求可行性评审报告-v1.0-2026-02-09.md`
- 文档规范：`docs/standards/文档规范-v1.0-2026-01-09.md`

### 1. 交付物清单（最终态）

#### 1.1 代码交付物

- CozyEngine 后端服务（可独立运行/部署）
- OpenAI 兼容 API：
  - `POST /v1/chat/completions`（流式/非流式，支持 tool_calls）
- CozyChat 兼容 API（最小集合）：
  - sessions/messages/personalities/tools/audio（按设计文档 08）
- 插件系统：
  - AI Engine、Tools Engine、Knowledge Engine、UserProfile Engine、ChatMemory Engine（按设计文档 05/06）
- 数据层：
  - Postgres（users/sessions/messages/audit_events）
  - Redis（缓存/队列可选）
- 可观测：
  - 结构化日志、关键指标、（可选）追踪、Sentry 开关

#### 1.2 文档交付物

- 设计文档（已存在，后续变更需升版本）
- 运维手册（runbooks，可新增）
- ADR（重要决策必须新增）
- 本计划书（更新随项目推进升版本）

### 2. 总体里程碑（Milestones）

> 说明：每个阶段均包含“交付标准（DoD）”与“验证过程（Verify）”，必须完成才能进入下一阶段。

- **M0：项目骨架与工程化底座（含安全/密钥基线）**
- **M1：核心聊天链路（非流式）**
- **M2：SSE 流式 + 工具调用闭环**
- **M3：人格化上下文（并行三引擎 + 超时降级 + token 预算）**
- **M4：语音能力（STT/TTS） + Realtime（FastRTC）**
- **M5：兼容层补齐 + 灰度切流**
- **M6：性能/稳定性/安全加固 + 可运营化**

**总体工期预估（基于评审修正）**：
- 主路径：14-20 人天（已纳入 FastRTC 简化）
- 风险缓冲：+20%（外部服务波动与兼容层差异）

### 3. 角色与责任（RACI 简化）

- **架构/实现负责人**：接口/边界、关键决策、最终验收
- **后端开发**：Orchestrator/Context/Engines/Storage/API
- **测试/QA**：测试计划、自动化、回归与验收
- **运维/平台**：部署、监控告警、灰度与回滚

### 4. 阶段计划（细颗粒度任务）

## M0：项目骨架与工程化底座

### M0-1 仓库结构与依赖管理

- **任务**
  - 建立 `backend/` 项目目录（按 `docs/engine-v2/04-*`）
  - 选择依赖管理（建议：`pyproject.toml + uv` 或 `poetry`；需 ADR 记录）
  - 增加 `README`（如何启动/配置）
  - 增加 `.env.example`（只放占位符，不放密钥）
- **交付标准（DoD）**
  - `backend/` 可 `pip install` 并启动
  - 代码风格/静态检查工具已配置（ruff/pyright/pytest 等）
- **验证过程（Verify）**
  - 本地启动成功（命令写入 README）
  - 运行 `pytest -q` 返回通过或明确“无测试（允许 M0 末仍少量）”

### M0-2 配置系统与环境分层

- **任务**
  - 建立 YAML 配置目录：`backend/config/`（按 `docs/engine-v2/10-*`）
  - 建立 Settings（环境变量）与 YAML 合并策略（YAML>env>default）
  - 配置 schema 校验（启动时强校验）
- **交付标准（DoD）**
  - 启动时输出配置版本与关键开关（脱敏）
  - 缺失必需密钥会明确报错（错误码清晰）
- **验证过程（Verify）**
  - 用缺失密钥/错误 provider 启动，必须失败且错误可读
  - 用完整配置启动，必须成功

### M0-3 可观测与错误体系

- **任务**
  - 结构化日志（request_id/user_id/session_id/personality_id）
  - 统一错误模型（error.code/message/request_id）
  - 接入限流/性能中间件（可参考 CozyChat，但按 v2 抽象）
- **交付标准（DoD）**
  - 任意 API 错误响应统一结构
  - 日志不泄露密钥/PII（默认不打印消息原文）
- **验证过程（Verify）**
  - 构造 401/403/422/500，检查错误结构一致
  - 搜索日志输出，确保无 token/secret

### M0-4 数据库基础与迁移
- **任务**
  - 建立 ORM 与迁移（Alembic）
  - 实现最小表：users/sessions/messages/audit_events（按 `docs/engine-v2/09-*`）
  - 增加索引与软删字段（基于评审结论）
  - 提供健康检查：DB/Redis/外部引擎（可先 stub）

- **交付标准（DoD）**
  - 一键迁移/建表可复现
  - 关键索引与软删字段到位
  - health check 端点能区分“部分降级可用/不可用”
- **验证过程（Verify）**
  - 新库执行迁移成功；重复执行幂等
  - 索引与软删字段存在且可用
  - health check 返回结构稳定

---

## M1：核心聊天链路（非流式）

### M1-1 人格系统（配置加载）

- **任务**
  - 定义 Personality 模型与加载器（YAML）
  - 人格注册表（启动加载、缓存、可重载但受控）
  - `GET /v1/personalities`（最小返回：id/name/description/ai/tools/memory/voice 摘要）
- **DoD**
  - 人格配置错误能被启动校验捕获
  - API 返回稳定
- **Verify**
  - 新增一个人格 YAML → 重启后可被列出
  - 人格缺字段/非法字段 → 启动失败并定位到文件

### M1-2 Orchestrator 主链路（非流式）

- **任务**
  - 建立 `ChatOrchestrator`（按 `docs/engine-v2/07-*`）
  - 请求准备：鉴权、会话校验、人格选择、模型选择、参数规范化
  - 消息持久化：将 user/assistant 消息写入 DB
- **DoD**
  - `POST /v1/chat/completions` 非流式返回可用
  - 任意失败返回统一错误结构
- **Verify**
  - 用 curl/客户端调用：返回 content
  - 查看 DB：messages/session 记录正确、归属正确

### M1-3 AI Engine（最小实现：OpenAI）

- **任务**
  - AI Engine 接口与 OpenAI provider 实现（按 `docs/engine-v2/06-*`）
  - 引擎池（按 provider/model 缓存）
- **DoD**
  - 能切换 model/provider（受控白名单）
- **Verify**
  - 同一 provider/model 多次调用命中缓存（日志可见）

---

## M2：SSE 流式 + 工具调用闭环

### M2-1 SSE 流式输出

- **任务**
  - `stream=true` 返回 SSE
  - `[DONE]` 结束帧
  - 反代兼容 header（`X-Accel-Buffering: no` 等）
- **DoD**
  - 与 OpenAI 兼容的 delta 格式
  - 不因客户端断开导致资源泄漏
- **Verify**
  - 使用简单 SSE 客户端接收 chunk，最后收到 `[DONE]`
  - 中途断开连接，服务端无异常堆积（观察日志/指标）

### M2-2 Tools Engine 与工具调用循环

- **任务**
  - Tools Engine 接口
  - 内置工具最小集（read-only 示例）+ MCP 工具发现（可后置）
  - 工具循环：最大迭代次数、工具失败回填 tool role 消息、审计记录
  - 工具安全基线：副作用等级、白名单、速率限制
- **DoD**
  - 工具调用有白名单与权限校验
  - 关键工具具备速率限制与基础沙箱策略
  - 每次工具调用写入 audit_events
- **Verify**
  - 构造模型触发 tool_calls：能执行并回填结果
  - 工具报错：模型收到 tool 错误并继续生成解释/降级方案
  - 超过限流阈值时返回明确错误

---

## M3：人格化上下文（并行三引擎 + 降级 + token 预算）

### M3-1 ContextService（新主路径）

- **任务**
  - ContextBundle 统一结构
  - recent messages + summaries（可选） + 三引擎并行结果组装
  - token 预算与裁剪策略
- **DoD**
  - 三引擎并行，单个失败不影响主链路
  - metadata 记录：命中缓存/降级原因/耗时
- **Verify**
  - 人为将一个引擎超时/失败：请求仍成功且降级被记录
  - 超长上下文：被裁剪后仍能成功生成

### M3-2 Knowledge/UserProfile/ChatMemory 引擎（先 remote client）

- **任务**
  - provider 接入：Cognee/Memobase/Mem0（按配置可开关）
  - 统一超时、错误分类、健康检查
  - 熔断与多级缓存（L1/L2）
- **DoD**
  - 引擎不可用 → 自动降级为空结构
  - 引擎可用 → 结果能进入系统 prompt/metadata
  - 熔断后可自动恢复（按时间窗口）
- **Verify**
  - 断开外部服务：系统可用但降级
  - 恢复外部服务：系统自动恢复且日志可观测

### M3-3 异步回写（画像/记忆）

- **任务**
  - ChatMemory/UserProfile 更新可异步（队列/批量/重试）
  - 回压策略与观测指标
- **DoD**
  - 异步队列积压可观测并可限流/丢弃策略明确（需 ADR）
- **Verify**
  - 注入高频请求：队列长度变化符合预期，系统不崩溃

---

## M4：语音能力（STT/TTS） + Realtime（FastRTC）

### M4-1 STT/TTS HTTP 与流式能力

- **任务**
  - STT HTTP 接口（离线上传）
  - TTS HTTP 接口（音频生成）
  - WebSocket STT + SSE TTS（在线模式）
  - 供应商抽象与主备切换
- **DoD**
  - 离线与在线模式均可用
  - 供应商可切换（主备）
- **Verify**
  - 录音上传 → 转录 → 进入对话流程
  - 在线模式边说边转录，生成语音播放

### M4-2 Realtime（基于 FastRTC）

- **任务**
  - FastRTC 集成与 `stream.mount(app)`
  - ReplyOnPause 启用 VAD
  - Realtime 会话创建/关闭/超时策略
- **DoD**
  - Realtime 延迟达成 P50 < 300ms（目标）
  - 断线后可重连（短期内）
- **Verify**
  - 端到端语音对话打通
  - 打断响应 < 100ms（P50）

## M5：兼容层补齐 + 灰度切流

### M5-1 CozyChat 兼容 API（最小集合）

- **任务**
  - sessions/messages/tools/audio 端点补齐（按 `docs/engine-v2/08-*`）
  - 鉴权与权限边界：只能访问自己的数据
- **DoD**
  - CozyChat 前端可在最小改动下使用（或提供适配层）
- **Verify**
  - 对照 CozyChat 前端需要的 API 清单逐条 smoke test

### M5-2 对比测试与差异分析

- **任务**
  - 新旧服务对照测试（相同输入 → 对比结构/关键字段）
  - 差异记录与处理：属于“可接受差异/必须一致”
- **DoD**
  - 差异清单归档到 `docs/reports/`（一次性报告）
- **Verify**
  - 关键字段一致：role/content/tool_calls/finish_reason

### M5-3 灰度与回滚机制

- **任务**
  - 灰度开关：按用户/环境/人格切流
  - 快速回滚：一键切回旧服务
- **DoD**
  - 回滚演练通过（必须做一次）
- **Verify**
  - 灰度打开/关闭即时生效，日志能追踪到路由决策

---

## M6：性能/稳定性/安全加固 + 可运营化

### M6-1 性能与容量

- **任务**
  - 压测脚本与基线（P50/P95/P99、降级率）
  - 缓存策略（L1/L2）与 key 规范
- **DoD**
  - 达到目标性能基线（阈值写入文档并可更新）
- **Verify**
  - 压测报告归档到 `docs/reports/`

### M6-2 安全加固

- **任务**
  - 工具权限分级、敏感接口管理员限制
  - 日志脱敏与 PII 策略检查
  - 密钥管理服务接入（KeyVault/Secret Manager/Vault）
  - 审计事件完整性校验（HMAC）
- **DoD**
  - 安全检查清单全部通过（写入 runbook）
  - 密钥可轮换且无明文外泄
- **Verify**
  - 静态扫描/人工审计通过（项目约定即可）

### M6-3 运行保障

- **任务**
  - 告警规则（引擎失败率、超时率、降级率、队列积压）
  - 故障排查 runbook
  - 灰度回滚演练记录
- **DoD**
  - 关键告警可触发且可定位
- **Verify**
  - 人为注入故障（关引擎/加延迟）→ 告警触发 → 按 runbook 可定位

---

### 5. 全局验收（Release Gate）

发布前必须满足：

- API：`/v1/chat/completions` 流式/非流式均可用
- 工具：白名单+权限+审计完整
- 上下文：三引擎并行+超时降级+token 预算
- 数据：session/messages/audit_events 可追溯
- 观测：日志结构化、关键指标可用、降级可观测
- 测试：关键场景自动化覆盖（见 `docs/engine-v2/13-*`）
- 文档：设计变更已升版本并同步实现；无“分叉设计文档”

### 6. 附：阶段验收检查清单模板（可复制）

- **文档**
  - [ ] 相关设计文档版本与更新日期已更新
  - [ ] 如有关键决策变更，已新增 ADR
- **功能**
  - [ ] API 行为符合设计
  - [ ] 权限边界正确
- **观测**
  - [ ] request_id 可贯穿日志
  - [ ] 降级原因可见
- **测试**
  - [ ] 单测通过
  - [ ] 集成测试通过
  - [ ] SSE/工具循环场景通过

