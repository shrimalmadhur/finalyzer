"""Reusable LLM client for document parsing with structured output."""

import asyncio
import json
import logging
from typing import Optional, Type, TypeVar

from litellm import acompletion
from pydantic import BaseModel, ValidationError

from backend.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ParsingError(Exception):
    """Raised when LLM-based parsing fails."""

    pass


def _get_model_name() -> str:
    """Get the appropriate model name based on provider."""
    if settings.llm_provider == "openai":
        return settings.openai_model
    else:
        return f"ollama/{settings.ollama_model}"


def _get_api_base() -> Optional[str]:
    """Get the API base URL for Ollama."""
    if settings.llm_provider == "ollama":
        return settings.ollama_host
    return None


async def llm_extract_json(
    prompt: str, response_model: Type[T], timeout: float = 30.0, max_retries: int = 3
) -> T:
    """
    Call LLM with a prompt and extract structured JSON output.

    Args:
        prompt: The prompt to send to the LLM
        response_model: Pydantic model class to parse response into
        timeout: Timeout in seconds for LLM call
        max_retries: Maximum number of retry attempts

    Returns:
        Instance of response_model with parsed data

    Raises:
        ParsingError: If LLM call fails or returns invalid JSON after all retries
    """
    for attempt in range(max_retries):
        try:
            print(f"      🔍 [llm_extract_json] Attempt {attempt + 1}/{max_retries}")
            print(f"      🔍 Model: {_get_model_name()}, Provider: {settings.llm_provider}")

            response = await acompletion(
                model=_get_model_name(),
                messages=[{"role": "user", "content": prompt}],
                api_base=_get_api_base(),
                api_key=settings.openai_api_key if settings.llm_provider == "openai" else None,
                temperature=0.1,  # Low temperature for consistency
                max_tokens=4096,  # Allow longer responses for transaction lists
                timeout=timeout,
            )

            print("      ✅ [llm_extract_json] Got LLM response")
            content = response.choices[0].message.content.strip()

            # Extract JSON from markdown code blocks if present
            # Handle both "```json" and "```" styles, and text before the block
            if "```" in content:
                # Find the JSON content between ``` markers
                parts = content.split("```")
                if len(parts) >= 3:
                    # Get the content between first ``` and second ```
                    json_content = parts[1]
                    # Remove language identifier (e.g., "json\n")
                    if json_content.lstrip().startswith("json"):
                        json_content = json_content.lstrip()[4:]
                    content = json_content.strip()
                elif len(parts) == 2:
                    # Only one ``` marker (incomplete response)
                    content = parts[1].strip()

            # Additional cleanup: remove any leading/trailing non-JSON text
            # Find first { or [
            json_start = min(
                content.find("{") if "{" in content else len(content),
                content.find("[") if "[" in content else len(content)
            )
            if json_start > 0 and json_start < len(content):
                content = content[json_start:]

            # Parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from LLM (attempt {attempt + 1}/{max_retries})")
                logger.error(f"Error: {e}")
                logger.error(f"Content preview: {content[:200]}...")
                logger.error(f"Content length: {len(content)} chars")

                # Check if response seems truncated
                if len(content) > 0 and not content.rstrip().endswith("}"):
                    logger.error("Response appears truncated (doesn't end with })")

                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise ParsingError(f"LLM returned invalid JSON: {e}")

            # Validate with Pydantic model
            try:
                return response_model.model_validate(data)
            except ValidationError as e:
                logger.error(f"Pydantic validation failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ParsingError(f"LLM response validation failed: {e}")

        except TimeoutError:
            logger.warning(f"LLM timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise ParsingError(f"LLM call timed out after {max_retries} attempts")

        except Exception as e:
            logger.error(f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise ParsingError(f"LLM call failed: {e}")

    # Should never reach here
    raise ParsingError("Unexpected error in llm_extract_json")
