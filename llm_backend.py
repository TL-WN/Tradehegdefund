"""
llm_backend.py
Tiny OpenAI-compatible client. Reads config from environment (.env supported):
  LLM_API_KEY   - your API key (required to run with a real model)
  LLM_BASE_URL  - default https://api.openai.com/v1
  LLM_MODEL     - default gpt-4o-mini
If no key is set, call() raises a clear error so the bot fails safe (never fake a call).
"""
import os
from openai import OpenAI

DOTENV_LOADED = False


def _ensure_env():
    global DOTENV_LOADED
    if DOTENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    DOTENV_LOADED = True


def client():
    _ensure_env()
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "No LLM_API_KEY / OPENAI_API_KEY set. Add it to .env to let the fund "
            "consult a real model. Without it the bot will not fabricate analysis."
        )
    return OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))


def model_name():
    _ensure_env()
    return os.getenv("LLM_MODEL", "gpt-4o-mini")


def call(system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 400) -> str:
    c = client()
    resp = c.chat.completions.create(
        model=model_name(),
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


if __name__ == "__main__":
    try:
        print(call("You are a terse assistant.", "Say the word: hedge."))
    except RuntimeError as e:
        print("SAFE-FAIL:", e)
