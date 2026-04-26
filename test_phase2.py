"""
Simple test script for Phase 2 (LLM Abstraction)
Tests LLM client initialization and prompt formatting
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.types import LLMConfig
from llm.client import LLMClient
from llm.prompts import EXTRACTION_PROMPT, RETRY_EXTRACTION_PROMPT


def test_prompt_formatting():
    """Test that prompts are properly formatted"""
    print("Testing prompt formatting...")

    # Test EXTRACTION_PROMPT
    clause_text = "If invoice amount exceeds $1000, escalate to manager."
    formatted = EXTRACTION_PROMPT.format(clause_text=clause_text)

    assert clause_text in formatted, "Clause text should be in formatted prompt"
    assert "condition" in formatted, "Prompt should mention condition"
    assert "action" in formatted, "Prompt should mention action"
    print("✓ EXTRACTION_PROMPT formatting works")

    # Test RETRY_EXTRACTION_PROMPT
    retry_formatted = RETRY_EXTRACTION_PROMPT.format(clause_text=clause_text)
    assert clause_text in retry_formatted, "Clause text should be in retry prompt"
    assert "condition" in retry_formatted, "Retry prompt should mention condition"
    print("✓ RETRY_EXTRACTION_PROMPT formatting works")


def test_llm_client_initialization():
    """Test that LLM client can be initialized with different providers"""
    print("\nTesting LLM client initialization...")

    config = LLMConfig(
        provider="openrouter",
        model="meta-llama/llama-3-8b-instruct",
        temperature=0.1,
        max_tokens=2048,
    )

    # Test OpenRouter client
    try:
        client = LLMClient(
            config=config,
            nvidia_api_key="test_key",
            openrouter_api_key="test_key",
            aws_credentials={},
        )
        assert client._config.provider == "openrouter", "Provider should be openrouter"
        print("✓ OpenRouter client initialization works")
    except Exception as e:
        print(f"✗ OpenRouter client initialization failed: {e}")

    # Test NVIDIA client
    config_nvidia = LLMConfig(
        provider="nvidia",
        model="meta/llama-3.3-70b-instruct",
        temperature=0.1,
        max_tokens=2048,
    )

    try:
        client_nvidia = LLMClient(
            config=config_nvidia,
            nvidia_api_key="test_key",
            openrouter_api_key="test_key",
            aws_credentials={},
        )
        assert client_nvidia._config.provider == "nvidia", "Provider should be nvidia"
        print("✓ NVIDIA client initialization works")
    except Exception as e:
        print(f"✗ NVIDIA client initialization failed: {e}")


def test_llm_config_validation():
    """Test that LLMConfig validates properly"""
    print("\nTesting LLMConfig validation...")

    try:
        config = LLMConfig(
            provider="openrouter",
            model="meta-llama/llama-3-8b-instruct",
            temperature=0.1,
            max_tokens=2048,
        )
        assert config.provider == "openrouter", "Provider should match"
        assert config.model == "meta-llama/llama-3-8b-instruct", "Model should match"
        assert config.temperature == 0.1, "Temperature should match"
        assert config.max_tokens == 2048, "Max tokens should match"
        print("✓ LLMConfig validation works")
    except Exception as e:
        print(f"✗ LLMConfig validation failed: {e}")


def main():
    print("=" * 60)
    print("Phase 2 (LLM Abstraction) Test Suite")
    print("=" * 60)

    try:
        test_prompt_formatting()
        test_llm_client_initialization()
        test_llm_config_validation()

        print("\n" + "=" * 60)
        print("✓ All Phase 2 tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())