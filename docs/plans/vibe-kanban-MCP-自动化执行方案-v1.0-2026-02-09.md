# vibe-kanban MCP 自动化执行方案

> **文档版本**: v1.0  
> **日期**: 2026-02-09  
> **目标**: 通过 MCP 工具自动按顺序启动 CozyEngine 任务  

---

## 1. vibe-kanban MCP 能力分析

### 📊 **可用工具清单**

| 工具名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `list_projects()` | 列出所有项目 | - | projects[], count |
| `list_tasks(project_id, status?, limit?)` | 列出项目中的任务 | project_id, status(可选), limit(可选) | tasks[], count |
| `get_task(task_id)` | 获取单个任务详情 | task_id | task{id, title, status, description, ...} |
| `create_task(project_id, title, description?)` | 创建新任务 | project_id, title, description | task_id |
| `update_task(task_id, title?, description?, status?)` | 更新任务 | task_id, title(可选), description(可选), status(可选) | success |
| `delete_task(task_id)` | 删除任务 | task_id | success |
| `list_repos(project_id)` | 列出项目仓库 | project_id | repos[], count |
| `get_repo(repo_id)` | 获取仓库详情 | repo_id | repo{id, name, setup_script, dev_server_script, cleanup_script} |
| `start_workspace_session(task_id, executor, repos, variant?)` | **启动任务工作空间** | task_id, executor, repos, variant(可选) | workspace_session_id |
| `update_setup_script(repo_id, script)` | 更新仓库 setup 脚本 | repo_id, script | success |
| `update_dev_server_script(repo_id, script)` | 更新 dev server 脚本 | repo_id, script | success |
| `update_cleanup_script(repo_id, script)` | 更新清理脚本 | repo_id, script | success |

### 🔑 **核心工具：start_workspace_session**

```yaml
参数说明:
  task_id: 必需
    类型: UUID string
    说明: 要启动的任务 ID（如 73f518bb-9e3f-41fe-b831-2902b2aaba76）
    
  executor: 必需
    类型: enum
    可选值: CLAUDE_CODE, AMP, GEMINI, CODEX, OPENCODE, CURSOR_AGENT, QWEN_CODE, COPILOT, DROID
    说明: 选择哪个 AI Agent 来执行任务
    推荐: CLAUDE_CODE（当前）
    
  repos: 必需
    类型: array of {repo_id, branch}
    说明: 关联的仓库
    示例: 
      - {repo_id: "d5b07fe1-3cab-441e-b042-85749317fbe4", branch: "main"}
    
  variant: 可选
    类型: string or null
    说明: executor 的特定变体
```

### 📈 **工作流程**

```
┌─────────────────────────────────────────────────────────┐
│                  MCP 自动化执行流                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  1. list_tasks()                                         │
│     ↓                                                     │
│     获取所有任务 → 按依赖关系排序                       │
│                                                           │
│  2. 对每个任务按序:                                     │
│     ├─ get_task(task_id) → 读取任务详情                │
│     ├─ update_task(task_id, status='inprogress')       │
│     └─ start_workspace_session(task_id, ...)           │
│        ↓                                                  │
│        返回 workspace_session_id                        │
│        ↓                                                  │
│        [Agent 自动在该工作空间执行任务]                │
│                                                           │
│  3. 任务完成后:                                         │
│     ├─ update_task(task_id, status='done')             │
│     └─ 进入下一个任务 (goto 2)                         │
│                                                           │
│  4. 全部完成或失败:                                     │
│     └─ 生成报告 & 打印总结                             │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 2. CozyEngine 项目的配置

### 📍 **当前状态**

```
Project ID: da91073d-dde3-4c98-baad-5ff1ad321c63
Repo ID:    d5b07fe1-3cab-441e-b042-85749317fbe4  (CozyEngine)
Total Tasks: 20
```

### 🔗 **任务依赖关系解析**

从任务执行指南中提取的依赖关系：

```
Level 0 (无依赖):
  M0-1: 73f518bb-9e3f-41fe-b831-2902b2aaba76

Level 1 (依赖 Level 0):
  M0-2: 6e3c37cb-7ceb-4fc0-8904-55f9da4fb13e (→ M0-1)
  M0-3: ea73f036-97d3-429c-80e5-abe56578fc20 (→ M0-1)

Level 2 (依赖 Level 1):
  M0-4: edcff342-38d4-432b-b15c-1b010593acfb (→ M0-2)
  M1-1: e5204f51-e5e7-49cb-bf47-7984f49a2a97 (→ M0 全部)
  M1-2: e9644fbe-1886-476d-a032-f37c29d1da52 (→ M0 全部 + M1-1)
  M4-1: 692d6da7-d113-43de-bead-f397cb68c196 (→ M1-2)
  M5-1: 7958e8aa-4680-44f9-a726-4a4a6b7e2d7a (→ M1-2 + M2-1)

Level 3+ ...
  [见完整依赖树]
```

---

## 3. 自动启动方案（A：Manual 自动化）

### 🚀 **方案 A：我（Claude Agent）手动按顺序启动**

**流程**：
1. 我读取 M0-1 任务详情
2. 我调用 `start_workspace_session(M0-1, CLAUDE_CODE, repos)`
3. 系统在新工作空间中启动 Agent 执行 M0-1
4. 我等待 Agent 完成（通过日志或回调）
5. 我调用 `update_task(M0-1, status='done')`
6. 继续下一个任务 (M0-2 或 M0-3)

**优点**：
- ✅ 完全自动化，不需人工干预
- ✅ 我可以感知任务进度，动态调整顺序
- ✅ 可以并行启动多个独立任务（如 M0-2 + M0-3）
- ✅ 任务失败时可自动重试或降级

**缺点**：
- ❌ 需要我持续监控（如果用户中断会话，无法继续）
- ❌ 工作空间会话生命周期不清楚（是否自动关闭？）
- ❌ 跨会话状态管理复杂

---

## 4. 自动启动方案（B：Script 自动化）

### 📜 **方案 B：生成执行脚本让用户运行**

**脚本框架**（伪代码）：

```python
#!/usr/bin/env python3
"""
CozyEngine 任务自动启动器
自动按依赖顺序启动 vibe-kanban 任务
"""

import sys
import time
from typing import Dict, List, Set

# 导入 vibe-kanban MCP 工具（需要环境支持）
from vibe_kanban_client import (
    list_tasks, get_task, update_task, start_workspace_session
)

# 定义依赖关系
TASK_DEPENDENCIES = {
    "73f518bb-9e3f-41fe-b831-2902b2aaba76": [],  # M0-1: 无依赖
    "6e3c37cb-7ceb-4fc0-8904-55f9da4fb13e": ["73f518bb-9e3f-41fe-b831-2902b2aaba76"],  # M0-2 → M0-1
    "ea73f036-97d3-429c-80e5-abe56578fc20": ["73f518bb-9e3f-41fe-b831-2902b2aaba76"],  # M0-3 → M0-1
    "edcff342-38d4-432b-b15c-1b010593acfb": ["6e3c37cb-7ceb-4fc0-8904-55f9da4fb13e"],  # M0-4 → M0-2
    # ... 其他 17 个任务
}

PROJECT_ID = "da91073d-dde3-4c98-baad-5ff1ad321c63"
REPO_ID = "d5b07fe1-3cab-441e-b042-85749317fbe4"
EXECUTOR = "CLAUDE_CODE"

def get_ready_tasks(
    completed: Set[str], 
    in_progress: Set[str],
    dependencies: Dict[str, List[str]]
) -> List[str]:
    """获取可以启动的任务（依赖已完成且未开始）"""
    ready = []
    for task_id, deps in dependencies.items():
        if task_id in completed or task_id in in_progress:
            continue
        # 所有依赖都完成了吗？
        if all(dep in completed for dep in deps):
            ready.append(task_id)
    return ready

def start_task(task_id: str) -> bool:
    """启动一个任务"""
    print(f"  → 启动任务 {task_id[:8]}...")
    try:
        # 更新任务状态为 in_progress
        update_task(task_id, status="inprogress")
        
        # 启动工作空间会话
        session_id = start_workspace_session(
            task_id=task_id,
            executor=EXECUTOR,
            repos=[{"repo_id": REPO_ID, "branch": "main"}]
        )
        
        print(f"    ✓ 会话已启动: {session_id}")
        return True
    except Exception as e:
        print(f"    ✗ 启动失败: {e}")
        return False

def main():
    print("=" * 60)
    print("CozyEngine vibe-kanban 自动启动器")
    print("=" * 60)
    
    completed = set()
    in_progress = set()
    failed = set()
    
    # 主循环
    while True:
        # получить可以启动的任务
        ready = get_ready_tasks(completed, in_progress, TASK_DEPENDENCIES)
        
        if not ready:
            # 没有可启动的任务
            if in_progress:
                print(f"\n⏳ 等待进行中任务完成: {len(in_progress)} 个")
                # TODO: 实现任务监控与完成检测
                time.sleep(10)
            else:
                # 全部完成
                break
        else:
            # 启动就绪的任务
            for task_id in ready[:1]:  # 一次启动 1 个（可根据并行度调整）
                if start_task(task_id):
                    in_progress.add(task_id)
                else:
                    failed.add(task_id)
    
    # 输出总结
    print("\n" + "=" * 60)
    print(f"✓ 已完成: {len(completed)} 个任务")
    print(f"✗ 失败: {len(failed)} 个任务")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

**优点**：
- ✅ 用户可随时启动和重启
- ✅ 可配置并发度（同时启动 N 个任务）
- ✅ 完整的错误处理与重试
- ✅ 易于集成到 CI/CD

**缺点**：
- ❌ 需要安装 vibe-kanban SDK 或 HTTP 客户端
- ❌ 任务完成检测需要额外实现（轮询或回调）

---

## 5. 推荐的混合方案

### 🎯 **方案 C：两阶段自动化（推荐）**

#### **第 1 阶段：我（Claude）自动化**

```
目标: 启动 M0 的 4 个任务
步骤:
  1. Claude 调用 start_workspace_session(M0-1)
  2. M0-1 Agent 开始执行
  3. Claude 调用 start_workspace_session(M0-2)  [可并行]
  4. Claude 调用 start_workspace_session(M0-3)  [可并行]
  5. Claude 等待 M0-1 完成（监听日志）
  6. Claude 等待 M0-2 完成
  7. Claude 调用 start_workspace_session(M0-4)  [取决于 M0-2]
  8. Claude 等待 M0-4 完成

时间: ~4-5 天（任务实际执行时间）
人员: 仅需 Claude Agent（我）
```

#### **第 2 阶段：用户批量启动**

M0 完成后，用户可以选择：
- **选项 A**：我继续自动启动 M1+（手工切记 50 个 token 的窗口约束）
- **选项 B**：用户运行脚本 `python auto_launcher.py` 自动启动 M1-M6

---

## 6. 实施方案：立即开始

### 🚀 **立即执行（推荐）**

我现在可以：

1. **读取 M0-1 任务详情**
   ```
   get_task(task_id="73f518bb-9e3f-41fe-b831-2902b2aaba76")
   ```

2. **更新状态为进行中**
   ```
   update_task(task_id="73f518bb-9e3f-41fe-b831-2902b2aaba76", status="inprogress")
   ```

3. **启动工作空间会话**
   ```
   start_workspace_session(
       task_id="73f518bb-9e3f-41fe-b831-2902b2aaba76",
       executor="CLAUDE_CODE",
       repos=[{
           repo_id="d5b07fe1-3cab-441e-b042-85749317fbe4",
           branch="main"
       }]
   )
   ```

4. **等待完成并移至下一个任务**

### ⚠️ **关键约束**

- **工作空间会话生命周期**：`start_workspace_session` 返回后，Agent 是否立即开始执行？是否需要我持续监控？
- **跨会话通信**：多个任务的工作空间之间是否可共享状态？
- **错误恢复**：任务失败时是否自动重试，还是需要手工介入？

### 💡 **建议的下一步**

你告诉我：

1. **你想要什么执行模式？**
   - 模式 A：我立即启动 M0-1（今天）
   - 模式 B：生成完整自动化脚本给你控制
   - 模式 C：两阶段混合（我做 M0，脚本做 M1+）

2. **并行度偏好？**
   - 严格串行（一次 1 个）
   - 适度并行（阶段内可并行，如 M0-2 + M0-3）
   - 高度并行（同时启动 M1/M2/M3...）

3. **工作空间会话的管理方式？**
   - 单独监控每个会话
   - 批量管理（10 个任务为一个 batch）
   - 由你通过 VS Code vibe-kanban UI 手工监控

---

## 7. 性能考量

| 方案 | 总耗时（20 任务） | 并行度 | 实现复杂度 |
|------|------------------|--------|-----------|
| 完全串行 | ~20 人天 | 1 | 低 |
| 适度并行（M0 内并行） | ~12-15 人天 | ~2-3 | 中 |
| 高度并行（跨阶段） | ~8-10 人天 | ~3-5 | 高 |

---

## 8. 快速开始命令

如果你选择 **模式 A**（我立即启动），告诉我：

```
"启动 M0-1"
或
"开始自动执行任务，并行度 2"
或
"生成自动化脚本"
```

我就可以立即开始！

---

**等待你的决定...** ⏳
