
from typing import Literal

from anthropic import Anthropic
from pydantic import BaseModel

client = Anthropic()

class IceCreamOrder(BaseModel):
    flavor: str
    number: int
    kind: Literal["cone", "cup"] 


response = client.messages.parse(
    model="claude-haiku-4-5",
    max_tokens=1024,
    system="you are an ice cream shop chatbot. Tell people what sort of ice cream they get",
    messages=[{"role": "user", "content": "one cone of vanilla please"}],
    output_format=IceCreamOrder
)

print(response.content)
print()

result = response.content[0].parsed_output
# IceCreamOrder.model_validate(...)
print(result)
