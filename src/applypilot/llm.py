"""
Unified LLM client for ApplyPilot.

Auto-detects provider from environment:
  LLM_PROVIDER    -> "antigravity" (or auto-detected when agy is available)
  GEMINI_API_KEY  -> Google Gemini (default: gemini-2.0-flash)
  OPENAI_API_KEY  -> OpenAI (default: gpt-4o-mini)
  LLM_URL         -> Local llama.cpp / Ollama compatible endpoint

LLM_MODEL env var overrides the model name for any provider.
"""

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Antigravity CLI binary discovery
# ---------------------------------------------------------------------------

def find_agy_binary() -> str | None:
    """Find the path to the agy CLI executable."""
    env_agy = os.environ.get("AGY_PATH")
    if env_agy and os.path.exists(env_agy):
        return env_agy

    found = shutil.which("agy")
    if found:
        return found

    candidates = [
        Path.home() / ".local" / "bin" / "agy",
        Path.home() / "bin" / "agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)

    return None


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def _detect_provider() -> tuple[str, str, str]:
    """Return (base_url, model, api_key_or_path) based on environment variables.

    Reads env at call time (not module import time) so that load_env() called
    in _bootstrap() is always visible here.
    """
    from applypilot.config import load_env
    load_env()

    provider_override = os.environ.get("LLM_PROVIDER", "").lower()
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    local_url = os.environ.get("LLM_URL", "")
    model_override = os.environ.get("LLM_MODEL", "")

    # Explicit provider selection
    if provider_override in ("gemini", "google"):
        if gemini_key:
            return (
                "https://generativelanguage.googleapis.com/v1beta/openai",
                model_override or "gemini-3.5-flash",
                gemini_key,
            )
        raise RuntimeError("LLM_PROVIDER=gemini specified but GEMINI_API_KEY is not set.")

    if provider_override in ("openai", "gpt"):
        if openai_key:
            return (
                "https://api.openai.com/v1",
                model_override or "gpt-4o-mini",
                openai_key,
            )
        raise RuntimeError("LLM_PROVIDER=openai specified but OPENAI_API_KEY is not set.")

    if provider_override in ("local", "ollama", "llamacpp"):
        if local_url:
            return (
                local_url.rstrip("/"),
                model_override or "local-model",
                os.environ.get("LLM_API_KEY", ""),
            )
        raise RuntimeError("LLM_PROVIDER=local specified but LLM_URL is not set.")

    # Default to Antigravity if agy binary is present
    agy_path = find_agy_binary()
    if agy_path and provider_override != "api":
        return ("antigravity", model_override or "default", agy_path)

    # Fallback to API keys if agy is not available
    if gemini_key and not local_url:
        return (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            model_override or "gemini-3.5-flash",
            gemini_key,
        )

    if openai_key and not local_url:
        return (
            "https://api.openai.com/v1",
            model_override or "gpt-4o-mini",
            openai_key,
        )

    if local_url:
        return (
            local_url.rstrip("/"),
            model_override or "local-model",
            os.environ.get("LLM_API_KEY", ""),
        )

    raise RuntimeError(
        "No LLM provider configured. "
        "Set GEMINI_API_KEY, OPENAI_API_KEY, LLM_URL, or ensure Antigravity CLI (agy) is available."
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_MAX_RETRIES = 5
_TIMEOUT = 120  # seconds

# Base wait on first 429/503 (doubles each retry, caps at 60s).
# Gemini free tier is 15 RPM = 4s minimum between requests; 10s gives headroom.
_RATE_LIMIT_BASE_WAIT = 10


_GEMINI_COMPAT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
_GEMINI_NATIVE_BASE = "https://generativelanguage.googleapis.com/v1beta"


class LLMClient:
    """Thin LLM client supporting OpenAI-compatible and native Gemini endpoints.

    For Gemini keys, starts on the OpenAI-compat layer. On a 403 (which
    happens with preview/experimental models not exposed via compat), it
    automatically switches to the native generateContent API and stays there
    for the lifetime of the process.
    """

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self._client = httpx.Client(timeout=_TIMEOUT)
        # True once we've confirmed the native Gemini API works for this model
        self._use_native_gemini: bool = False
        self._is_gemini: bool = base_url.startswith(_GEMINI_COMPAT_BASE)

    # -- Native Gemini API --------------------------------------------------

    def _chat_native_gemini(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call the native Gemini generateContent API.

        Used automatically when the OpenAI-compat endpoint returns 403,
        which happens for preview/experimental models not exposed via compat.

        Converts OpenAI-style messages to Gemini's contents/systemInstruction
        format transparently.
        """
        contents: list[dict] = []
        system_parts: list[dict] = []

        for msg in messages:
            role = msg["role"]
            text = msg.get("content", "")
            if role == "system":
                system_parts.append({"text": text})
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": text}]})
            elif role == "assistant":
                # Gemini uses "model" instead of "assistant"
                contents.append({"role": "model", "parts": [{"text": text}]})

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        url = f"{_GEMINI_NATIVE_BASE}/models/{self.model}:generateContent"
        resp = self._client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            params={"key": self.api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    # -- OpenAI-compat API --------------------------------------------------

    def _chat_compat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call the OpenAI-compatible endpoint."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )

        # 403 or 404 on Gemini compat = model not available on compat layer.
        # Raise a specific sentinel so chat() can switch to native API.
        if resp.status_code in (403, 404) and self._is_gemini:
            raise _GeminiCompatForbidden(resp)

        return self._handle_compat_response(resp)

    @staticmethod
    def _handle_compat_response(resp: httpx.Response) -> str:
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # -- public API ---------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request and return the assistant message text."""
        # Qwen3 optimization: prepend /no_think to skip chain-of-thought
        # reasoning, saving tokens on structured extraction tasks.
        if "qwen" in self.model.lower() and messages:
            first = messages[0]
            if first.get("role") == "user" and not first["content"].startswith("/no_think"):
                messages = [{"role": first["role"], "content": f"/no_think\n{first['content']}"}] + messages[1:]

        for attempt in range(_MAX_RETRIES):
            try:
                # Route to native Gemini if we've already confirmed it's needed
                if self._use_native_gemini:
                    return self._chat_native_gemini(messages, temperature, max_tokens)

                return self._chat_compat(messages, temperature, max_tokens)

            except _GeminiCompatForbidden as exc:
                # Model not available on OpenAI-compat layer — switch to native.
                log.warning(
                    "Gemini compat endpoint returned %d for model '%s'. "
                    "Switching to native generateContent API. "
                    "(Preview/experimental models are often only supported via native API.)",
                    exc.response.status_code,
                    self.model,
                )
                self._use_native_gemini = True
                # Retry immediately with native — don't count as a rate-limit wait
                try:
                    return self._chat_native_gemini(messages, temperature, max_tokens)
                except httpx.HTTPStatusError as native_exc:
                    raise RuntimeError(
                        f"Both Gemini endpoints failed. Compat: {exc.response.status_code}. "
                        f"Native: {native_exc.response.status_code} — "
                        f"{native_exc.response.text[:200]}"
                    ) from native_exc

            except httpx.HTTPStatusError as exc:
                resp = exc.response
                if resp.status_code in (429, 503) and attempt < _MAX_RETRIES - 1:
                    # Respect Retry-After header if provided (Gemini sends this).
                    retry_after = (
                        resp.headers.get("Retry-After")
                        or resp.headers.get("X-RateLimit-Reset-Requests")
                    )
                    if retry_after:
                        try:
                            wait = float(retry_after)
                        except (ValueError, TypeError):
                            wait = _RATE_LIMIT_BASE_WAIT * (2 ** attempt)
                    else:
                        wait = min(_RATE_LIMIT_BASE_WAIT * (2 ** attempt), 60)

                    log.warning(
                        "LLM rate limited (HTTP %s). Waiting %ds before retry %d/%d. "
                        "Tip: Gemini free tier = 15 RPM. Consider a paid account "
                        "or switching to a local model.",
                        resp.status_code, wait, attempt + 1, _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                raise

            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES - 1:
                    wait = min(_RATE_LIMIT_BASE_WAIT * (2 ** attempt), 60)
                    log.warning(
                        "LLM request timed out, retrying in %ds (attempt %d/%d)",
                        wait, attempt + 1, _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                raise

        raise RuntimeError("LLM request failed after all retries")

    def ask(self, prompt: str, **kwargs) -> str:
        """Convenience: single user prompt -> assistant response."""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def close(self) -> None:
        self._client.close()


class AntigravityClient:
    """LLM client powered directly by the local Antigravity agent (agy CLI / SDK).

    Requires no external API keys or paid credits. Executes prompts through
    the user's authenticated Antigravity agent session.
    """

    def __init__(self, agy_path: str, model: str = "") -> None:
        self.agy_path = agy_path
        self.model = model

    def _build_prompt(self, messages: list[dict]) -> str:
        """Combine OpenAI-style messages into a clear prompt for the agent."""
        system_prompts = []
        user_prompts = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompts.append(content)
            elif role == "user":
                user_prompts.append(content)
            elif role == "assistant":
                user_prompts.append(f"Assistant previous output:\n{content}")

        if not system_prompts and len(user_prompts) == 1:
            return user_prompts[0]

        parts = []
        if system_prompts:
            parts.append("INSTRUCTIONS:\n" + "\n\n".join(system_prompts))
        if user_prompts:
            parts.append("INPUT:\n" + "\n\n".join(user_prompts))

        return "\n\n---\n\n".join(parts)

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Execute chat completion via Antigravity agent CLI."""
        prompt = self._build_prompt(messages)
        return self.ask(prompt, temperature=temperature, max_tokens=max_tokens)

    def ask(self, prompt: str, **kwargs) -> str:
        """Execute a single prompt via Antigravity agent CLI."""
        cmd = [self.agy_path, "--dangerously-skip-permissions", "--print", prompt]
        if self.model and self.model != "default":
            cmd.extend(["--model", self.model])

        for attempt in range(_MAX_RETRIES):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=_TIMEOUT,
                )
                if result.returncode == 0:
                    return result.stdout.strip()

                log.warning(
                    "Antigravity CLI returned exit code %d (attempt %d/%d): %s",
                    result.returncode,
                    attempt + 1,
                    _MAX_RETRIES,
                    result.stderr[:200] if result.stderr else result.stdout[:200],
                )
            except subprocess.TimeoutExpired:
                log.warning("Antigravity CLI call timed out (attempt %d/%d)", attempt + 1, _MAX_RETRIES)
            except Exception as e:
                log.error("Antigravity CLI execution error: %s", e)

            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))

        raise RuntimeError("Antigravity agent execution failed after retries")

    def close(self) -> None:
        pass


class _GeminiCompatForbidden(Exception):
    """Sentinel: Gemini OpenAI-compat returned 403 or 404. Switch to native API."""
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        super().__init__(f"Gemini compat {response.status_code}: {response.text[:200]}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: LLMClient | AntigravityClient | None = None


def get_client() -> LLMClient | AntigravityClient:
    """Return (or create) the module-level LLMClient or AntigravityClient singleton."""
    global _instance
    if _instance is None:
        base_url_or_provider, model, api_key_or_path = _detect_provider()
        if base_url_or_provider == "antigravity":
            log.info("LLM provider: Antigravity Agent (%s)  model: %s", api_key_or_path, model)
            _instance = AntigravityClient(agy_path=api_key_or_path, model=model)
        else:
            log.info("LLM provider: %s  model: %s", base_url_or_provider, model)
            _instance = LLMClient(base_url_or_provider, model, api_key_or_path)
    return _instance
