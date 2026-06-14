# 0. 总览与技术选型

## 项目定位
面向**生产级多Agent协作场景**的轻量编排框架，以“约束下的自治”为核心设计理念。

**核心差异化**：
- 不是给Agent无限自由，而是在确定性框架内赋予自主权
- 针对AI输出不确定性，提供“人造幂等”工程方案
- 将质量保障作为架构一等公民，而非事后审核

## 整体技术选型

| 组件 | 生产环境 | 开发/单机模式 |
|------|----------|---------------|
| 事件总线 | RabbitMQ（公平分发，basicQos=1，手动确认） | 内存 asyncio.Queue |
| 缓存与锁 | Redis（分布式锁 + 幂等缓存） | 内存 dict + asyncio.Lock |
| 状态存储 | PostgreSQL（事件日志） | SQLite |
| 可观测 | OpenTelemetry → OTLP Collector | 本地结构化日志 |
| API层 | FastAPI | 同左 |
| 数据模型 | Pydantic v2 | 同左 |
| 异步运行时 | asyncio + AnyIO | 同左 |

## 目录结构
agentic-framework/
├── core/
│   ├── commander/          # → 1.1-commander.md
│   ├── arbiter/            # → 1.2-arbiter.md
│   ├── state_machine/      # → 1.3-state-machine.md
│   ├── event_bus/          # → 1.4-event-bus.md
│   ├── gate/               # → 1.5-gate-evaluator.md
│   ├── tracing/            # → 1.6-tracing.md
│   └── harness/            # → 1.7-harness.md
├── agent/                  # → 2-agent-skill.md
├── adapters/               # RabbitMQ、Redis、PostgreSQL适配器
├── contrib/                # Grafana模板、CLI脚手架
├── examples/hello-world/   # 单文件可运行示例
├── tests/
└── docs/

## 代码生成总要求
- 零业务耦合：不出现任何具体业务术语
- 接口优于实现：核心组件优先定义抽象基类
- 可测试性：预留Mock接口
- 渐进式复杂度：默认安装即可单机内存运行
- 文档注释：所有公开API有Google风格docstring