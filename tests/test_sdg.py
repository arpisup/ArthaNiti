from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from ecosim.sources.sdg import (
    PROFILES,
    _clean_2019_20_table,
    _clean_2020_21_table,
    _clean_2023_24_table,
)


class SDGExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_pdf = Path("dummy.pdf")
        self.profile_2019_20 = next(profile for profile in PROFILES if profile.key == "sdg_2019_20")
        self.profile_2020_21 = next(profile for profile in PROFILES if profile.key == "sdg_2020_21")
        self.profile_2023_24 = next(profile for profile in PROFILES if profile.key == "sdg_2023_24")

    def test_clean_2019_20_table_splits_merged_columns(self) -> None:
        table = pd.DataFrame(
            [
                {
                    "Unnamed: 1": "States/UTs",
                },
                {
                    "Unnamed: 1": "Andhra Pradesh",
                    "Unnamed: 2": "69",
                    "Unnamed: 3": "35",
                    "Unnamed: 4": "76",
                    "Unnamed: 5": "52",
                    "Unnamed: 6": "37",
                    "Unnamed: 7": "96",
                    "Unnamed: 8": "86",
                    "Unnamed: 9": "78 66",
                    "Unnamed: 11": "68",
                    "Unnamed: 12": "36",
                    "Unnamed: 13": "57",
                    "Unnamed: 14": "70",
                    "Unnamed: 15": "86",
                    "Unnamed: 16": "86",
                    "Composite": "67 Goal 7: Affordable and Clean Energy",
                },
                {
                    "Unnamed: 1": "A and N Islands",
                    "Unnamed: 2": "48",
                    "Unnamed: 3": "38",
                    "Unnamed: 4": "65",
                    "Unnamed: 5": "61",
                    "Unnamed: 6": "48",
                    "Unnamed: 7": "85",
                    "Unnamed: 8": "73",
                    "Unnamed: 9": "55 13",
                    "Unnamed: 11": "94",
                    "Unnamed: 12": "47",
                    "Unnamed: 13": "69",
                    "Unnamed: 14": "72",
                    "Unnamed: 15": "85",
                    "Unnamed: 16": "65",
                    "Composite": "61",
                },
            ]
        )

        records = _clean_2019_20_table(table, self.profile_2019_20, self.base_pdf)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["sdg_8"], 78)
        self.assertEqual(records[0]["sdg_9"], 66)
        self.assertEqual(records[0]["composite_score"], 67)
        self.assertEqual(records[1]["name"], "Andaman and Nicobar Islands")
        self.assertEqual(records[1]["row_type"], "union_territory")

    def test_clean_2020_21_table_repairs_merged_ut_name(self) -> None:
        table = pd.DataFrame(
            [
                {"States": "Kerala", "SDG7": "100", "SDG6": "89", "SDG12": "65", "SDG16": "80", "SDG11": "75", "SDG3": "72", "SDG10": "69", "SDG1": "83", "SDG15": "77", "SDG8": "62", "SDG4": "80", "SDG2": "80", "SDG13": "69", "SDG5": "63", "SDG9": "60", "Composite SDG": "75"},
                {"States": "Dadra and Nagar Haveli &"},
                {"States": None, "SDG7": "71", "SDG6": "95", "SDG12": "62", "SDG16": "75", "SDG11": "89", "SDG3": "80", "SDG10": "66", "SDG1": "65", "SDG15": "62", "SDG8": "57", "SDG4": "56", "SDG2": "27", "SDG13": "18", "SDG5": "53", "SDG9": "47", "Composite SDG": "62"},
                {"States": "Daman and Diu"},
                {"States": "India", "SDG7": "92", "SDG6": "83", "SDG12": "74", "SDG16": "74", "SDG11": "79", "SDG3": "74", "SDG10": "67", "SDG1": "60", "SDG15": "66", "SDG8": "61", "SDG4": "57", "SDG2": "47", "SDG13": "54", "SDG5": "48", "SDG9": "55", "Composite SDG": "66"},
            ]
        )

        records = _clean_2020_21_table(table, self.profile_2020_21, self.base_pdf)

        self.assertEqual(len(records), 3)
        merged = next(record for record in records if "Dadra and Nagar Haveli and Daman and Diu" == record["name"])
        self.assertEqual(merged["sdg_7"], 71)
        self.assertEqual(merged["composite_score"], 62)

    def test_clean_2023_24_table_repairs_trailing_name_row(self) -> None:
        table = pd.DataFrame(
            [
                {"Unnamed: 0": "STATES"},
                {"Unnamed: 0": "Kerala", "Unnamed: 1": "100", "Unnamed: 2": "87", "Unnamed: 3": "82", "Unnamed: 4": "88", "Unnamed: 5": "80", "Unnamed: 6": "74", "Unnamed: 7": "71", "Unnamed: 8": "84", "Unnamed: 9": "53", "Unnamed: 10": "81", "Unnamed: 11": "84", "Unnamed: 12": "80", "Unnamed: 13": "82", "Unnamed: 14": "69", "Unnamed: 15": "66", "Composite": "79"},
                {"Unnamed: 0": "Dadra and Nagar Haveli and", "Unnamed: 1": "52", "Unnamed: 2": "73", "Unnamed: 3": "80", "Unnamed: 4": "99", "Unnamed: 5": "70", "Unnamed: 6": "73", "Unnamed: 7": "71", "Unnamed: 8": "89", "Unnamed: 9": "76", "Unnamed: 10": "89", "Unnamed: 11": "22", "Unnamed: 12": "38", "Unnamed: 13": "67", "Unnamed: 14": "55", "Unnamed: 15": "41", "Composite": "66"},
                {"Unnamed: 0": "Daman and Diu"},
            ]
        )

        records = _clean_2023_24_table(table, self.profile_2023_24, self.base_pdf)

        self.assertEqual(len(records), 2)
        merged = next(record for record in records if record["name"] == "Dadra and Nagar Haveli and Daman and Diu")
        self.assertEqual(merged["row_type"], "union_territory")
        self.assertEqual(merged["sdg_7"], 52)
        self.assertEqual(merged["composite_score"], 66)


if __name__ == "__main__":
    unittest.main()
