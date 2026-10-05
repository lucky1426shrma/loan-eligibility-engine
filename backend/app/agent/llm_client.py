from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class GeminiAgentClient:
    """
    Wrapper for Google GenAI (Gemini) API with tool-calling capabilities.
    Activated when GEMINI_API_KEY is available.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize GenAI client: {e}")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def generate_agent_turn(
        self,
        system_instruction: str,
        messages: List[Dict[str, Any]],
        tools_declarations: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Executes a turn with Gemini.
        Returns function calls or text reply.
        """
        if not self.is_available:
            return None

        try:
            from google.genai import types

            # Format tool declarations for google-genai SDK
            # Note: SDK types.Tool or function_declarations
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0, # zero temperature for determinism
            )

            # Build prompt contents
            prompt_parts = []
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                prompt_parts.append(f"{role.upper()}: {content}")

            prompt = "\n".join(prompt_parts)
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            return {
                "text": response.text if hasattr(response, "text") else "",
                "usage": {
                    "total_tokens": getattr(response.usage_metadata, "total_token_count", 0)
                    if hasattr(response, "usage_metadata")
                    else 0
                },
            }
        except Exception as e:
            logger.error(f"Gemini API execution error: {e}")
            return None
