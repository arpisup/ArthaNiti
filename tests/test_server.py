from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from ecosim.server import create_wsgi_app


def _request(app, method: str, path: str, body: dict | None = None, query: str = "") -> tuple[str, bytes]:
    raw_body = json.dumps(body).encode("utf-8") if body is not None else b""
    status_line = {"value": ""}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_line["value"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw_body)),
        "wsgi.input": io.BytesIO(raw_body),
    }
    chunks = app(environ, start_response)
    response_body = b"".join(chunks)
    return status_line["value"], response_body


class ServerTests(unittest.TestCase):
    def test_wsgi_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            (base_dir / "configs").mkdir(parents=True)
            (base_dir / "data/processed/latest").mkdir(parents=True)
            (base_dir / "data/knowledge/latest").mkdir(parents=True)
            (base_dir / "web").mkdir(parents=True)

            repo_root = Path(__file__).resolve().parents[1]
            for name in ("policy_model.json", "colony_entities.json"):
                (base_dir / "configs" / name).write_text(
                    (repo_root / "configs" / name).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

            snapshot = {
                "baseline_year": 2024,
                "macro_baseline": {
                    "gdp_growth_pct": 6.5,
                    "inflation_pct": 4.8,
                    "unemployment_pct": 4.2,
                    "fiscal_stress_index": 48.0,
                    "investment_sentiment_index": 57.0,
                    "exchange_stability_index": 68.0,
                    "trade_momentum_index": 55.0,
                    "household_pressure_index": 42.0,
                },
                "data_quality": {"stale_indicators": []},
            }
            (base_dir / "data/processed/latest/snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            (base_dir / "data/knowledge/latest/index.json").write_text(
                json.dumps({"chunk_count": 0, "source_count": 0, "document_frequency": {}, "chunks": []}),
                encoding="utf-8",
            )
            (base_dir / "web/index.html").write_text("<!doctype html><title>Eco Sim</title>", encoding="utf-8")

            app = create_wsgi_app(base_dir, auto_build=False)

            status, body = _request(app, "GET", "/api/health")
            self.assertEqual(status, "200 OK")
            self.assertEqual(json.loads(body)["status"], "ok")

            status, body = _request(app, "GET", "/api/config")
            self.assertEqual(status, "200 OK")
            self.assertIn("policy_levers", json.loads(body))

            status, body = _request(app, "POST", "/api/simulate", {"policy_inputs": {"gst_rate": 20}})
            self.assertEqual(status, "200 OK")
            self.assertIn("macro_metrics", json.loads(body))

            status, body = _request(app, "GET", "/")
            self.assertEqual(status, "200 OK")
            self.assertIn(b"Eco Sim", body)


if __name__ == "__main__":
    unittest.main()
