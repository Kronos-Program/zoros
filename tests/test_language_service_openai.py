import os
import pytest

from source.language_service import LanguageService

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_openai_complete_chat():
    svc = LanguageService()
    resp = svc.complete_chat([{"role": "user", "content": "Hello"}])
    assert "Hello" in resp
