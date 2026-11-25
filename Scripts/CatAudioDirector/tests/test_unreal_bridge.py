import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from contextlib import redirect_stdout
import wave

MODULE = Path(__file__).resolve().parents[1] / "unreal_bridge.py"
spec = importlib.util.spec_from_file_location("unreal_bridge", MODULE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        wav = self.folder / "tone.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b"\x00\x00" * 480)
        self.plan = {"run_id": "test_01", "mock": True, "assets": [{"id": "bell", "kind": "sfx", "loop": False,
                     "path": str(wav), "sha256": hashlib.sha256(wav.read_bytes()).hexdigest()}]}

    def test_mock_requires_explicit_gate(self):
        with self.assertRaisesRegex(bridge.BridgeError, "allow-mock"):
            bridge.validate_plan(self.plan)

    def test_hash_change_refused(self):
        self.plan["assets"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(bridge.BridgeError, "hash mismatch"):
            bridge.validate_plan(self.plan, allow_mock=True)

    def test_path_escape_refused(self):
        for value in ("../bad", "/Game/Existing", "x.y", "x\\y"):
            with self.subTest(value=value):
                self.plan["run_id"] = value
                with self.assertRaises(bridge.BridgeError):
                    bridge.validate_plan(self.plan, allow_mock=True)

    def test_case_insensitive_duplicate_refused(self):
        self.plan["assets"].append({**self.plan["assets"][0], "id": "Bell"})
        with self.assertRaisesRegex(bridge.BridgeError, "Duplicate"):
            bridge.validate_plan(self.plan, allow_mock=True)

    def test_mock_field_required(self):
        del self.plan["mock"]
        with self.assertRaisesRegex(bridge.BridgeError, "explicitly"):
            bridge.validate_plan(self.plan, allow_mock=True)

    def test_channel_contract(self):
        self.plan["assets"][0]["kind"] = "bgm"
        with self.assertRaisesRegex(bridge.BridgeError, "channel"):
            bridge.validate_plan(self.plan, allow_mock=True)

    def test_dry_run_never_connects(self):
        plan_file = self.folder / "plan.json"
        plan_file.write_text(json.dumps(self.plan), encoding="utf-8")
        with patch.object(bridge.UnrealMCP, "connect", side_effect=AssertionError("network forbidden")):
            self.assertEqual(bridge.main(["import", "--plan", str(plan_file)]), 0)
        report = json.loads((self.folder / "unreal_report.json").read_text(encoding="utf-8"))
        self.assertFalse(report["editor_mutated"])

    def test_apply_mock_without_gate_never_connects(self):
        plan_file = self.folder / "plan.json"
        plan_file.write_text(json.dumps(self.plan), encoding="utf-8")
        with patch.object(bridge.UnrealMCP, "connect", side_effect=AssertionError("network forbidden")):
            self.assertEqual(bridge.main(["import", "--plan", str(plan_file), "--apply"]), 1)

    def test_nonlocal_endpoint_refused(self):
        with self.assertRaisesRegex(bridge.BridgeError, "loopback"):
            bridge.UnrealMCP("http://192.168.1.2:8000/mcp")

    def test_generated_script_compiles(self):
        plan = bridge.validate_plan(self.plan, allow_mock=True)
        compile(bridge.import_source(plan, self.folder), "<import-script>", "exec")
        self.assertEqual(plan["assets"][0]["asset_path"], "/Game/Audio/CatAudioDirector/test_01/SW_bell")

    def test_mcp_error_not_treated_as_success(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.unwrap({"isError": True, "content": [{"type": "text", "text": "failed"}]})

    def run_editor_script(self, *, dirty=False, exists=False, playing=False):
        unreal = MagicMock()
        unreal.Paths.convert_relative_path_to_full.return_value = str(self.folder)
        unreal.SystemLibrary.get_engine_version.return_value = "5.8.2-test"
        unreal.EditorLevelLibrary.get_pie_worlds.return_value = [object()] if playing else []
        package = MagicMock()
        package.get_path_name.return_value = "/Game/ExistingMap"
        unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages.return_value = [package] if dirty else []
        unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages.return_value = []
        unreal.get_editor_subsystem.return_value.does_asset_exist.return_value = exists
        plan = bridge.validate_plan(self.plan, allow_mock=True)
        output = io.StringIO()
        with patch.dict("sys.modules", {"unreal": unreal}), redirect_stdout(output):
            exec(compile(bridge.import_source(plan, self.folder), "<script>", "exec"), {})
        report = json.loads(output.getvalue().split(bridge.MARKER)[1])
        unreal.AssetImportTask.assert_not_called()
        unreal.AssetToolsHelpers.get_asset_tools.assert_not_called()
        return report

    def test_existing_asset_blocks_all_writes_in_editor(self):
        report = self.run_editor_script(exists=True)
        self.assertIn("Existing asset refused", report["error"])
        self.assertFalse(report["partial_import"])

    def test_dirty_editor_blocks_all_writes(self):
        report = self.run_editor_script(dirty=True)
        self.assertIn("unsaved packages", report["error"])

    def test_playing_editor_blocks_all_writes(self):
        report = self.run_editor_script(playing=True)
        self.assertIn("PIE active", report["error"])


if __name__ == "__main__":
    unittest.main()
