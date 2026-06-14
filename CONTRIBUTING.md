# 贡献指南

欢迎参与 Constrain 的开发！本文档涵盖了开发环境搭建、代码规范、测试流程和 PR 提交流程。

---

## 开发环境

### 前置要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（包管理工具）

### 初始化

```bash
# 克隆仓库
git clone https://github.com/your-org/constrain
cd constrain

# 创建虚拟环境并安装所有依赖（包括开发依赖）
uv sync

# 激活虚拟环境
source .venv/bin/activate

# 验证安装
uv run pytest tests/ -v
```

---

## 开发工作流

### 分支策略

- `main` — 稳定版本，始终保持可发布状态
- `feat/*` — 新功能分支
- `fix/*` — 缺陷修复分支
- `refactor/*` — 重构分支

```bash
# 从 main 创建功能分支
git checkout -b feat/my-feature main
```

### 开发循环

```bash
# 1. 确保虚拟环境激活
source .venv/bin/activate

# 2. 编写代码

# 3. 运行测试
uv run pytest tests/ -v

# 4. 检查代码风格（如果安装了 ruff）
uv run ruff check .
```

### 提交规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <description>

[optional body]
```

**type** 包括：
- `feat` — 新功能
- `fix` — 缺陷修复
- `refactor` — 重构
- `test` — 测试相关
- `docs` — 文档
- `chore` — 构建/工具链

**scope** 包括：
- `commander` — 指挥官引擎
- `arbiter` — 仲裁器引擎
- `state-machine` — 状态机引擎
- `event-bus` — 事件总线
- `gate` — 门禁评估器
- `tracing` — 全链路可观测
- `harness` — 执行容器
- `agent` — Agent 模块
- `skill` — Skill 模块
- `adapters` — 适配器
- `docker` — 容器部署
- `docs` — 文档

示例：

```
feat(commander): 支持扇出-扇入模式的动态 Task 注入

在运行时 Workflow 执行过程中，允许动态插入新的 Task 节点到 DAG，
支持 fan-out/fan-in 模式的动态扩缩。
```

---

## 代码规范

### 风格指南

- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/) 规范
- 行长度不超过 100 字符（由 ruff 强制执行）
- 使用 `ruff` 进行代码检查：

```bash
uv run ruff check .
```

### 类型注解

所有公共 API 必须包含完整的类型注解：

```python
# 正确
async def execute(self, input_data: dict[str, Any], parameters: dict[str, Any], trace_id: str) -> dict[str, Any]:
    ...

# 错误（缺少返回类型注解）
async def execute(self, input_data, parameters, trace_id):
    ...
```

### 文档注释

所有公开 API 使用 Google 风格的 docstring：

```python
def submit_workflow(self, workflow_def: WorkflowDef, input_data: dict[str, Any]) -> str:
    """Submit a workflow definition for execution.

    Args:
        workflow_def: The workflow DAG definition.
        input_data: Global input data available to all tasks.

    Returns:
        The unique run_id for tracking execution progress.
    """
```

### 导入顺序

按以下顺序分组，每组间空一行：

1. `from __future__ import annotations`
2. 标准库（`asyncio`, `logging`, `abc` 等）
3. 第三方库（`pydantic`, `yaml` 等）
4. 项目内部（`core.*`, `skill.*`, `agent.*` 等）

---

## 测试指南

### 运行所有测试

```bash
uv run pytest tests/ -v
```

### 运行特定测试文件

```bash
uv run pytest tests/test_tracing.py -v
```

### 运行特定测试

```bash
uv run pytest tests/test_tracing.py::TestTracerDevMode::test_start_span -v
```

### 测试要求

- **新功能必须包含测试**：覆盖率不应低于改动前
- 所有测试使用 `pytest` 和 `pytest-asyncio`
- 异步测试使用 `asyncio_mode = "auto"`（已在 `pyproject.toml` 中配置）
- 核心模块的测试不应依赖外部服务（Redis、RabbitMQ、PostgreSQL）

### 测试文件命名

```
tests/
├── test_commander.py
├── test_arbiter.py
├── test_state_machine.py
├── test_event_bus.py
├── test_gate.py
├── test_tracing.py
├── test_skill.py
└── test_harness.py
```

---

## 模块设计原则

### 接口优于实现

核心组件优先定义抽象基类（ABC），具体实现在子类或适配器中：

```python
class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: Event, routing_key: str) -> None: ...

class MemoryEventBus(EventBus):  # 开发/测试
    ...

class RabbitMQEventBus(EventBus):  # 生产
    ...
```

### 零业务耦合

核心模块不出现任何具体业务术语。业务逻辑仅在 Skill 中实现。

### 渐进式复杂度

- **默认**：MemoryEventBus + dict/SQLite 存储，零外部依赖即可运行
- **生产**：RabbitMQ + Redis + PostgreSQL，通过配置切换

### 可测试性

所有外部依赖通过抽象接口注入，便于 Mock：

```python
class StateMachine:
    def __init__(self, store: StateStore | None = None):
        self._store = store or InMemoryStateStore()  # 默认轻量实现
```

---

## PR 提交流程

1. 确保所有测试通过：`uv run pytest tests/ -v`
2. 确保代码风格合规：`uv run ruff check .`
3. 提交 commit 遵循 Conventional Commits 规范
4. 推送到你的 fork 并创建 Pull Request
5. PR 标题使用相同规范，例如 `feat(commander): support fan-out/fan-in pattern`
6. 在 PR 描述中说明：
   - **背景**：为什么要做这个改动
   - **改动内容**：改了什么、怎么改的
   - **测试方式**：如何验证改动正确

---

## 项目结构速查

| 目录 | 职责 | 关键文件 |
|------|------|---------|
| `core/commander/` | DAG 编排引擎 | `engine.py`, `scheduler.py`, `models.py` |
| `core/arbiter/` | 资源锁 + 策略仲裁 | `arbiter.py`, `policies.py`, `models.py` |
| `core/state_machine/` | 事件溯源状态机 | `machine.py`, `models.py` |
| `core/event_bus/` | 事件发布/订阅 | `base.py`, `models.py`, `backends/*` |
| `core/gate/` | 分层质量门禁 | `pipeline.py`, `models.py` |
| `core/tracing/` | OTel + Jaeger 可观测 | `tracer.py`, `context.py`, `exporters.py` |
| `core/harness/` | 执行容器 + 中间件 | `harness.py`, `config.py`, `middleware.py` |
| `agent/` | Agent 基类 | `base.py`, `registry.py` |
| `skill/` | Skill 基类 + 幂等 | `base.py`, `decorators.py`, `registry.py` |
| `adapters/` | 外部服务适配器 | `redis.py`, `postgres.py` |

---

## 问题反馈

提交 Issue 时请包含：
- 问题的清晰描述
- 复现步骤（代码片段 + 错误输出）
- 环境信息（Python 版本、操作系统）
- 如果是功能请求，请描述使用场景

---

感谢你的贡献！
