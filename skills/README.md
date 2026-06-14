# Custom Skills Directory

Place your Python skill modules here. The Harness auto-discovers
`BaseSkill` subclasses by scanning `.py` files in this directory.

Example: `skills/greeting.py`

```python
from skill import BaseSkill, idempotent

class GreetingSkill(BaseSkill):
    name = "greeting"
    version = "1.0.0"

    @idempotent(ttl=3600)
    async def execute(self, input_data, parameters, trace_id):
        name = input_data.get("name", "World")
        return {"greeting": f"Hello, {name}!"}
```
