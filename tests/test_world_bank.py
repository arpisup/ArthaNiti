from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ecosim.sources.world_bank import (
    IndicatorConfig,
    _parse_world_bank_payload,
    _load_cached_indicator_payload,
    fetch_world_bank_payload,
    normalize_indicator_rows,
)


class _FakeResponse:
    def __init__(self, payload: list[object]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class WorldBankNormalizationTests(unittest.TestCase):
    def test_normalize_indicator_rows_filters_invalid_years_and_sorts(self) -> None:
        indicator = IndicatorConfig(code="FP.CPI.TOTL.ZG", name="Inflation")
        rows = [
            {
                "date": "2021",
                "value": 5.1,
                "unit": "",
                "obs_status": "",
                "decimal": 1,
                "country": {"value": "India"},
            },
            {
                "date": "not-a-year",
                "value": 9.9,
                "country": {"value": "India"},
            },
            {
                "date": "2019",
                "value": 4.8,
                "unit": "",
                "obs_status": "",
                "decimal": 1,
                "country": {"value": "India"},
            },
        ]

        normalized = normalize_indicator_rows("IND", indicator, rows)

        self.assertEqual([row["year"] for row in normalized], [2019, 2021])
        self.assertEqual(normalized[0]["country"], "IND")
        self.assertEqual(normalized[0]["indicator_code"], "FP.CPI.TOTL.ZG")

    def test_parse_world_bank_payload_raises_clean_api_error(self) -> None:
        payload = [
            {
                "message": [
                    {
                        "id": "120",
                        "key": "Invalid value",
                        "value": "The provided parameter value is not valid",
                    }
                ]
            }
        ]

        with self.assertRaisesRegex(ValueError, "API error"):
            _parse_world_bank_payload(payload, "FP.CPI.TOTL.ZG")

    @patch("ecosim.sources.world_bank.urlopen")
    def test_fetch_world_bank_payload_collects_all_pages(self, mocked_urlopen) -> None:
        mocked_urlopen.side_effect = [
            _FakeResponse(
                [
                    {"page": 1, "pages": 2, "per_page": 2, "total": 3, "sourceid": "2"},
                    [
                        {"date": "2024", "country": {"value": "India"}, "value": 1.0},
                        {"date": "2023", "country": {"value": "India"}, "value": 2.0},
                    ],
                ]
            ),
            _FakeResponse(
                [
                    {"page": 2, "pages": 2, "per_page": 2, "total": 3, "sourceid": "2"},
                    [
                        {"date": "2022", "country": {"value": "India"}, "value": 3.0},
                    ],
                ]
            ),
        ]

        payload = fetch_world_bank_payload(
            country="IN",
            indicator_code="FP.CPI.TOTL.ZG",
            start_year=2022,
            end_year=2024,
            retries=1,
            timeout_seconds=1,
            per_page=2,
        )

        self.assertEqual(payload["metadata"]["pages"], 2)
        self.assertEqual(len(payload["rows"]), 3)
        self.assertIn("source=2", payload["request_url"])

    def test_load_cached_indicator_payload_uses_most_recent_previous_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            older_run = base_dir / "data/raw/world_bank/20260408T000000Z"
            newer_run = base_dir / "data/raw/world_bank/20260409T000000Z"
            current_run = base_dir / "data/raw/world_bank/20260410T000000Z"
            older_run.mkdir(parents=True)
            newer_run.mkdir(parents=True)
            current_run.mkdir(parents=True)

            (older_run / "FP.CPI.TOTL.ZG.json").write_text(
                json.dumps({"rows": [{"date": "2021"}], "metadata": {"page": 1}}),
                encoding="utf-8",
            )
            (newer_run / "FP.CPI.TOTL.ZG.json").write_text(
                json.dumps({"rows": [{"date": "2022"}], "metadata": {"page": 1}}),
                encoding="utf-8",
            )

            cached = _load_cached_indicator_payload(
                base_dir=base_dir,
                indicator_code="FP.CPI.TOTL.ZG",
                current_run_dir=current_run,
            )

            self.assertIsNotNone(cached)
            payload, run_id = cached
            self.assertEqual(run_id, "20260409T000000Z")
            self.assertEqual(payload["rows"][0]["date"], "2022")


if __name__ == "__main__":
    unittest.main()
