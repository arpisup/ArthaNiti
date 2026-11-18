from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ecosim.sources.manual import load_manual_registry, register_manual_file
from ecosim.sources.structural_economic_analysis import load_structural_economic_catalog


class ManualIntakeTests(unittest.TestCase):
    def test_register_manual_file_copies_input_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            registry_path = base_dir / "registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "sdg",
                                "name": "SDG export",
                                "automation": "manual",
                                "category": "dataset",
                                "preferred_formats": [".csv"],
                                "notes": "test",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            input_file = base_dir / "input.csv"
            input_file.write_text("year,value\n2024,1\n", encoding="utf-8")

            manifest = register_manual_file(
                base_dir=base_dir,
                registry_path=registry_path,
                source_id="sdg",
                file_path=input_file,
            )

            copied_file = Path(manifest["copied_file"])
            self.assertTrue(copied_file.exists())
            self.assertEqual(copied_file.read_text(encoding="utf-8"), input_file.read_text(encoding="utf-8"))
            self.assertTrue((copied_file.parent.parent / "manifest.json").exists())
            self.assertTrue(manifest["format_matches_preference"])

    def test_load_manual_registry_requires_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "registry.json"
            registry_path.write_text(json.dumps({"sources": []}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_manual_registry(registry_path)

    def test_kaggle_structural_analysis_catalog_loads_cleanly(self) -> None:
        catalog_path = Path("data/data-resources-for-structural-economic-analysis.csv")
        self.assertTrue(catalog_path.exists(), "Expected Kaggle structural analysis catalog to be present")

        rows = load_structural_economic_catalog(catalog_path)
        self.assertGreater(len(rows), 0)
        self.assertIn("World Development Indicators", [row["name"] for row in rows])

        registry = load_manual_registry(Path("configs/source_registry.json"))
        self.assertIn("structural_economic_analysis", registry)


if __name__ == "__main__":
    unittest.main()
