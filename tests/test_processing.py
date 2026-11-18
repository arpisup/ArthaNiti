from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from ecosim.processing import prepare_processed_data


class ProcessingTests(unittest.TestCase):
    def test_prepare_processed_data_builds_latest_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            raw_dir = base_dir / "data/raw/world_bank/20240101T000000Z"
            raw_dir.mkdir(parents=True)

            records_path = raw_dir / "records.csv"
            with records_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "country",
                        "country_name",
                        "indicator_code",
                        "indicator_name",
                        "year",
                        "value",
                        "unit",
                        "obs_status",
                        "decimal",
                    ],
                )
                writer.writeheader()
                rows = [
                    ("NY.GDP.MKTP.KD.ZG", "GDP growth", 2023, "6.0"),
                    ("NY.GDP.MKTP.KD.ZG", "GDP growth", 2024, "6.5"),
                    ("FP.CPI.TOTL.ZG", "Inflation", 2023, "5.0"),
                    ("FP.CPI.TOTL.ZG", "Inflation", 2024, "4.8"),
                    ("SL.UEM.TOTL.ZS", "Unemployment", 2023, "4.5"),
                    ("SL.UEM.TOTL.ZS", "Unemployment", 2024, "4.2"),
                    ("FR.INR.RINR", "Real interest", 2024, "2.0"),
                    ("PA.NUS.FCRF", "Exchange rate", 2024, "80.0"),
                    ("GC.DOD.TOTL.GD.ZS", "Debt", 2024, "52.0"),
                    ("GC.TAX.TOTL.GD.ZS", "Tax", 2024, "11.0"),
                    ("BX.KLT.DINV.WD.GD.ZS", "FDI", 2024, "2.2"),
                    ("NE.TRD.GNFS.ZS", "Trade", 2024, "42.0"),
                    ("NV.AGR.TOTL.ZS", "Agriculture", 2024, "18.0"),
                    ("NV.IND.TOTL.ZS", "Industry", 2024, "28.0"),
                    ("NV.SRV.TOTL.ZS", "Services", 2024, "54.0"),
                    ("NY.GDP.MKTP.CD", "GDP current", 2024, "100.0"),
                ]
                for code, name, year, value in rows:
                    writer.writerow(
                        {
                            "country": "IND",
                            "country_name": "India",
                            "indicator_code": code,
                            "indicator_name": name,
                            "year": year,
                            "value": value,
                            "unit": "",
                            "obs_status": "",
                            "decimal": 1,
                        }
                    )

            manifest = prepare_processed_data(base_dir)
            snapshot = json.loads((base_dir / "data/processed/latest/snapshot.json").read_text(encoding="utf-8"))

            self.assertEqual(snapshot["baseline_year"], 2024)
            self.assertEqual(manifest["source_world_bank_run_id"], "20240101T000000Z")
            self.assertIn("gdp_growth_pct", snapshot["macro_baseline"])

    def test_world_bank_config_includes_additional_social_and_energy_indicators(self) -> None:
        config = json.loads(Path("configs/world_bank_india.json").read_text(encoding="utf-8"))
        codes = {item["code"] for item in config["indicators"]}
        required = {
            "SP.POP.DPND",
            "SI.POV.DDAY",
            "SE.PRM.ENRR",
            "IT.NET.USER.ZS",
            "EG.FEC.RNEW.ZS",
            "NY.GDP.PCAP.KD",
        }
        missing = sorted(required - codes)
        self.assertFalse(missing, f"Missing social/energy indicators: {missing}")


if __name__ == "__main__":
    unittest.main()
