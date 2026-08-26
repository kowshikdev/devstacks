from os import getenv

from langchain_openai import ChatOpenAI


class AgentModelUnavailableError(RuntimeError):
    """Raised when the agent model is not configured."""


def build_model() -> ChatOpenAI:
    """Builds the claim-extraction/verifier model from a custom OpenAI-compatible
    endpoint (e.g. OpenRouter). LLM_BASE_URL means a provider:model shortcut
    string isn't used — deepagents accepts a preconfigured model instance too."""
    api_key = getenv("LLM_API_KEY", "")
    model_name = getenv("LLM_MODEL", "")
    base_url = getenv("LLM_BASE_URL", "")
    if not api_key or not model_name or not base_url:
        raise AgentModelUnavailableError("LLM_API_KEY, LLM_MODEL, and LLM_BASE_URL are required")
    return ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)
