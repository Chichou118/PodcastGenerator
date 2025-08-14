import os

def get_llm_provider(cfg: dict) -> str:
    return (cfg or {}).get("provider", "openai")

def get_llm_model(cfg: dict) -> str:
    return (cfg or {}).get("model", "gpt-4o-mini")

def get_api_key() -> str:
    # Prefer OPENAI_API_KEY but allow others; adjust as needed
    return os.getenv("OPENAI_API_KEY") or os.getenv("MISTRAL_API_KEY") or ""