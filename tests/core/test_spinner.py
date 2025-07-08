from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import pytest

pytest.importorskip("pydantic")

from source.core.models.fiber import Fiber
from source.orchestration.spinner import Spinner


class SpinnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = os.path.abspath("tmp_test")
        os.makedirs(self.tmp, exist_ok=True)
        os.environ["DATA_DIR"] = self.tmp
        self.spinner = Spinner("unit")

    def tearDown(self) -> None:
        for root, _dirs, files in os.walk(self.tmp):
            for f in files:
                os.remove(os.path.join(root, f))

    def _make_fiber(self, text: str) -> Fiber:
        return Fiber(
            id=uuid4(),
            content=text,
            type="text",
            metadata={},
            revision_count=0,
            created_at=datetime.utcnow(),
            source="unit",
        )

    def test_spin_single(self) -> None:
        f = self._make_fiber("a")
        th = self.spinner.spin(f)
        self.assertEqual(th.fiber_ids, [f.id])
        self.assertEqual(th.tags, ["spun"])
        self.assertEqual(th.metadata["source_fiber_ids"], [f.id])
        path = (
            Path(self.tmp) / "snapshots" / "threads" / f"{th.id}.json"
        )
        data = json.loads(path.read_text())
        self.assertEqual(data["fiber_ids"], [str(f.id)])
        self.assertEqual(data["metadata"]["spin_fiber_id"], str(th.metadata["spin_fiber_id"]))

    def test_batch_spin(self) -> None:
        f1 = self._make_fiber("a")
        f2 = self._make_fiber("b")
        f3 = self._make_fiber("c")
        out = self.spinner.batch_spin([[f1, f2], f3])
        self.assertEqual(len(out), 2)
        self.assertEqual(set(out[0].fiber_ids), {f1.id, f2.id})
        self.assertEqual(out[1].fiber_ids, [f3.id])

    def test_batch_spin_error(self) -> None:
        f = self._make_fiber("a")
        out = self.spinner.batch_spin(["bad", f])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].fiber_ids, [f.id])


if __name__ == "__main__":
    unittest.main()
