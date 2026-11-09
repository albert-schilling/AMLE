
from typing import Literal

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict

client = Anthropic()

class IceCreamOrder(BaseModel):
    model_config = ConfigDict(extra="forbid") # good idea in all pydantic classes

    flavor: str
    number: int
    kind: Literal["cone", "cup"]


response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1024,
    system="you are an ice cream shop chatbot. Tell people what sort of ice cream they get",
    messages=[{"role": "user", "content": "one cone of vanilla please"}],
    tools=[
        {
            "name": "ice_cream_order",
            "description": "Record the order or an ice cream",
            "strict": True, # enable grammar-constrained sampling
            "input_schema": IceCreamOrder.model_json_schema(),
        }
    ],
    tool_choice={"type": "auto"}
)

print(response.content)
print()

result = IceCreamOrder.model_validate(response.content[0].input)
print(result)
