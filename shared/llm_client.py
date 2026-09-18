"""
shared/llm_client.py
=====================
Thin wrapper so every agent calls one function: `call_llm(system, user)`.

- In mock mode: returns canned, realistic responses (agent modules provide
  their own mock text so this stays generic).
- In live mode: calls Anthropic Claude by default, or OpenAI if
  LLM_PROVIDER=openai. Falls back to a clear error message (not a crash)
  if the required key is missing.
"""

from .config import config


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    if not config.is_live:
        raise RuntimeError(
            "call_llm() should not be invoked directly in mock mode — "
            "agents should branch to their local mock generator instead."
        )

    if config.llm_provider == "openai":
        if not config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing in .env but MODE=live and LLM_PROVIDER=openai.")
        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content

    # default: anthropic
    if not config.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing in .env but MODE=live.")
    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    resp = client.messages.create(
        model=config.llm_model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")
