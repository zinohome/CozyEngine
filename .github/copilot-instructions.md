# CozyEngine Copilot Instructions

## Project context
- CozyEngine is a plugin-based chat engine extracted from CozyChat. Architecture is 5-layer: API -> Orchestration -> Context -> Engines -> Storage. See docs/engine-v2/02-总体架构-v2.0-2026-01-09.md.
- API supports OpenAI-compatible chat completions plus CozyChat compatibility endpoints. See docs/engine-v2/08-API设计（OpenAI兼容+CozyChat兼容）-v2.0-2026-01-09.md.
- Core personalization uses three engines (Knowledge, UserProfile, ChatMemory) in parallel with timeouts and per-engine degradation. See docs/engine-v2/02-总体架构-v2.0-2026-01-09.md.
- Voice/Reatime design uses FastRTC for WebRTC/VAD when implemented. See docs/reports/CozyEngine-高风险技术解决方案-v2.0-基于FastRTC-2026-02-09.md.

## Structure and dependency rules
- Follow the intended backend layout: backend/app/{api,core,orchestration,context,engines,storage,middleware,observability,utils}. See docs/engine-v2/04-目录结构与分层规范-v2.0-2026-01-09.md.
- Dependency direction must be respected: API -> orchestration/context/core; orchestration -> context + engines (interfaces) + storage (interfaces); context -> engines (interfaces) + core; engines cannot depend on orchestration/context/api; storage cannot depend on engines.
- Compatibility endpoints must live under api/compat/* (no mixing with primary API code).
- Singletons are allowed only for stateless components (pools, registries, clients). Do not store user/session/request state in singletons.

## Coding conventions (from .cursorrules)
- Use async for IO paths and FastAPI Depends for DI. API layer stays thin; business logic lives in orchestration/context/engines.
- All public interfaces require type hints and docstrings.
- Error responses must follow the unified error model (docs/engine-v2/11-错误处理与可观测性-v2.0-2026-01-09.md).
- Structured logs must include request_id/user_id/session_id/personality_id when available; never log secrets or PII.
- SSE responses must follow OpenAI delta format and end with [DONE].
- Tools must be gated by whitelist + permission checks + audit logging; limit tool-call loops.

## Documentation and ADR workflow
- Design docs in docs/engine-v2/ are authoritative. If implementation deviates, update the original design doc first and bump its version/date.
- Document naming must include version and date: ...-vX.Y-YYYY-MM-DD.md.
- For key architectural decisions (interfaces, boundaries, data/security), add ADRs under docs/adr/ADR-####-标题-v1.0-YYYY-MM-DD.md.
- Docs index: docs/README.md and docs/engine-v2/INDEX-v2.0-2026-01-09.md.

## What to check before changing code
- Does this change alter behavior, interfaces, or boundaries? If yes, update the relevant design doc and bump version.
- Does it touch API behavior? Align with OpenAI-compatible chat completions and CozyChat compatibility API definitions.
- Does it affect personalization or tool calls? Ensure parallelism, timeouts, and degradation are preserved.

## Where to look for plans
- Delivery milestones and phased tasks are in docs/plans/CozyEngine-v2-开发任务计划书-v1.1-2026-02-09.md.
