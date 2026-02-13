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

## Python 虚拟环境（后端）
- 如果后端项目是 Python（存在 backend/pyproject.toml 或 backend/requirements.txt），必须优先使用 backend/venv 作为虚拟环境目录（不是全局 Python，也不要依赖系统 site-packages）。
- 每次进行任何 Python 相关操作（运行/测试/格式化/安装依赖）前，先检查 backend/venv 是否存在；不存在则创建：python3 -m venv backend/venv。
- 依赖安装规则：
  - 存在 backend/pyproject.toml：使用 backend/venv/bin/python -m pip install -e ".[dev]"（需要测试/ruff/pyright 时）；仅运行服务可用 -e .。
  - 存在 backend/requirements.txt：使用 backend/venv/bin/python -m pip install -r requirements.txt。
- 调用 Python / pytest / ruff 时，必须使用 backend/venv/bin/python（或 venv 激活后的等价命令），避免混用不同解释器导致不可复现。

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
## vibe_kanban task development workflow

**MANDATORY**: All tasks MUST follow this standardized workflow using vibe_kanban task management.

### Phase 1: Task Preparation
1. **Query task list**:
   ```
   list_projects() → list_tasks(project_id)
   ```
2. **Select next task** based on:
   - Priority (P0 > P1 > P2 > P3)
   - Dependency completion
   - Current milestone
3. **Read task details**:
   ```
   get_task(task_id)
   ```
   Review: description, acceptance criteria, dependencies, design docs

### Phase 1.5: Repo Hygiene Check
1. Ensure all previous work is already on `main`.
2. Ensure no open PRs or leftover feature branches for this repo.

### Phase 2: Main Branch Sync (No PR)
```bash
git checkout main
git pull origin main
```
Develop directly on `main`. Do not create feature branches or PRs.

### Phase 3: Development & Implementation
1. **Read design docs** referenced in task (e.g., docs/engine-v2/*)
2. **Implement changes** following:
   - Architecture constraints (dependency direction)
   - Coding conventions (async, type hints, docstrings)
   - Error handling (unified error model)
   - Observability (structured logs with request_id)
3. **Keep commits atomic** and focused on the task

### Phase 4: Self Code Review (MANDATORY)
Before committing, perform self-review checking:
- ✅ **Functionality**: Core requirements met
- ✅ **Architecture**: Follows 5-layer design, respects dependency rules
- ✅ **Code quality**: Type hints, docstrings, clear logic
- ✅ **Error handling**: Unified error format (error.code/message/request_id)
- ✅ **Observability**: Logs include request_id/user_id/session_id, no PII/secrets
- ✅ **Testing**: Existing tests pass (pytest)
- ✅ **Design compliance**: Changes align with design docs

**If issues found**: Fix before committing (or create hotfix after merge if critical)

### Phase 5: Testing
```bash
cd backend
pytest -q tests/test_{relevant_module}.py
# Or run full test suite
pytest -q
```
Ensure all tests pass before proceeding.

### Phase 6: Commit & Push (Main Only)
```bash
git add {changed-files}
git commit -m "feat(M{milestone}-{task}): {short description}

{detailed changes, bullet points}
...

Deliverable: {task title} (Task #{task_id})"

git push origin main
```

**Commit message format**:
- Type: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Scope: `(M{milestone}-{task})` e.g., `(M2-1)`
- Include task_id in footer

### Phase 7: Local Review Report (MANDATORY)
**Before delivery, perform comprehensive code review**:

#### Review Checklist:
- ✅ **Functionality**: Core requirements fully met, no bugs
- ✅ **Architecture Compliance**: 
  - Follows 5-layer design (API/Orchestration/Context/Engines/Storage)
  - Respects dependency direction rules
  - No violations of singleton/stateless rules
- ✅ **Code Quality**:
  - Complete type hints on all public interfaces
  - Docstrings on all public functions/classes
  - Clear, readable logic
  - No code smells or anti-patterns
- ✅ **Error Handling**:
  - Uses unified error model (error.code/message/request_id)
  - Proper exception propagation
  - No silent failures
- ✅ **Observability**:
  - Structured logs with request_id/user_id/session_id/personality_id
  - No PII/secrets in logs
  - Key operations logged (start/end/errors)
  - Proper log levels
- ✅ **Security**:
  - No hardcoded credentials
  - Input validation present
  - No SQL injection risks
  - Proper authentication/authorization checks
- ✅ **Performance**:
  - No obvious performance bottlenecks
  - Proper async/await usage
  - Resource cleanup (connections, files, streams)
- ✅ **Testing**:
  - All existing tests pass
  - Critical paths have test coverage
  - Edge cases considered
- ✅ **Design Compliance**:
  - Aligns with design docs (docs/engine-v2/*)
  - No deviations without ADR
  - API behavior matches OpenAI compatibility spec

#### Review Process:
1. Read through all changes carefully
2. Run tests locally
3. Check against design documents
4. Identify P0 (blocking), P1 (should fix), P2 (nice to have) issues
5. **If P0 issues found**: Fix immediately on main before delivery
6. **If P1 issues found**: Document for immediate follow-up hotfix
7. **If only P2 issues**: Document for future optimization, OK to deliver

#### Review Output:
Generate a structured review report with:
- **✅ Passed checks**: What's good
- **⚠️ Issues found**: Categorized by priority (P0/P1/P2)
- **📊 Scoring**: Rate each dimension (Functionality, Architecture, Quality, etc.)
- **🎯 Recommendation**: Deliver / Fix P0 first / Major rework needed

### Phase 8: Delivery on Main
1. Ensure `main` is pushed to origin.
2. Attach the review report to the task record if needed.

### Phase 9: Update Task Status
```bash
update_task(task_id, status="done")
```

### Hotfix Workflow (if issues found post-delivery)
1. **Sync main**:
  ```bash
  git checkout main
  git pull origin main
  ```
2. **Fix issues** (follow Phase 3-5)
3. **Commit**:
  ```bash
  git commit -m "fix(M{milestone}-{task}): {what was fixed}

  Addresses Code Review issues:
  - {issue 1}
  - {issue 2}
   
  Task: {task title} (#{task_id})"
  ```
4. **Push main**:
  ```bash
  git push origin main
  ```
5. **No need to update task status** (already done)

### Key Principles
- **One task = Direct main development** - No feature branches or PRs
- **Self-review before commit** - Catch issues early
- **Local review report before delivery** - Ensure quality without PRs
- **Test before push** - Keep main green
- **Always include task_id** - Enable traceability
- **Update vibe_kanban status** - Keep task board synchronized

### Common Mistakes to Avoid
- ❌ Creating feature branches or PRs
- ❌ Skipping self-review or the local review report
- ❌ Pushing without running tests
- ❌ Forgetting to update task status
- ❌ Not including request_id in logs/responses
- ❌ Breaking dependency direction rules
- ❌ Mixing feature work with unrelated changes