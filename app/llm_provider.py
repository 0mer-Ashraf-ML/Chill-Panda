import os
from typing import Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI


load_dotenv()

OPENROUTER_BASE_URL_DEFAULT = "https://openrouter.ai/api/v1"
OPENAI_REASONING_MODEL_PREFIXES = (
    "gpt-5",
    "openai/gpt-5",
)
OPENROUTER_MODEL_PREFIXES = (
    "anthropic/",
    "deepseek/",
    "google/",
    "minimax/",
    "moonshotai/",
    "openai/",
    "qwen/",
    "z-ai/",
)
OPENROUTER_MODEL_ALIASES = {
    "claude-haiku-4.5",
    "claude-sonnet-4.6",
    "deepseek-v3.2",
    "gemini-3-flash",
    "glm-5.1",
    "glm-5",
    "gpt-5.4",
    "kimi-k2.5",
    "minimax-m2.7",
    "qwen3.6-plus",
}


def should_route_model_to_openrouter(model: Optional[str] = None) -> bool:
    """Route explicit playground/provider model ids through OpenRouter."""
    if not model:
        return False

    model_id = str(model)
    return (
        model_id in OPENROUTER_MODEL_ALIASES
        or model_id.startswith(OPENROUTER_MODEL_PREFIXES)
    )


def is_openrouter_enabled(model: Optional[str] = None) -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY")) and should_route_model_to_openrouter(model)


def get_llm_provider_name(model: Optional[str] = None) -> str:
    return "openrouter" if is_openrouter_enabled(model) else "openai"


def get_llm_api_key(
    explicit_api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    if explicit_api_key:
        return explicit_api_key
    if get_llm_provider_name(model) == "openrouter":
        return os.getenv("OPENROUTER_API_KEY", "")
    return os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")


def get_llm_base_url(model: Optional[str] = None) -> Optional[str]:
    if get_llm_provider_name(model) == "openrouter":
        return os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL_DEFAULT)
    return os.getenv("OPENAI_BASE_URL") or None


def get_llm_default_headers(model: Optional[str] = None) -> Optional[dict[str, str]]:
    if get_llm_provider_name(model) != "openrouter":
        return None

    headers: dict[str, str] = {}
    http_referer = os.getenv("OPENROUTER_HTTP_REFERER")
    if http_referer:
        headers["HTTP-Referer"] = http_referer

    app_name = os.getenv("OPENROUTER_APP_NAME", "Chill Panda")
    if app_name:
        headers["X-Title"] = app_name

    return headers or None


def get_openai_client_kwargs(
    explicit_api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "api_key": get_llm_api_key(explicit_api_key, model),
    }

    base_url = get_llm_base_url(model)
    if base_url:
        kwargs["base_url"] = base_url

    default_headers = get_llm_default_headers(model)
    if default_headers:
        kwargs["default_headers"] = default_headers

    return kwargs


def get_embedding_client_kwargs(
    explicit_api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "api_key": get_llm_api_key(explicit_api_key, model),
    }

    base_url = get_llm_base_url(model)
    if base_url:
        kwargs["base_url"] = base_url

    default_headers = get_llm_default_headers(model)
    if default_headers:
        kwargs["default_headers"] = default_headers

    return kwargs


def apply_openrouter_request_overrides(params: dict[str, Any]) -> dict[str, Any]:
    """
    Keep OpenRouter requests fast and non-reasoning by default.

    OpenRouter normalizes this setting for providers that support reasoning.
    """
    model = str(params.get("model") or "")
    if not is_openrouter_enabled(model):
        return params

    if model.startswith("minimax/") or model.startswith(OPENAI_REASONING_MODEL_PREFIXES):
        return params

    updated = dict(params)
    extra_body = dict(updated.get("extra_body") or {})
    reasoning = dict(extra_body.get("reasoning") or {})
    reasoning["effort"] = "none"
    extra_body["reasoning"] = reasoning
    updated["extra_body"] = extra_body
    return updated


def create_sync_llm_client(
    explicit_api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> OpenAI:
    return OpenAI(**get_openai_client_kwargs(explicit_api_key, model))


def create_async_llm_client(
    explicit_api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> AsyncOpenAI:
    return AsyncOpenAI(**get_openai_client_kwargs(explicit_api_key, model))
