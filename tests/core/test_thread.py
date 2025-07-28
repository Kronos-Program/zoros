import unittest
from datetime import datetime
from uuid import uuid4
from unittest import mock
import pytest

pytest.importorskip("pydantic")

from backend.core.models import thread as thread_mod
from backend.core.models.fiber import Fiber
from backend.core.models.thread import Thread


class ThreadTest(unittest.TestCase):
    def _make_thread(self) -> Thread:
        return Thread(
            id=uuid4(),
            name="T",
            fiber_ids=[],
            status="open",
            priority=3,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def _make_fiber(self, txt: str) -> Fiber:
        return Fiber(
            id=uuid4(),
            content=txt,
            type="text",
            metadata={},
            revision_count=0,
            created_at=datetime.utcnow(),
            source="unit",
        )

    def test_add_remove_reorder(self):
        th = self._make_thread()
        f1 = self._make_fiber("a")
        f2 = self._make_fiber("b")
        with mock.patch.object(thread_mod, "resolve_fiber", side_effect=[f1, f2, f1, f2]):
            th.add_fiber(f1.id)
            th.add_fiber(f2.id)
            self.assertEqual(th.fiber_ids, [f1.id, f2.id])
            th.remove_fiber(f1.id)
            self.assertEqual(th.fiber_ids, [f2.id])
            th.add_fiber(f1.id, position=0)
            self.assertEqual(th.fiber_ids, [f1.id, f2.id])
            th.reorder_fibers([f2.id, f1.id])
            self.assertEqual(th.fiber_ids, [f2.id, f1.id])
            with self.assertRaises(ValueError):
                th.reorder_fibers([f2.id])

    def test_summarize(self):
        th = self._make_thread()
        f1 = self._make_fiber("one")
        f2 = self._make_fiber("two")
        with mock.patch.object(thread_mod, "resolve_fiber", side_effect=[f1, f2]):
            th.add_fiber(f1.id)
            th.add_fiber(f2.id)
        with mock.patch.object(Fiber, "generate_summary", return_value="mix"):
            summary = th.summarize()
        self.assertEqual(summary, "mix")


if __name__ == "__main__":
    unittest.main()
