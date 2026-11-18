from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ecosim.knowledge import build_knowledge_index, load_knowledge_index, search_knowledge


class KnowledgeTests(unittest.TestCase):
    def test_build_and_search_knowledge_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            (base_dir / "docs").mkdir(parents=True)
            (base_dir / "configs").mkdir(parents=True)
            (base_dir / "data/processed/latest").mkdir(parents=True)

            (base_dir / "README.md").write_text("# Eco Sim\nGDP growth and infrastructure planning.\n", encoding="utf-8")
            (base_dir / "docs/phase1.md").write_text("Phase 1 covers data collection and crawling.\n", encoding="utf-8")
            (base_dir / "docs/frontend_direction.md").write_text("Frontend should center the colony view.\n", encoding="utf-8")
            (base_dir / "data/processed/latest/overview.md").write_text(
                "Processed data overview with GDP growth and inflation baselines.\n",
                encoding="utf-8",
            )
            (base_dir / "configs/knowledge_documents.json").write_text(
                json.dumps({"allowed_document_ids": []}),
                encoding="utf-8",
            )

            build_knowledge_index(base_dir)
            index = load_knowledge_index(base_dir)
            results = search_knowledge(index, "gdp growth", limit=3)

            self.assertTrue(results)
            self.assertEqual(index["source_count"], 4)


if __name__ == "__main__":
    unittest.main()
