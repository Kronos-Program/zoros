import json
import os
import unittest
from pathlib import Path
from unittest import mock

from source.language_service import LanguageService


class CompleteTurnTest(unittest.TestCase):
    def test_turn_output_fields(self):
        cfg = Path("turntmp") / "language_service.yml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("default_backend: lmos\nlmos:\n  url: http://host\n")
        with mock.patch("source.language_service.keyring") as keyring_mock:
            keyring_mock.get_password.return_value = "KEY"
            with mock.patch("urllib.request.urlopen") as m:
                def fake(req, timeout=0):
                    return mock.Mock(read=lambda: b'{"turn_id":"t1","content":"done"}', __enter__=lambda s: s, __exit__=lambda *a: None)

                m.side_effect = fake
                service = LanguageService(config_path=str(cfg))
                output = service.complete_turn("t1", {})
                self.assertEqual(output, {"turn_id": "t1", "content": "done"})
        cfg.unlink()
        cfg.parent.rmdir()


if __name__ == "__main__":
    unittest.main()
