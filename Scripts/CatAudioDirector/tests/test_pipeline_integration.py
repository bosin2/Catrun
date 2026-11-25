"""Integration gates use mocked QA/subprocess and never contact Unreal."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cat_audio as cad


class IntegrationGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cat_audio_integration_tests_")
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name)
        self.assets = [{"id": "Bell", "path": str(self.run / "final" / "Bell.wav"), "sha256": "a" * 64, "loop": False, "kind": "sfx"}]
        self.manifest = {"run_id": "CAD_test", "status": "ready_for_import", "mock": True, "unreal_status": "not_imported", "assets": self.assets}
        cad.save_json(self.run / "manifest.json", self.manifest)
        cad.save_json(self.run / "import_plan.json", {"run_id": "CAD_test", "mock": True, "assets": self.assets})
        self.qa = patch.object(cad, "qa_run", return_value={"passed": True}).start()
        self.runner = patch.object(cad, "Runner").start()
        self.addCleanup(patch.stopall)

    def persisted(self):
        return json.loads((self.run / "manifest.json").read_text(encoding="utf-8"))

    def test_tampered_plan_never_calls_unreal(self):
        cad.save_json(self.run / "import_plan.json", {"run_id": "CAD_test", "mock": True, "assets": []})
        with self.assertRaisesRegex(ValueError, "differs"):
            cad.integrate_run(self.run, allow_mock=True)
        self.runner.assert_not_called()
        self.assertEqual(self.persisted()["unreal_status"], "not_imported")

    def test_partial_report_fails_and_blocks_duplicate_mutation(self):
        cad.save_json(self.run / "unreal_report.json", {"status": "passed", "assets": []})
        with self.assertRaisesRegex(ValueError, "incomplete"):
            cad.integrate_run(self.run, allow_mock=True)
        self.assertEqual(self.persisted()["unreal_status"], "failed_or_unknown")
        self.runner.assert_called_once_with(self.run / "logs.jsonl", attempts=1)
        self.runner.return_value.call.assert_called_once()
        with self.assertRaisesRegex(ValueError, "already attempted"):
            cad.integrate_run(self.run, allow_mock=True)
        self.runner.return_value.call.assert_called_once()

    def test_ambiguous_process_failure_is_persisted_and_never_retried(self):
        self.runner.return_value.call.side_effect = TimeoutError("test ambiguous editor outcome")
        with self.assertRaises(TimeoutError):
            cad.integrate_run(self.run, allow_mock=True)
        self.assertEqual(self.persisted()["unreal_status"], "failed_or_unknown")
        self.runner.assert_called_once_with(self.run / "logs.jsonl", attempts=1)
        self.runner.return_value.call.assert_called_once()

    def test_failed_qa_or_missing_mock_gate_never_calls_unreal(self):
        with self.assertRaisesRegex(ValueError, "allow-mock"):
            cad.integrate_run(self.run)
        self.qa.return_value = {"passed": False}
        with self.assertRaisesRegex(ValueError, "QA must pass"):
            cad.integrate_run(self.run, allow_mock=True)
        self.runner.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
