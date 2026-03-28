"""
Language Model configuration for DSPy prompt engineering.

Supports multiple providers via LiteLLM: OpenRouter, OpenAI, Anthropic, etc.
Loads API keys from .env files or environment variables.

Usage:
    from config import configure_lm
    configure_lm()  # uses defaults from .env
    configure_lm(provider="openai", model="gpt-4o")
"""
import os
import dspy
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv(PROJECT_ROOT / '.env.dev')

# Default provider configurations
PROVIDERS = {
    "openrouter": {
        "prefix": "openrouter/",
        "default_model": "google/gemini-2.5-pro-preview",
        "api_key_env": "OPENROUTER_API_KEY",
        "api_base": "https://openrouter.ai/api/v1",
    },
    "openai": {
        "prefix": "openai/",
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "api_base": None,
    },
    "anthropic": {
        "prefix": "anthropic/",
        "default_model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_base": None,
    },
}

DEFAULT_PROVIDER = "openai"

def configure_lm(provider: str = None, model: str = None, **kwargs):
    """
    Configure DSPy with a language model.

    Args:
        provider: Provider name (openrouter, openai, anthropic). Defaults to DEFAULT_PROVIDER.
        model: Model name. Defaults to provider's default model.
        **kwargs: Additional arguments passed to dspy.LM()
    """
    provider = provider or os.getenv("DSPY_PROVIDER", DEFAULT_PROVIDER)
    provider_config = PROVIDERS.get(provider)

    if not provider_config:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")

    model = model or os.getenv("DSPY_MODEL", provider_config["default_model"])
    api_key = os.getenv(provider_config["api_key_env"])

    if not api_key:
        raise ValueError(
            f"API key not found. Set {provider_config['api_key_env']} in your .env file or environment."
        )

    # Build model string for LiteLLM
    model_string = f"{provider_config['prefix']}{model}" if provider_config['prefix'] else model

    lm_kwargs = {
        "model": model_string,
        "api_key": api_key,
        "temperature": kwargs.pop("temperature", 0),
    }

    if provider_config["api_base"]:
        lm_kwargs["api_base"] = provider_config["api_base"]

    lm_kwargs.update(kwargs)

    lm = dspy.LM(**lm_kwargs)
    dspy.configure(lm=lm)

    print(f"Configured DSPy with {provider}/{model}")
    return lm
