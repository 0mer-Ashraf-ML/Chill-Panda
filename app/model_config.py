# app/model_config.py
"""
Model configuration for the prompt experimentation playground.

This module handles:
- Available models and their properties
- Parameter validation per model
- Dynamic parameter construction

Primarily OpenAI-compatible chat models, including OpenRouter-routed models.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    id: str
    display_name: str
    max_output_tokens: int
    context_window: int = 128000
    supports_temperature: bool = True
    supports_top_p: bool = True
    supports_frequency_penalty: bool = True
    supports_presence_penalty: bool = True
    # GPT-5 family uses max_completion_tokens instead of max_tokens
    uses_max_completion_tokens: bool = False
    # GPT-5 family supports reasoning effort
    supports_reasoning_effort: bool = False
    # Valid reasoning effort levels for this model
    reasoning_effort_levels: tuple = field(default_factory=tuple)


MODEL_ID_ALIASES: Dict[str, str] = {
    "google/gemini-3-flash": "google/gemini-3-flash-preview",
    "gemini-3-flash": "google/gemini-3-flash-preview",
    "glm-5": "z-ai/glm-5.1",
}


def resolve_model_id(model_id: str) -> str:
    """Map user-facing aliases to the actual API model id."""
    return MODEL_ID_ALIASES.get(model_id, model_id)


# Currently supported chat models
# Organized by family/provider for clarity
SUPPORTED_MODELS: Dict[str, ModelConfig] = {
    # ==================
    # GPT-4o Family
    # ==================
    "gpt-4o": ModelConfig(
        id="gpt-4o",
        display_name="GPT-4o",
        context_window=128000,
        max_output_tokens=16384,
    ),
    "gpt-4o-mini": ModelConfig(
        id="gpt-4o-mini",
        display_name="GPT-4o Mini (Cost-effective)",
        context_window=128000,
        max_output_tokens=16384,
    ),

    # ==================
    # GPT-4.1 Family
    # ==================
    "gpt-4.1": ModelConfig(
        id="gpt-4.1",
        display_name="GPT-4.1 (1M context)",
        context_window=1047576,
        max_output_tokens=32768,
    ),
    "gpt-4.1-mini": ModelConfig(
        id="gpt-4.1-mini",
        display_name="GPT-4.1 Mini (1M context)",
        context_window=1047576,
        max_output_tokens=32768,
    ),
    "gpt-4.1-nano": ModelConfig(
        id="gpt-4.1-nano",
        display_name="GPT-4.1 Nano (Fast)",
        context_window=1047576,
        max_output_tokens=16384,
    ),

    # ==================
    # GPT-5 Family
    # ==================
    "gpt-5": ModelConfig(
        id="gpt-5",
        display_name="GPT-5",
        context_window=400000,
        max_output_tokens=128000,
        uses_max_completion_tokens=True,
        supports_reasoning_effort=True,
        reasoning_effort_levels=("minimal", "low", "medium", "high"),
    ),
    "gpt-5-mini": ModelConfig(
        id="gpt-5-mini",
        display_name="GPT-5 Mini (Cost-effective)",
        context_window=400000,
        max_output_tokens=128000,
        uses_max_completion_tokens=True,
        supports_reasoning_effort=True,
        reasoning_effort_levels=("low", "medium", "high"),
    ),

    # ==================
    # GPT-5.1 Family
    # ==================
    "gpt-5.1": ModelConfig(
        id="gpt-5.1",
        display_name="GPT-5.1 (Recommended)",
        context_window=400000,
        max_output_tokens=128000,
        uses_max_completion_tokens=True,
        supports_reasoning_effort=True,
        reasoning_effort_levels=("none", "low", "medium", "high"),
    ),

    # ==================
    # GPT-5.2 Family (Latest)
    # ==================
    "gpt-5.2": ModelConfig(
        id="gpt-5.2",
        display_name="GPT-5.2 (Best Overall)",
        context_window=400000,
        max_output_tokens=128000,
        uses_max_completion_tokens=True,
        supports_reasoning_effort=True,
        reasoning_effort_levels=("none", "low", "medium", "high", "xhigh"),
    ),
    "gpt-5.2-pro": ModelConfig(
        id="gpt-5.2-pro",
        display_name="GPT-5.2 Pro (Highest Quality)",
        context_window=400000,
        max_output_tokens=128000,
        uses_max_completion_tokens=True,
        supports_reasoning_effort=True,
        reasoning_effort_levels=("medium", "high", "xhigh"),
    ),

    # ==================
    # OpenRouter Additional Models
    # ==================
    "moonshotai/kimi-k2.5": ModelConfig(
        id="moonshotai/kimi-k2.5",
        display_name="Kimi K2.5",
        context_window=128000,
        max_output_tokens=32768,
    ),
    "anthropic/claude-haiku-4.5": ModelConfig(
        id="anthropic/claude-haiku-4.5",
        display_name="Claude Haiku 4.5",
        context_window=200000,
        max_output_tokens=16384,
    ),
    "anthropic/claude-sonnet-4.6": ModelConfig(
        id="anthropic/claude-sonnet-4.6",
        display_name="Claude Sonnet 4.6 (Expensive!)",
        context_window=200000,
        max_output_tokens=16384,
    ),
    "z-ai/glm-5.1": ModelConfig(
        id="z-ai/glm-5.1",
        display_name="GLM-5.1",
        context_window=128000,
        max_output_tokens=32768,
    ),
    "qwen/qwen3.6-plus": ModelConfig(
        id="qwen/qwen3.6-plus",
        display_name="Qwen 3.6 Plus",
        context_window=1000000,
        max_output_tokens=32768,
    ),
    "deepseek/deepseek-v3.2": ModelConfig(
        id="deepseek/deepseek-v3.2",
        display_name="DeepSeek V3.2",
        context_window=163840,
        max_output_tokens=32768,
    ),
    "minimax/minimax-m2.7": ModelConfig(
        id="minimax/minimax-m2.7",
        display_name="MiniMax M2.7",
        context_window=204800,
        max_output_tokens=32768,
    ),
    "google/gemini-3-flash-preview": ModelConfig(
        id="google/gemini-3-flash-preview",
        display_name="Gemini 3 Flash",
        context_window=128000,
        max_output_tokens=32768,
    ),
    "openai/gpt-5.4": ModelConfig(
        id="openai/gpt-5.4",
        display_name="GPT-5.4",
        context_window=1050000,
        max_output_tokens=128000,
    ),
}

# Default model if none specified
DEFAULT_MODEL = "gpt-4.1-nano"


def get_model_config(model_id: str) -> Optional[ModelConfig]:
    """Get configuration for a specific model."""
    return SUPPORTED_MODELS.get(resolve_model_id(model_id))


def get_model_list() -> list[tuple[str, str]]:
    """
    Get list of available models for UI dropdown.
    Returns list of (model_id, display_name) tuples.
    """
    return [(m.id, m.display_name) for m in SUPPORTED_MODELS.values()]


def is_reasoning_model(model_id: str) -> bool:
    """Check if a model supports reasoning effort."""
    config = get_model_config(model_id)
    return config.supports_reasoning_effort if config else False


def build_api_params(
    model_id: str,
    messages: list,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    reasoning_effort: Optional[str] = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    Build API parameters dynamically based on the model's capabilities.

    This function ensures only valid parameters are passed to each model,
    preventing runtime errors when switching between models.

    Args:
        model_id: The model identifier
        messages: The messages array for the API call
        temperature: Optional temperature (0-2)
        max_tokens: Optional max output tokens
        presence_penalty: Optional presence penalty (-2 to 2)
        frequency_penalty: Optional frequency penalty (-2 to 2)
        reasoning_effort: Optional reasoning effort level (GPT-5 family)
        stream: Whether to stream the response

    Returns:
        Dict of parameters safe to pass to the OpenAI API
    """
    config = get_model_config(model_id)

    # Start with required parameters
    params: Dict[str, Any] = {
        "model": resolve_model_id(model_id),
        "messages": messages,
        "stream": stream,
    }

    if config is None:
        # Unknown model - use conservative defaults with max_tokens
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        return params

    # Add optional parameters only if the model supports them
    if config.supports_temperature and temperature is not None:
        params["temperature"] = temperature

    if config.supports_presence_penalty and presence_penalty is not None:
        params["presence_penalty"] = presence_penalty

    if config.supports_frequency_penalty and frequency_penalty is not None:
        params["frequency_penalty"] = frequency_penalty

    # Handle max tokens parameter naming
    # GPT-5 family uses max_completion_tokens, older models use max_tokens
    if max_tokens is not None:
        if config.uses_max_completion_tokens:
            params["max_completion_tokens"] = max_tokens
        else:
            params["max_tokens"] = max_tokens

    # Handle reasoning effort (GPT-5 family only)
    if config.supports_reasoning_effort and reasoning_effort is not None:
        if reasoning_effort in config.reasoning_effort_levels:
            params["reasoning_effort"] = reasoning_effort

    return params


def get_default_params_for_model(model_id: str) -> Dict[str, Any]:
    """
    Get sensible default parameters for a specific model.
    Useful for UI initialization.
    """
    config = get_model_config(model_id)

    defaults = {
        "max_tokens": 300,
        "temperature": 0.7,
    }

    if config is None:
        return defaults

    if config.supports_presence_penalty:
        defaults["presence_penalty"] = 0.3

    if config.supports_frequency_penalty:
        defaults["frequency_penalty"] = 0.3

    # Cap max_tokens to model's limit
    if config.supports_reasoning_effort:
        defaults["max_tokens"] = min(1000, config.max_output_tokens)
    else:
        defaults["max_tokens"] = min(300, config.max_output_tokens)

    # Add default reasoning effort for reasoning models
    if config.supports_reasoning_effort:
        defaults["reasoning_effort"] = (
            "none" if "none" in config.reasoning_effort_levels
            else config.reasoning_effort_levels[0]
        )

    return defaults
