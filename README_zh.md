# Constrain

<p align="center">
  <img src="./docs/images/logo-wide.png" alt="Constrain Logo" width="100%"/>
</p>

**Constrain to Unleash.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](./LICENSE)

---

## 为什么叫 Constrain？

因为我们相信：**真正的自主，源于清晰的边界。**

Constrain 不是给 Agent 无限自由，而是在确定性的边界内，赋予其最大的自主权。通过 Commander（指挥官）、Arbiter（仲裁器）、StateMachine（状态机）三大引擎，配合人造幂等、分层质量门禁与全链路可观测能力，Constrain 让 AI Agent 从"能跑"进化到"能抗能打"。

---

## 架构核心

```text
┌─────────────────────────────────────────────────┐
│                   Harness                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │Commander │  │ Arbiter  │  │ StateMachine │  │
│  │ 编排调度  │  │ 冲突裁决  │  │  状态管理     │  │
│  └─────┬────┘  └────┬─────┘  └──────┬───────┘  │
│        │            │               │           │
│  ┌─────┴────────────┴───────────────┴────────┐  │
│  │            EventBus (事件总线)              │  │
│  └─────┬──────────────────────────────┬──────┘  │
│        │                              │         │
│  ┌─────┴─────┐                ┌───────┴─────┐  │
│  │  Agent α  │      ...      │  Agent ω    │  │
│  │ ┌───────┐ │                │ ┌─────────┐ │  │
│  │ │Skills │ │                │ │ Skills  │ │  │
│  │ └───────┘ │                │ └─────────┘ │  │
│  └───────────┘                └─────────────┘  │
│        │                              │         │
│  ┌─────┴──────────────────────────────┴──────┐  │
│  │     Gate  │  Tracing  │  Skill Registry   │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 三大引擎

| 引擎 | 代号 | 职责 |
|------|------|------|
| 指挥官 | **Commander** | 解析工作流 DAG，拆分任务，发布到事件总线，不执行具体逻辑 |
| 仲裁器 | **Arbiter** | 分布式资源锁、冲突裁决、重试决策、策略热加载 |
| 状态机 | **StateMachine** | 严格约束状态转移，事件溯源持久化，支持暂停/恢复/交互等待 |

### 关键设计

- **人造幂等（Pseudo-Idempotency）**：通过参数锁定 + 输入哈希缓存，让 AI 生成任务可安全重试。
- **分层质量门禁（Gate）**：L1 硬性合规 → L2 柔性技术规范 → L3 人工创意仲裁。
- **全链路可观测（Tracing）**：基于 OpenTelemetry + Jaeger，一条 Trace ID 贯穿用户行为到 AI 推理。
- **渐进式部署**：默认安装即可单机内存运行，生产环境切换 RabbitMQ + Redis + PostgreSQL。

---

## 快速开始

### 前置要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（包管理工具）

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 初始化

```bash
# 克隆项目
cd constrain

# 创建虚拟环境并安装依赖
uv sync

# 运行测试
uv run pytest tests/ -v

# 运行 hello-world 示例
uv run python examples/hello-world/main.py
```

### Hello World

```python
import asyncio
from core.harness import Harness, HarnessConfig
from skill import BaseSkill, idempotent

class GreetingSkill(BaseSkill):
    name = "greeting"
    version = "1.0.0"

    @idempotent(ttl=3600)
    async def execute(self, input_data, parameters, trace_id):
        name = input_data.get("name", "World")
        return {"greeting": f"Hello, {name}!"}

async def main():
    forge = Harness(HarnessConfig(mode="memory"))  # 单机内存模式，零依赖
    forge.register_skill(GreetingSkill())
    await forge.start()
    run_id = await forge.execute_workflow("hello_world", {"name": "Constrain"})
    await forge.shutdown()

asyncio.run(main())
```

更多示例见 `examples/hello-world/` 目录。

---

## CLI 脚手架工具

Constrain 内置了命令行工具，用于项目脚手架搭建与日常管理。

```bash
# 查看可用命令
uv run constrain --help

# 脚手架初始化新项目
uv run constrain init my-project

# 从模板生成组件
cd my-project
uv run constrain new skill my-task
uv run constrain new agent worker
uv run constrain new workflow data-pipeline

# 列出项目已有组件
uv run constrain list skills
uv run constrain list agents
uv run constrain list workflows
```

### 命令列表

| 命令 | 说明 |
|------|------|
| `init [name]` | 初始化新项目，生成 `constrain.yaml`、`skills/`、`agents/`、`workflows/` 和 `run.py` 入口文件 |
| `new skill <name>` | 从模板生成 Skill 类 |
| `new agent <name>` | 从模板生成 Agent 类 |
| `new workflow <name>` | 从模板生成 workflow YAML 定义 |
| `list skills\|agents\|workflows` | 列出项目已有组件 |
| `run [workflow]` | 执行工作流（`--dev` 启用内存模式，`-i key=val` 传入参数） |

---

## Docker 部署

### 全栈生产环境

```bash
# 一键启动所有服务（Jaeger + Redis + RabbitMQ + PostgreSQL + App）
docker compose up -d

# 查看日志
docker compose logs -f app

# 停止并清理
docker compose down -v
```

启动后访问：
- **Jaeger UI**: http://localhost:16686
- **RabbitMQ 管理**: http://localhost:15672 (guest/guest)

### 独立构建

```bash
# 构建镜像
docker build -t constrain:latest .

# 运行自定义 agent
docker run --rm -v ./my_agent.py:/app/agent.py constrain python agent.py
```

### 生产配置

通过环境变量配置（完整参考见 `config/production.yaml`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CONSTRAIN_MODE` | 运行模式 | `memory` |
| `CONSTRAIN_BUS_BACKEND` | 事件总线 (`rabbitmq`/`memory`) | `memory` |
| `CONSTRAIN_RABBITMQ_URL` | RabbitMQ 连接字符串 | `amqp://guest:guest@localhost:5672/` |
| `CONSTRAIN_STATE_STORE_BACKEND` | 状态存储 (`postgres`/`sqlite`/`memory`) | `memory` |
| `CONSTRAIN_POSTGRES_DSN` | PostgreSQL 连接字符串 | `postgresql://user:pass@localhost:5432/constrain` |
| `CONSTRAIN_REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379/0` |
| `CONSTRAIN_TRACING_MODE` | 追踪模式 (`production`/`dev`) | `dev` |
| `CONSTRAIN_JAEGER_ENDPOINT` | Jaeger OTLP gRPC endpoint | `http://localhost:4317` |
| `CONSTRAIN_SAMPLING_RATE` | 采样率 [0,1] | `1.0` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTel 导出地址（优先级高于 Jaeger 配置） | 同 CONSTRAIN_JAEGER_ENDPOINT |

```bash
# 单容器生产模式
docker run --rm \
  -e CONSTRAIN_MODE=production \
  -e CONSTRAIN_BUS_BACKEND=rabbitmq \
  -e CONSTRAIN_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  -e CONSTRAIN_TRACING_MODE=production \
  --network constrain_default \
  constrain:latest python app.py
```

---

## 与同类框架的对比

| 特性 | Constrain | LangGraph | CrewAI | AutoGen | Temporal |
|------|-----------|-----------|--------|---------|----------|
| DAG 工作流编排 | ✅ | ✅ | 部分 | ❌ | ✅ |
| 分布式资源锁/冲突裁决 | ✅ **Arbiter** | ❌ | ❌ | ❌ | ❌ |
| 事件溯源状态机 | ✅ **StateMachine** | ✅ | ❌ | ❌ | ✅ |
| AI 人造幂等 | ✅ **内置** | ❌ | ❌ | ❌ | ❌ |
| 分层质量门禁 | ✅ **Gate** | ❌ | ❌ | ❌ | ❌ |
| 全链路 Trace（OTel + Jaeger） | ✅ **Tracing** | 部分 | ❌ | ❌ | 部分 |
| 零依赖单机模式 | ✅ | ❌ | ❌ | ❌ | ❌ |

**Constrain 的独特定位**：不是实验性 Agent 框架，而是 **AI 原生、生产就绪的 Agentic 编排中台**，填补从 Demo 到工业级落地之间的工程空白。

---

## 目录结构

```text
.
├── cli/                     # CLI 脚手架工具
│   ├── main.py              # 入口文件（click）
│   ├── templates.py         # 脚手架模板
│   └── commands/            # CLI 子命令（init, new, list, run）
├── core/                    # 核心引擎
│   ├── commander/           # 指挥官：DAG 编排引擎
│   ├── arbiter/             # 仲裁器：资源锁 + 重试 + 策略
│   ├── state_machine/       # 状态机：事件溯源 + 生命周期
│   ├── event_bus/           # 事件总线（Memory / RabbitMQ / Redis）
│   │   └── backends/
│   ├── gate/                # 分层质量门禁（L1/L2/L3）
│   ├── tracing/             # 全链路可观测（OpenTelemetry + Jaeger）
│   └── harness/             # 执行容器 + 配置 + 中间件
├── agent/                   # Agent 基类 + 注册表
├── skill/                   # Skill 基类 + @idempotent 装饰器
├── adapters/                # Redis / PostgreSQL / RabbitMQ 适配器
├── config/                  # 生产配置
│   └── production.yaml
├── examples/                # 示例项目
│   └── hello-world/
├── tests/                   # 单元测试（37 个，全部通过）
├── Dockerfile               # 多阶段构建（uv + alpine）
├── docker-compose.yml       # 全栈容器编排（6 服务）
├── pyproject.toml           # 依赖管理（uv + hatchling）
├── uv.lock                  # 锁定文件
└── .env.example             # 环境变量模板
```

---

## 贡献

欢迎提交 Issue 和 PR。详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 许可

Apache 2.0 © 2025 Constrain Contributors
