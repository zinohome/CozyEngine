# CozyEngine 自动化执行与 PR 合并系统

> **文档版本**: v2.0 (完整版)  
> **日期**: 2026-02-09  
> **目标**: 自动执行任务 → 验证 → PR 合并 → 基线更新  

---

## 1. 完整执行流程架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     自动化 CI/CD 执行系统                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│ START                                                            │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 1. 任务读取 & 依赖分析                          │             │
│ │   get_task() → 读取 M0-1 详情                  │             │
│ │   分析依赖关系，确定执行顺序                    │             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 2. 创建 Feature 分支                            │             │
│ │   git checkout -b feature/M0-1/repo-structure   │             │
│ │   git push -u origin feature/M0-1/repo-structure│             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 3. 启动任务工作空间                             │             │
│ │   start_workspace_session(                      │             │
│ │     task_id=M0-1,                              │             │
│ │     executor=CLAUDE_CODE,                      │             │
│ │     repos=[{id, branch: feature/M0-1/*}]      │             │
│ │   )                                             │             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 4. Agent 执行代码 (在新工作空间)                │             │
│ │   - 实现 M0-1 需求                             │             │
│ │   - 提交代码到 feature 分支                    │             │
│ │   - 运行测试验证                               │             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 5. 自动验证 (我做)                             │             │
│ │   a) fetch 代码 & 检查更改                     │             │
│ │   b) 运行本地测试: pytest -q                   │             │
│ │   c) 代码质量检查: ruff check, pyright         │             │
│ │   d) 验证文档更新                              │             │
│ │ 结果: PASS/FAIL → 记录到任务描述               │             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 6. 创建 & 自动合并 PR                          │             │
│ │ 如果验证 PASS:                                 │             │
│ │   a) gh pr create --base main --head feature   │             │
│ │   b) 添加自动标签 & 描述                       │             │
│ │   c) 触发 GitHub Actions 验证                  │             │
│ │   d) 允许自动合并 (gh pr merge)                │             │
│ │ 如果验证 FAIL:                                 │             │
│ │   → 更新任务状态为 'inreview'                  │             │
│ │   → 标记失败原因在 PR 评论中                   │             │
│ │   → 等待人工介入                               │             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 7. 基线更新 & 任务完成                         │             │
│ │   - PR 合并到 main ✓                           │             │
│ │   - git pull origin main (更新本地)            │             │
│ │   - update_task(status='done')                 │             │
│ │   - 生成完成报告                               │             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ┌─────────────────────────────────────────────────┐             │
│ │ 8. 进入下一个任务的循环 (goto 1)               │             │
│ └─────────────────────────────────────────────────┘             │
│   ↓                                                              │
│ ALL TASKS COMPLETE                                             │
│   ↓                                                              │
│ 生成交付报告 & 发送总结                                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 前提条件检查

### ✅ **必需环境**

```
✓ Git 仓库配置: https://github.com/zinohome/CozyEngine.git
✓ 当前分支: main (同步最新)
✓ GitHub CLI: gh (用于 PR 管理)
✓ Python 环境: venv 已激活，依赖已安装
✓ Docker (可选): 用于隔离执行环境

❌ 需要创建:
  - GitHub Actions workflows (.github/workflows/ci.yml)
  - 任务执行验证脚本 (backend/scripts/validate.py)
  - PR 合并规则配置 (branch protection)
```

### 🔑 **权限要求**

```
GitHub 权限:
  - PR 创建: ✓ (origin 有写权限)
  - PR 合并: ✓ (需要 admin 或 maintain 权限)
  - Actions: ✓ (需要启用)

本地权限:
  - Git push: ✓ (已配置 main)
  - 文件修改: ✓ (workspace 可写)
```

---

## 3. 关键组件实现

### 3.1 **自动化任务执行器 (Task Executor)**

```python
# backend/scripts/task_executor.py

import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class TaskExecutor:
    """
    自动化任务执行器
    - 管理分支创建/切换
    - 触发 Agent 执行
    - 运行验证和测试
    - 创建和管理 PR
    - 更新任务状态
    """
    
    def __init__(self, project_id: str, repo_path: str):
        self.project_id = project_id
        self.repo_path = Path(repo_path)
        self.main_branch = "main"
        self.execution_log = []
    
    # ─── 分支管理 ───
    
    def create_feature_branch(self, task_id: str, task_name: str) -> str:
        """
        为任务创建 feature 分支
        
        分支命名规范: feature/{MILESTONE}/{task-name}
        示例: feature/M0/repo-structure
        """
        branch_name = f"feature/{task_name.split(':')[0]}/{task_name.lower().replace(' ', '-')}"
        
        # 确保本地在 main
        subprocess.run(["git", "checkout", self.main_branch], cwd=self.repo_path)
        subprocess.run(["git", "pull", "origin", self.main_branch], cwd=self.repo_path)
        
        # 创建并推送分支
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.repo_path)
        subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=self.repo_path)
        
        self.log(f"✓ 创建 feature 分支: {branch_name}")
        return branch_name
    
    def cleanup_feature_branch(self, branch_name: str):
        """任务完成后清理 feature 分支"""
        # 切回 main
        subprocess.run(["git", "checkout", self.main_branch], cwd=self.repo_path)
        # 删除本地分支
        subprocess.run(["git", "branch", "-D", branch_name], cwd=self.repo_path, 
                      capture_output=True)
        # 删除远程分支
        subprocess.run(["git", "push", "origin", "--delete", branch_name], cwd=self.repo_path,
                      capture_output=True)
    
    # ─── 验证与测试 ───
    
    def run_tests(self) -> Dict[str, bool]:
        """运行项目测试"""
        results = {}
        
        # 切入 backend 目录
        backend_path = self.repo_path / "backend"
        
        # 1. pytest
        print("  → 运行 pytest...")
        result = subprocess.run(
            ["python", "-m", "pytest", "-q", "--tb=short"],
            cwd=backend_path,
            capture_output=True,
            text=True
        )
        results["pytest"] = result.returncode == 0
        if result.returncode != 0:
            self.log(f"  ✗ pytest failed:\n{result.stdout}\n{result.stderr}")
        else:
            self.log(f"  ✓ pytest passed")
        
        # 2. ruff check
        print("  → 运行 ruff check...")
        result = subprocess.run(
            ["ruff", "check", "app/"],
            cwd=backend_path,
            capture_output=True,
            text=True
        )
        results["ruff"] = result.returncode == 0
        if result.returncode != 0:
            self.log(f"  ✗ ruff failed:\n{result.stdout}")
        else:
            self.log(f"  ✓ ruff check passed")
        
        # 3. pyright
        print("  → 运行 pyright...")
        result = subprocess.run(
            ["pyright", "app/"],
            cwd=backend_path,
            capture_output=True,
            text=True
        )
        results["pyright"] = result.returncode == 0
        if result.returncode != 0:
            self.log(f"  ✗ pyright failed:\n{result.stdout}")
        else:
            self.log(f"  ✓ pyright passed")
        
        return results
    
    def verify_changes(self, task_id: str) -> bool:
        """验证代码更改是否符合要求"""
        # 获取本次提交的更改
        result = subprocess.run(
            ["git", "diff", self.main_branch, "--name-only"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        changed_files = result.stdout.strip().split('\n')
        
        # 验证规则
        validations = {
            "docs_updated": any("docs" in f for f in changed_files),
            "code_changed": any("app" in f or "backend" in f for f in changed_files),
            "no_secrets": not self._check_secrets(changed_files),
        }
        
        self.log(f"  验证结果: {validations}")
        return all(validations.values())
    
    def _check_secrets(self, files: List[str]) -> bool:
        """检查是否有密钥泄露"""
        # 简单的正则检查
        import re
        secret_patterns = [
            r"api[_-]?key",
            r"password",
            r"secret",
            r"token",
        ]
        
        for file in files:
            with open(self.repo_path / file, 'r', errors='ignore') as f:
                content = f.read()
                for pattern in secret_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        return True
        return False
    
    # ─── PR 管理 ───
    
    def create_pr(self, branch_name: str, task_id: str, task_title: str) -> Optional[str]:
        """
        创建 Pull Request
        
        返回 PR URL 或 None (失败时)
        """
        pr_title = f"[{task_title.split(':')[0]}] {task_title}"
        pr_description = f"""
## Task Information
- Task ID: {task_id}
- Branch: {branch_name}
- Created at: {datetime.now().isoformat()}

## Changes Made
- Implemented required functionality
- Added/updated tests
- Updated documentation

## Verification
- [ ] Tests passed
- [ ] Code quality checks passed
- [ ] Documentation updated
- [ ] No secrets leaked
"""
        
        # 创建 PR
        result = subprocess.run(
            ["gh", "pr", "create",
             "--base", self.main_branch,
             "--head", branch_name,
             "--title", pr_title,
             "--body", pr_description,
             "--label", "automated"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pr_url = result.stdout.strip()
            self.log(f"✓ PR 创建成功: {pr_url}")
            return pr_url
        else:
            self.log(f"✗ PR 创建失败: {result.stderr}")
            return None
    
    def merge_pr(self, branch_name: str) -> bool:
        """
        自动合并 PR 到 main
        
        前提:
          - CI 通过
          - 代码审查通过（或无需审查）
          - 不存在冲突
        """
        # 等待 GitHub Actions 完成
        self.log("  ⏳ 等待 GitHub Actions 完成...")
        time.sleep(30)  # 给 GitHub Actions 时间启动
        
        # 检查 CI 状态
        result = subprocess.run(
            ["gh", "pr", "checks", branch_name],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        if "pass" not in result.stdout.lower():
            self.log(f"  ✗ CI 未通过，暂不合并")
            return False
        
        # 执行合并 (squash merge, 保持 main 清洁)
        result = subprocess.run(
            ["gh", "pr", "merge", branch_name,
             "--squash",
             "--body", "Auto-merged by CI"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            self.log(f"✓ PR 已合并到 main")
            return True
        else:
            self.log(f"✗ PR 合并失败: {result.stderr}")
            return False
    
    # ─── 任务管理 ───
    
    def execute_task(self, task_id: str, task_title: str) -> Dict[str, any]:
        """
        执行一个完整的任务周期
        
        返回执行结果:
        {
            "success": bool,
            "branch": str,
            "pr_url": str,
            "test_results": dict,
            "execution_log": list,
        }
        """
        print(f"\n{'='*60}")
        print(f"执行任务: {task_title}")
        print(f"Task ID: {task_id}")
        print(f"{'='*60}\n")
        
        self.execution_log = []
        result = {
            "success": False,
            "branch": None,
            "pr_url": None,
            "test_results": {},
            "execution_log": [],
        }
        
        try:
            # 1. 创建 feature 分支
            branch_name = self.create_feature_branch(task_id, task_title)
            result["branch"] = branch_name
            
            # 2. 启动任务工作空间 (由外部 Agent 执行)
            self.log(f"⏳ 等待任务执行 (由 Agent 在工作空间完成)...")
            self.log(f"   工作空间提示: 在分支 {branch_name} 上提交代码")
            
            # 3. 给用户时间完成任务（这里应该是异步等待）
            # 实际流程: Agent 在工作空间执行 → 推送到 {branch_name}
            # 这里需要等待或由用户触发"检查点"
            
            input(f"\n按 Enter 继续验证任务... (确保代码已推送到 {branch_name})")
            
            # 4. 验证变更
            self.log("开始验证...")
            if not self.verify_changes(task_id):
                self.log("✗ 代码验证失败")
                result["success"] = False
                return result
            
            # 5. 运行测试
            test_results = self.run_tests()
            result["test_results"] = test_results
            
            if not all(test_results.values()):
                self.log("✗ 测试失败，不创建 PR")
                result["success"] = False
                return result
            
            # 6. 创建 PR
            pr_url = self.create_pr(branch_name, task_id, task_title)
            result["pr_url"] = pr_url
            
            if not pr_url:
                result["success"] = False
                return result
            
            # 7. 合并 PR
            if self.merge_pr(branch_name):
                # 8. 更新本地 main 基线
                subprocess.run(["git", "checkout", self.main_branch], cwd=self.repo_path)
                subprocess.run(["git", "pull", "origin", self.main_branch], cwd=self.repo_path)
                
                # 9. 清理 feature 分支
                self.cleanup_feature_branch(branch_name)
                
                self.log("✓ 任务完成！")
                result["success"] = True
            
        except Exception as e:
            self.log(f"✗ 执行异常: {e}")
            result["success"] = False
        
        result["execution_log"] = self.execution_log
        return result
    
    def log(self, message: str):
        """记录执行日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        self.execution_log.append(log_msg)
        print(log_msg)


# ─── 用法示例 ───
if __name__ == "__main__":
    executor = TaskExecutor(
        project_id="da91073d-dde3-4c98-baad-5ff1ad321c63",
        repo_path="/Users/zhangjun/CursorProjects/CozyEngine"
    )
    
    # 执行单个任务
    result = executor.execute_task(
        task_id="73f518bb-9e3f-41fe-b831-2902b2aaba76",
        task_title="M0-1: 仓库结构与依赖管理"
    )
    
    print(f"\n执行结果: {result}")
```

---

### 3.2 **任务编排器 (Task Orchestrator)**

```python
# backend/scripts/task_orchestrator.py

from task_executor import TaskExecutor
from vibe_kanban_client import (
    list_tasks, get_task, update_task, start_workspace_session
)

class TaskOrchestrator:
    """
    任务编排器
    - 按依赖顺序执行所有任务
    - 监控执行进度
    - 生成最终报告
    """
    
    TASK_DEPENDENCIES = {
        # M0
        "73f518bb-9e3f-41fe-b831-2902b2aaba76": [],  # M0-1
        "6e3c37cb-7ceb-4fc0-8904-55f9da4fb13e": ["73f518bb-9e3f-41fe-b831-2902b2aaba76"],  # M0-2
        "ea73f036-97d3-429c-80e5-abe56578fc20": ["73f518bb-9e3f-41fe-b831-2902b2aaba76"],  # M0-3
        "edcff342-38d4-432b-b15c-1b010593acfb": ["6e3c37cb-7ceb-4fc0-8904-55f9da4fb13e"],  # M0-4
        # M1
        "e5204f51-e5e7-49cb-bf47-7984f49a2a97": ["73f518bb-9e3f-41fe-b831-2902b2aaba76", "6e3c37cb-7ceb-4fc0-8904-55f9da4fb13e", "ea73f036-97d3-429c-80e5-abe56578fc20", "edcff342-38d4-432b-b15c-1b010593acfb"],  # M1-1
        # ... 其他任务
    }
    
    def __init__(self, project_id: str, repo_path: str):
        self.project_id = project_id
        self.repo_path = repo_path
        self.executor = TaskExecutor(project_id, repo_path)
        self.results = {}
        self.failed_tasks = []
    
    def run_all_tasks(self, parallel_degree: int = 1):
        """
        执行所有任务
        
        参数:
          parallel_degree: 并行度 (目前仅支持 1，串行执行)
        """
        completed = set()
        failed = set()
        
        print("=" * 70)
        print("开始自动化任务执行")
        print("=" * 70)
        
        while True:
            # 获取可执行的任务
            ready = self._get_ready_tasks(completed, failed)
            
            if not ready:
                if not completed and not failed:
                    print("✗ 无可执行的任务")
                break
            
            # 执行就绪的任务
            for task_id in ready:
                # 获取任务详情
                task = get_task(task_id)
                task_title = task["title"]
                
                print(f"\n['执行任务 {len(completed)+1}/{len(self.TASK_DEPENDENCIES)}]")
                
                # 启动工作空间
                print(f"  1️⃣  启动工作空间...")
                try:
                    session_id = start_workspace_session(
                        task_id=task_id,
                        executor="CLAUDE_CODE",
                        repos=[{
                            "repo_id": "d5b07fe1-3cab-441e-b042-85749317fbe4",
                            "branch": "main"
                        }]
                    )
                    print(f"     ✓ 会话 ID: {session_id}")
                except Exception as e:
                    print(f"     ✗ 启动失败: {e}")
                    failed.add(task_id)
                    continue
                
                # 更新任务状态
                update_task(task_id, status="inprogress")
                
                # 执行任务
                print(f"  2️⃣  执行任务...")
                result = self.executor.execute_task(task_id, task_title)
                self.results[task_id] = result
                
                if result["success"]:
                    # 更新任务为完成
                    update_task(task_id, status="done")
                    completed.add(task_id)
                    print(f"  ✅ 任务完成")
                else:
                    failed.add(task_id)
                    update_task(task_id, status="inreview")
                    print(f"  ❌ 任务失败，标记为 inreview 等待人工处理")
                    self.failed_tasks.append({
                        "task_id": task_id,
                        "title": task_title,
                        "result": result
                    })
        
        # 生成报告
        self._generate_report(completed, failed)
    
    def _get_ready_tasks(self, completed, failed):
        """获取可以执行的任务"""
        ready = []
        for task_id, deps in self.TASK_DEPENDENCIES.items():
            if task_id in completed or task_id in failed:
                continue
            if all(dep in completed for dep in deps):
                ready.append(task_id)
        return ready
    
    def _generate_report(self, completed, failed):
        """生成执行报告"""
        print("\n" + "=" * 70)
        print("执行报告总结")
        print("=" * 70)
        print(f"✅ 成功: {len(completed)} 任务")
        print(f"❌ 失败: {len(failed)} 任务")
        
        if self.failed_tasks:
            print("\n需要人工处理的任务:")
            for task in self.failed_tasks:
                print(f"  - {task['title']}")
                print(f"    原因: {task['result'].get('test_results', {})}")
        
        # 保存报告到文件
        report_path = self.executor.repo_path / "docs/reports/execution_report.md"
        # 生成 Markdown 报告...


if __name__ == "__main__":
    orchestrator = TaskOrchestrator(
        project_id="da91073d-dde3-4c98-baad-5ff1ad321c63",
        repo_path="/Users/zhangjun/CursorProjects/CozyEngine"
    )
    
    orchestrator.run_all_tasks(parallel_degree=1)
```

---

## 4. 关键实现步骤

### 🔴 **第 1 阶段：基础设施准备**

```bash
# 1️⃣  创建 GitHub Actions CI 配置
mkdir -p /Users/zhangjun/CursorProjects/CozyEngine/.github/workflows
cat > .github/workflows/ci.yml << 'EOF'
name: CI Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -e ".[dev]"
      - name: Run tests
        run: |
          cd backend
          pytest -q
      - name: Ruff check
        run: |
          cd backend
          ruff check app/
      - name: Pyright
        run: |
          cd backend
          pyright app/
EOF

# 2️⃣  创建验证脚本
mkdir -p backend/scripts
touch backend/scripts/__init__.py
touch backend/scripts/task_executor.py
touch backend/scripts/task_orchestrator.py

# 3️⃣  配置 branch protection 规则
# 在 GitHub 仓库设置中:
#   Settings → Branches → Add rule (main)
#   - Require pull request reviews before merging: OFF (自动合并)
#   - Require status checks to pass before merging: ON
#   - Required checks: CI Tests
```

### 🟠 **第 2 阶段：启动自动化**

```bash
# 1️⃣  安装依赖
cd /Users/zhangjun/CursorProjects/CozyEngine/backend
python -m pip install pydantic httpx

# 2️⃣  设置 GitHub CLI token (如果还没有)
gh auth login

# 3️⃣  运行编排器
python scripts/task_orchestrator.py
```

---

## 5. 完整的执行流程示意

### **例：M0-1 完整执行周期**

```
Day 1, 09:00 - 启动
├─ task_orchestrator.run_all_tasks()
├─ 识别 M0-1 (无依赖，可执行)
└─ 调用 start_workspace_session(M0-1)
   
   [新工作空间打开]
   ├─ Claude Agent 开始执行
   ├─ 创建目录结构: backend/app/{api,core,...}
   ├─ 创建 pyproject.toml, README, .env.example
   ├─ 提交代码: git commit -m "feat: M0-1 repo structure"
   ├─ 推送分支: git push origin feature/M0/repo-structure
   └─ 通知编排器: "代码已推送，请验证"

Day 1, 10:00 - 验证
├─ task_executor.execute_task(M0-1)
├─ git fetch origin feature/M0/repo-structure
├─ verify_changes() → ✓ 检查文件和目录
├─ run_tests()
│  ├─ pytest -q → ✓ 通过（或 0 测试，允许）
│  ├─ ruff check → ✓ 代码风格
│  └─ pyright → ✓ 类型检查
└─ all_pass = True

Day 1, 10:15 - PR 创建
├─ gh pr create --base main --head feature/M0/repo-structure
├─ PR 自动添加标签: automated, M0
└─ PR URL: https://github.com/zinohome/CozyEngine/pull/1

Day 1, 10:20 - CI 验证
├─ GitHub Actions 启动: CI Tests
├─ ubuntu-latest 上重新运行 pytest/ruff/pyright
└─ Status: ✓ PASS

Day 1, 10:25 - 自动合并
├─ gh pr merge feature/M0/repo-structure --squash
├─ PR 合并到 main ✓
└─ Commit: "Merge pull request #1: [M0-1] 仓库结构与依赖管理"

Day 1, 10:30 - 基线更新
├─ git checkout main
├─ git pull origin main  (本地同步)
├─ update_task(M0-1, status="done")
└─ 进入 M0-2 执行...

[循环继续，直到所有 20 个任务完成]
```

---

## 6. 预期结果

### ✅ **任务完成标志**

每个任务完成后确认：

```
☑ 代码在 main 分支上
☑ PR 已合并
☑ CI 通过
☑ docs 已更新（如需）
☑ 下一个任务重新在 main 基线上启动
```

### 📊 **最终交付**

```
CozyEngine/
├── backend/
│   ├── app/
│   │   ├── api/          ✓ M1-2 完成
│   │   ├── orchestration/ ✓ M1-2 完成
│   │   ├── context/       ✓ M3 完成
│   │   ├── engines/       ✓ M3-2 完成
│   │   └── ...
│   ├── tests/             ✓ 全覆盖
│   └── pyproject.toml     ✓ M0-1 完成
│
├── docs/
│   ├── reports/
│   │   └── execution_report.md  ✓ 自动生成
│   └── plans/
│       └── [20 个任务的执行记录]
│
└── .github/
    └── workflows/
        └── ci.yml          ✓ 自动化 CI
```

---

## 7. 当前配置状况

```
✓ Git 仓库: https://github.com/zinohome/CozyEngine.git
✓ 主分支: main (已同步)
✓ 依赖: pyproject.toml (已配置)

❌ 待创建:
  - .github/workflows/ci.yml
  - backend/scripts/task_executor.py
  - backend/scripts/task_orchestrator.py

❌ 待配置:
  - GitHub branch protection rules
  - GitHub CLI token (gh auth)
```

---

## 8. 立即开始

### 🚀 **你应该对我说：**

```
"创建自动化执行脚本，启动 M0 任务"

或

"生成 CI/CD 配置，准备自动化执行"

或

"立即执行 M0-1 任务，完整的工作空间 + PR 合并流程"
```

我会：
1. ✅ 创建所有必需的脚本和配置
2. ✅ 配置 GitHub Actions
3. ✅ 启动 M0-1 工作空间
4. ✅ 等待代码推送
5. ✅ 自动验证、创建 PR、合并
6. ✅ 更新任务状态
7. ✅ 进入 M0-2...

---

**准备好了吗？** 说出你的决定！ 🚀
