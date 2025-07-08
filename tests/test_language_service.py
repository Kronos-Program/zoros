import json
import os
import unittest
from pathlib import Path
from unittest import mock

from source.language_service import LanguageService


class LanguageServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = mock.MagicMock()

    def _make_service(self, tmp_path: Path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        cfg = tmp_path / "language_service.yml"
        cfg.write_text(
            """default_backend: lmos
lmos:
  url: http://testserver
rate_limits:
  openai:
    rpm: 10
    retries: 1
"""
        )
        return LanguageService(config_path=str(cfg))

    def _make_openai_service(self, tmp_path: Path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        cfg = tmp_path / "language_service.yml"
        cfg.write_text(
            """default_backend: openai
backends:
  openai:
    rate_limit_per_minute: 10
"""
        )
        return LanguageService(config_path=str(cfg))

    def test_complete_chat_success(self):
        with mock.patch("source.language_service.keyring") as keyring_mock:
            keyring_mock.get_password.return_value = "TESTKEY"
            with mock.patch("urllib.request.urlopen") as m:
                svc = self._make_service(Path("temp1"))
                resp = {"choices": [{"message": {"content": "hi"}}]}

                def fake(req, timeout=0):
                    self.assertEqual(req.full_url, "http://testserver/chat/completions")
                    return mock.Mock(read=lambda: json.dumps(resp).encode(), __enter__=lambda s: s, __exit__=lambda *a: None)

                m.side_effect = fake
                out = svc.complete_chat([{"role": "user", "content": "hello"}])
                self.assertEqual(out, resp)

    def test_complete_turn_fields(self):
        with mock.patch("source.language_service.keyring") as keyring_mock:
            keyring_mock.get_password.return_value = "TESTKEY"
            with mock.patch("urllib.request.urlopen") as m:
                svc = self._make_service(Path("temp2"))
                response = {"turn_id": "123", "content": "ok"}

                def fake(req, timeout=0):
                    self.assertTrue(req.full_url.endswith("/turn/123/complete"))
                    return mock.Mock(read=lambda: json.dumps(response).encode(), __enter__=lambda s: s, __exit__=lambda *a: None)

                m.side_effect = fake
                result = svc.complete_turn("123", {"prompt": "hi"})
                self.assertEqual(result["turn_id"], "123")
                self.assertIn("content", result)

    def test_env_secret_fallback(self):
        with mock.patch("source.language_service.keyring") as keyring_mock:
            keyring_mock.get_password.return_value = None
            os.environ["OPENAI_API_KEY"] = "ENVKEY"
            cfg = Path("./tmp.yml")
            cfg.write_text("default_backend: lmos\nlmos:\n  url: http://x\n")
            svc = LanguageService(config_path=str(cfg))
            self.assertEqual(svc.api_key, "ENVKEY")
        os.remove(cfg)
        os.environ.pop("OPENAI_API_KEY")

    def test_embed_lmos(self):
        with mock.patch("source.language_service.keyring") as keyring_mock:
            keyring_mock.get_password.return_value = "TESTKEY"
            svc = self._make_service(Path("temp_embed"))
            with mock.patch.object(svc, "_post") as post_mock:
                post_mock.return_value = {"embedding": [0.1, 0.2]}
                out = svc.embed("hello")
                self.assertEqual(out, [0.1, 0.2])

    def test_embed_openai(self):
        with mock.patch("source.language_service.keyring") as keyring_mock:
            keyring_mock.get_password.return_value = "TESTKEY"
            with mock.patch("source.language_service.openai") as openai_mock:
                mock_client = mock.Mock()
                mock_resp = mock.Mock(data=[mock.Mock(embedding=[0.3, 0.4])])
                mock_client.embeddings.create.return_value = mock_resp
                openai_mock.OpenAI.return_value = mock_client
                svc = self._make_openai_service(Path("temp_openai"))
                out = svc.embed("hi")
                self.assertEqual(out, [0.3, 0.4])

    def test_embed_openai_error(self):
        with mock.patch("source.language_service.keyring") as keyring_mock:
            keyring_mock.get_password.return_value = "TESTKEY"
            with mock.patch("source.language_service.openai") as openai_mock:
                mock_client = mock.Mock()
                mock_client.embeddings.create.side_effect = RuntimeError("fail")
                openai_mock.OpenAI.return_value = mock_client
                svc = self._make_openai_service(Path("temp_openai2"))
                out = svc.embed("bad")
                self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
