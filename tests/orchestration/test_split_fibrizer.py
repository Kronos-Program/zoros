import unittest
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from unittest import mock

from source.core.models.fiber import Fiber
from source.core.models.fibrizer_options import FibrizerOptions
from source.orchestration.fibrizers.split_fibrizer import SplitFibrizer


class SplitFibrizerTest(unittest.TestCase):
    def test_split_sentences(self):
        fiber = Fiber(
            id=uuid4(),
            content="One. Two. Three.",
            type="text",
            metadata={},
            revision_count=0,
            created_at=datetime.utcnow(),
            source="unit",
        )

        tmp_dir = Path("tmp_prompt")
        tmp_dir.mkdir(exist_ok=True)
        prompt_file = tmp_dir / "split.txt"
        prompt_file.write_text("{text}")

        options = FibrizerOptions(
            fold_levels=[0],
            model_class="standard",
            embed=False,
            prompt_templates={0: str(prompt_file)},
        )

        fibrizer = SplitFibrizer(options)

        with mock.patch.object(fibrizer, "_run_model", return_value="One.\nTwo.\nThree."):
            children = fibrizer.fibrize(fiber)

        self.assertEqual(len(children), 3)
        for child in children:
            self.assertEqual(child.metadata.get("parent_fiber_id"), str(fiber.id))

        prompt_file.unlink()
        tmp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()

