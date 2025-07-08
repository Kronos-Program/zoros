import unittest
from datetime import datetime
from uuid import uuid4
from unittest import mock
import pytest

pytest.importorskip("pydantic")

from source.core.models.fiber import Fiber, TransformOptions


class FiberTest(unittest.TestCase):
    def _make_fiber(self) -> Fiber:
        return Fiber(
            id=uuid4(),
            content="Hello World",
            type="text",
            metadata={},
            revision_count=0,
            created_at=datetime.utcnow(),
            source="unit",
        )

    def test_json_round_trip(self):
        f = self._make_fiber()
        f.add_tag("One")
        data = f.to_json()
        loaded = Fiber(
            id=data["id"],
            content=data["content"],
            type=data["type"],
            embeddings=data["embeddings"],
            metadata=data["metadata"],
            revision_count=data["revision_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
            source=data["source"],
            tags=data["tags"],
        )
        self.assertEqual(loaded.tags, ["one"])
        self.assertEqual(loaded.content, f.content)

    def test_transform_summary(self):
        f = self._make_fiber()
        with mock.patch.object(Fiber, "generate_summary", return_value="short"):
            out = f.transform("summary", TransformOptions())
        self.assertEqual(out.content, "short")
        self.assertEqual(out.revision_count, 1)
        self.assertNotEqual(out.id, f.id)

    def test_transform_translation(self):
        f = self._make_fiber()
        out = f.transform("translation", TransformOptions(language="fr"))
        self.assertTrue(out.content.startswith("[fr]"))

    def test_transform_tag_extract(self):
        f = self._make_fiber()
        out = f.transform("tag_extract", TransformOptions(tags=["A", "b"]))
        self.assertIn("a", out.tags)
        self.assertIn("b", out.tags)

    def test_tag_add_remove(self):
        f = self._make_fiber()
        f.add_tag("Test")
        f.add_tag("test")
        self.assertEqual(f.tags, ["test"])
        f.remove_tag("TEST")
        self.assertEqual(f.tags, [])

    def test_generate_summary_fallback(self):
        f = self._make_fiber()
        summary = f.generate_summary()
        self.assertEqual(summary, "Hello World"[:128])

    def test_generate_summary_service(self):
        f = self._make_fiber()
        fake_resp = {"content": "service summary"}
        with mock.patch("source.language_service.LanguageService") as svc:
            svc.return_value.complete_turn.return_value = fake_resp
            out = f.generate_summary()
        self.assertEqual(out, "service summary")


if __name__ == "__main__":
    unittest.main()
