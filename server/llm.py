import os
from cerebras.cloud.sdk import Cerebras

client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))

async def call_gemini(
    prompt: str,
    system_prompt: str = None,
    model_name: str = "llama3.1-8b",
    max_tokens: int = 2048
) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="llama3.1-8b",
        messages=messages,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

async def call_gemini_json(
    prompt: str,
    system_prompt: str = None,
) -> str:
    json_system = (system_prompt or "") + \
        "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no backticks, no explanation."
    response = await call_gemini(prompt, json_system, max_tokens=3000)
    # Clean markdown if present
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    return response.strip()
