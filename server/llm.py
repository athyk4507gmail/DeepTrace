import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def call_gemini(
    prompt: str,
    system_prompt: str = None,
    model_name: str = "llama-3.3-70b-versatile",
    max_tokens: int = 2048
) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

async def call_gemini_json(
    prompt: str,
    system_prompt: str = None,
) -> str:
    json_system = (system_prompt or "") + \
        "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, \n         no backticks, no explanation."
    return await call_gemini(prompt, json_system)
