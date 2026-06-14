# 2. Agent 与 Skill 规范

## 核心职责
定义Agent和Skill的标准接口、幂等性保障机制、注册发现机制。

## Agent 需求

| 需求项 | 规格 |
|--------|------|
| 基类 | BaseAgent抽象类，提供订阅、确认、异常处理 |
| 并发模型 | 单进程异步协程，配合basicQos=1公平分发 |
| 通信 | 只与EventBus交互，不暴露HTTP端口 |
| 上下文 | 完全无状态，所有上下文由事件消息体携带 |

## Skill 需求

| 需求项 | 规格 |
|--------|------|
| 接口 | BaseSkill基类，含execute()和validate_input() |
| 输入输出 | Pydantic BaseModel，自动生成JSON Schema |
| 幂等性 | @idempotent(ttl, backend)装饰器，基于输入哈希缓存 |
| 版本管理 | version字段，不同版本缓存隔离 |
| 注册发现 | SkillRegistry，启动时自动注册 |
| 执行日志 | 自动记录skill_id、version、input_hash、execution_time、cache_hit、trace_id |

## Skill SDK模板

from agentic_framework.skill import BaseSkill, idempotent
from pydantic import BaseModel

class MySkillInput(BaseModel):
    text: str

class MySkill(BaseSkill):
    name = "my_skill"
    version = "1.0.0"
    description = "示例Skill"

    def validate_input(self, input_data: dict) -> bool:
        return MySkillInput(**input_data)

    @idempotent(ttl=3600, cache_backend="redis")
    async def execute(self, input_data: dict, parameters: dict, trace_id: str) -> dict:
        # 业务逻辑
        pass