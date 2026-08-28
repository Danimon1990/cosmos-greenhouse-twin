import base64
import sys
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "src" / "agent"
sys.path.insert(0, str(AGENT_DIR))

from cosmos_client import build_request_payload


class Cosmos3RequestTests(unittest.TestCase):
    def test_request_matches_media_first_chat_completions_contract(self):
        context = {
            "sensors": {"temperatureC": 22.0, "humidityPct": 50.0, "soilMoisturePct": 40.0},
            "devices": {"fanPower": 0.0, "ventPosition": 0.0, "valveFlow": 0.0},
            "alerts": {"dryZones": ["B03-C"], "shadedZones": []},
        }
        png_header = base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode("ascii")
        payload = build_request_payload(context, png_header)

        self.assertEqual(payload["model"], "nvidia/cosmos3-nano-reasoner")
        self.assertEqual(payload["messages"][0]["role"], "system")
        content = payload["messages"][1]["content"]
        self.assertEqual(content[0]["type"], "image_url")
        self.assertTrue(content[0]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(content[1]["type"], "text")
        self.assertIn("B03-C", content[1]["text"])
        self.assertIn("<think>", content[1]["text"])
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertFalse(payload["stream"])


if __name__ == "__main__":
    unittest.main()
