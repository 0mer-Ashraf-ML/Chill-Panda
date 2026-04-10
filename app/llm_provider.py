import os
from typing import Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI


load_dotenv()

OPENROUTER_BASE_URL_DEFAULT = "https://openrouter.ai/api/v1"


def is_openrouter_enabled() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def get_llm_provider_name() -> str:
    return "openrouter" if is_openrouter_enabled() else "openai"


def get_llm_api_key(explicit_api_key: Optional[str] = None) -> str:
    if explicit_api_key:
        return explicit_api_key
    return os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")


def get_llm_base_url() -> Optional[str]:
    if is_openrouter_enabled():
        return os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL_DEFAULT)
    return os.getenv("OPENAI_BASE_URL") or None


def get_llm_default_headers() -> Optional[dict[str, str]]:
    if not is_openrouter_enabled():
        return None

    headers: dict[str, str] = {}
    http_referer = os.getenv("OPENROUTER_HTTP_REFERER")
    if http_referer:
        headers["HTTP-Referer"] = http_referer

    app_name = os.getenv("OPENROUTER_APP_NAME", "Chill Panda")
    if app_name:
        headers["X-Title"] = app_name

    return headers or None


def get_openai_client_kwargs(explicit_api_key: Optional[str] = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "api_key": get_llm_api_key(explicit_api_key),
    }

    base_url = get_llm_base_url()
    if base_url:
        kwargs["base_url"] = base_url

    default_headers = get_llm_default_headers()
    if default_headers:
        kwargs["default_headers"] = default_headers

    return kwargs


def get_embedding_client_kwargs(explicit_api_key: Optional[str] = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "api_key": get_llm_api_key(explicit_api_key),
    }

    base_url = get_llm_base_url()
    if base_url:
        kwargs["base_url"] = base_url

    default_headers = get_llm_default_headers()
    if default_headers:
        kwargs["default_headers"] = default_headers

    return kwargs


def apply_openrouter_request_overrides(params: dict[str, Any]) -> dict[str, Any]:
    """
    Keep OpenRouter requests fast and non-reasoning by default.

    OpenRouter normalizes this setting for providers that support reasoning.
    """
    if not is_openrouter_enabled():
        return params

    updated = dict(params)
    extra_body = dict(updated.get("extra_body") or {})
    reasoning = dict(extra_body.get("reasoning") or {})
    reasoning["effort"] = "none"
    extra_body["reasoning"] = reasoning
    updated["extra_body"] = extra_body
    return updated


def create_sync_llm_client(explicit_api_key: Optional[str] = None) -> OpenAI:
    return OpenAI(**get_openai_client_kwargs(explicit_api_key))


def create_async_llm_client(explicit_api_key: Optional[str] = None) -> AsyncOpenAI:
    return AsyncOpenAI(**get_openai_client_kwargs(explicit_api_key))
