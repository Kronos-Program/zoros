import unittest
import pytest
from datetime import datetime
from uuid import uuid4

pytest.skip("Integration test requires full model stack", allow_module_level=True)

from source.core.models.fiber import Fiber
from source.core.models.fibrizer_options import FibrizerOptions
from source.orchestration.fibrizers.chain_fibrizer import ChainFibrizer
from source.orchestration import fibrizers as chain_mod
from unittest import mock


class ChainFibrizerIntegrationTest(unittest.TestCase):
    def test_full_chain_with_embedding(self):
        content = "Sentence one. Sentence two. Sentence three. " * 4
        parent = Fiber(
            id=uuid4(),
            content=content,
            type="text",
            metadata={},
            revision_count=0,
            created_at=datetime.utcnow(),
            source="test",
        )

        responses = [
            "A. B.",
            "Short summary.",
            "Longer summary for the source level.",
            "Expanded explanation of the content.",
        ]

        class DummyService:
            def __init__(self, *a, **k):
                pass

            def complete_turn(self, turn_id, ctx):
                return {"content": responses.pop(0)}

            def embed(self, text):
                return [0.1]

        # patch LanguageService used inside fibrizer modules
        with mock.patch.object(chain_mod.chain_fibrizer, "LanguageService", DummyService):
            opts = FibrizerOptions(embed=True)
            chain = ChainFibrizer(opts)
            out = chain.fibrize(parent)

        self.assertEqual(len(out), 4)
        levels = sorted(f.metadata["fold_level"] for f in out)
        self.assertEqual(levels, [0, 1, 2, 3])
        for f in out:
            self.assertEqual(f.metadata["parent_fiber_id"], str(parent.id))
            self.assertIn("fibrizer_used", f.metadata)
            self.assertEqual(f.embeddings, [0.1])


if __name__ == "__main__":
    unittest.main()
