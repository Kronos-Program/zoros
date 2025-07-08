
# See architecture: docs/zoros_architecture.md#component-overview
import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional

import json
from urllib import request as urlrequest
from urllib.error import URLError

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    genai = None

try:
    import openai  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    openai = None

try:
    import keyring  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    keyring = None

def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
def _load_simple_yaml(path: Path) -> Dict:
    root: Dict = {}
    stack = [root]
    last_indent = 0
    last_key = None
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip())
            key, _, val = raw.strip().partition(":")
            val = val.strip()
            if indent > last_indent:
                stack.append(stack[-1][last_key])
            while indent < last_indent:
                stack.pop()
                last_indent -= 2
            current = stack[-1]
            if val:
                parsed: Any
                if val.startswith("{") or val.startswith("["):
                    try:
                        parsed = json.loads(val)
                    except Exception:
                        parsed = val
                elif val.lower() in {"true", "false"}:
                    parsed = val.lower() == "true"
                elif val.isdigit():
                    parsed = int(val)
                else:
                    parsed = val
                current[key] = parsed
            else:
                current[key] = {}
            last_indent = indent
            last_key = key
    return root


class RateLimiter:
    """Simple token bucket rate limiter for requests per minute."""

    def __init__(self, rpm: int) -> None:
        self.rpm = max(1, rpm)
        self.tokens = self.rpm
        self.updated = time.monotonic()

    def acquire(self) -> None:
        now = time.monotonic()
        elapsed = now - self.updated
        self.updated = now
        self.tokens = min(self.rpm, self.tokens + elapsed * self.rpm / 60)
        if self.tokens < 1:
            sleep_for = (1 - self.tokens) * 60 / self.rpm
            time.sleep(sleep_for)
            self.tokens = 0
        self.tokens -= 1


class LanguageService:
    """LanguageService wrapper.

    Example
    -------
    >>> svc = LanguageService()
    >>> svc.complete_chat([{"role": "user", "content": "Hello"}])
    'Hello...'
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        cfg_path = (
            Path(config_path)
            if config_path
            else Path(__file__).parent / "config" / "language_service.yml"
        )
        self.config = _load_simple_yaml(cfg_path)

        self.default_backend = self.config.get("default_backend", "lmos")

        self._retries = int(self.config.get("rate_limits", {}).get("openai", {}).get("retries", 3))
        self._limiter = RateLimiter(int(self.config.get("rate_limits", {}).get("openai", {}).get("rpm", 60)))

        if self.default_backend == "openai":
            self.api_key = self._resolve_openai_key()
            if openai is None:
                raise RuntimeError("openai package not available")
            backend_cfg = self.config.get("backends", {}).get("openai", {})
            rpm = int(backend_cfg.get("rate_limit_per_minute", 60))
            self._limiter = RateLimiter(rpm)
            self._client = openai.OpenAI(api_key=self.api_key)
        elif self.default_backend == "gemini":
            self.api_key = self._resolve_gemini_key()
            if genai is None:
                raise RuntimeError("google.generativeai package not available")
            genai.configure(api_key=self.api_key)
            backend_cfg = self.config.get("backends", {}).get("gemini", {})
            rpm = int(backend_cfg.get("rate_limit_per_minute", 60))
            self._limiter = RateLimiter(rpm)
            self._client = genai.GenerativeModel('gemini-pro')
        else:
            self.api_key = self._resolve_api_key()
            self._backend_url = self.config[self.default_backend]["url"].rstrip("/")

    @staticmethod
    def _resolve_api_key() -> str:
        """Resolve LMOS API key from keyring or environment."""
        key = None
        if keyring:
            try:
                key = keyring.get_password("zoros", "OPENAI_API_KEY")
            except Exception:
                key = None
        if not key:
            load_dotenv()
            key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not found in keyring or .env")
        return key

    @staticmethod
    def _resolve_openai_key() -> str:
        """Resolve OpenAI API key from keyring or environment."""
        key = None
        if keyring:
            try:
                key = keyring.get_password("openai", "api_key")
            except Exception:
                key = None
        if not key:
            load_dotenv()
            key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not found in keyring or environment")
        return key

    @staticmethod
    @staticmethod
    def _resolve_gemini_key() -> str:
        """Resolve Gemini API key from keyring or environment."""
        key = None
        if keyring:
            try:
                key = keyring.get_password("gemini", "api_key")
            except Exception:
                key = None
        if not key:
            load_dotenv()
            key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not found in keyring or environment")
        return key

    def _post(self, route: str, payload: Dict) -> Dict:
        data = json.dumps(payload).encode()
        for attempt in range(self._retries + 1):
            self._limiter.acquire()
            req = urlrequest.Request(
                f"{self._backend_url}{route}",
                data=data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlrequest.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except URLError:
                if attempt >= self._retries:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Request failed")

    def complete_chat(self, messages: List[Dict], **kwargs) -> str:
        """Chat completion via configured backend."""
        if self.default_backend == "openai":
            self._limiter.acquire()
            resp = self._client.chat.completions.create(
                model=kwargs.get("model", "gpt-4o"),
                messages=messages,
                **kwargs,
            )
            return resp.choices[0].message.content
        elif self.default_backend == "gemini":
            self._limiter.acquire()
            # Gemini uses a different message format, so we need to adapt it
            gemini_messages = []
            for message in messages:
                role = 'user' if message['role'] == 'user' else 'model'
                gemini_messages.append({'role': role, 'parts': [{'text': message['content']}]})

            resp = self._client.generate_content(gemini_messages)
            return resp.text
        return self._post("/chat/completions", {"messages": messages})

    def complete_turn(self, turn_id: str, context: Dict) -> Dict:
        """Complete a Turn via LMOS Router."""
        return self._post(f"/turn/{turn_id}/complete", {"context": context})

    def embed(self, text: str) -> List[float]:
        """Return an embedding vector for ``text`` using the configured backend."""
        if self.default_backend == "openai":
            if openai is None:
                raise RuntimeError("openai package not available")
            try:
                self._limiter.acquire()
                resp = self._client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=text,
                )
                return list(resp.data[0].embedding)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - network failure
                logging.warning("OpenAI embed failed: %s", exc)
                return []
        try:
            data = self._post("/embeddings", {"input": text})
        except Exception as exc:  # pragma: no cover - network failure
            logging.warning("LMOS embed failed: %s", exc)
            return []
        emb = data.get("embedding", [])
        return emb if isinstance(emb, list) else []
