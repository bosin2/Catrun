"""Offline contract tests. FFmpeg tests process real audio; no service calls or UE writes."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cat_audio as cad


class TemporaryAudioCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cat_audio_tests_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def brief(self, assets):
        path = self.root / "brief.json"
        cad.save_json(path, {"assets": assets})
        return path

    def asset(self, name="test_sfx", kind="sfx", **kwargs):
        return {"id": name, "kind": kind, "duration_seconds": 1.0, **kwargs}


class ValidationTests(TemporaryAudioCase):
    def test_unsafe_or_case_colliding_ids_are_rejected(self):
        for name in ("../escape", "C:/escape", "sound.wav", "", "한글", "A" * 65):
            with self.subTest(name=name), self.assertRaises(ValueError):
                cad.validate_brief({"assets": [self.asset(name)]}, self.root, "mock")
        with self.assertRaises(ValueError):
            cad.validate_brief({"assets": [self.asset("Bell"), self.asset("bell")]}, self.root, "mock")

    def test_bad_duration_and_loop_values_are_rejected(self):
        for duration in (True, 0, 601, float("nan"), float("inf"), "2"):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                cad.validate_brief({"assets": [self.asset(duration_seconds=duration)]}, self.root, "mock")
        with self.assertRaises(ValueError):
            cad.validate_brief({"assets": [self.asset(loop="yes")]}, self.root, "mock")

    def test_local_source_must_exist_and_cannot_be_a_url(self):
        for source in (None, "", "missing.wav", "https://example.com/audio.wav"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                cad.validate_brief({"assets": [self.asset(source_path=source)]}, self.root, "local")

    def test_relative_unicode_path_is_resolved_from_brief_directory(self):
        source = self.root / "원본 오디오.wav"
        source.write_bytes(b"validation only")
        result = cad.validate_brief({"assets": [self.asset(source_path=source.name)]}, self.root, "local")
        self.assertEqual(result[0]["source_path"], str(source.resolve()))

    def test_retry_logs_failure_then_success_without_shell(self):
        stamp = self.root / "attempt.txt"
        log = self.root / "retries.jsonl"
        script = "import pathlib,sys; p=pathlib.Path(sys.argv[1]); existed=p.exists(); p.write_text('attempt'); sys.exit(0 if existed else 7)"
        result = cad.Runner(log, attempts=2).call([sys.executable, "-c", script, str(stamp)], "retry-fixture")
        self.assertEqual(result.returncode, 0)
        events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["event"] for item in events], ["start", "failure", "start", "complete"])
        self.assertEqual([item["attempt"] for item in events], [1, 1, 2, 2])

    def test_retry_exhaustion_is_reported(self):
        log = self.root / "failed.jsonl"
        with self.assertRaises(RuntimeError):
            cad.Runner(log, attempts=2).call([sys.executable, "-c", "import sys; sys.stderr.write('fixture failure'); sys.exit(9)"], "failure-fixture")
        events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(item["event"] == "failure" for item in events), 2)
        self.assertIn("fixture failure", events[-1]["error"])


class FFmpegPipelineTests(TemporaryAudioCase):
    @classmethod
    def setUpClass(cls):
        # Missing FFmpeg is a failing prerequisite, never an invisible skip.
        for name in ("ffmpeg", "ffprobe"):
            subprocess.run([cad.find_tool(name), "-version"], capture_output=True, check=True, timeout=10)

    def pipeline(self, assets, mode="mock"):
        return cad.run_pipeline(self.brief(assets), mode, self.root / "runs", workers=2)

    def test_mock_bgm_and_sfx_pass_real_finishing_and_independent_qa(self):
        run, manifest = self.pipeline([self.asset("CastleBgm", "bgm"), self.asset("BellSfx")])
        self.assertEqual(manifest["status"], "ready_for_import", manifest)
        self.assertEqual(manifest["paid_requests"], 0)
        self.assertTrue(manifest["mock"])
        self.assertEqual(len(manifest["assets"]), 2)
        self.assertTrue((run / "import_plan.json").is_file())
        for item in manifest["assets"]:
            self.assertEqual(item["provenance"]["provider"], "mock")
            self.assertFalse(item["provenance"]["production_ready"])
            self.assertTrue(item["qa"]["passed"], item["qa"])
            with wave.open(item["path"], "rb") as audio:
                self.assertEqual(audio.getnchannels(), 2 if item["kind"] == "bgm" else 1)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getframerate(), 48000)
                self.assertAlmostEqual(audio.getnframes() / 48000, 1.0, places=2)
        report = cad.qa_run(run)
        self.assertTrue(report["passed"], report)
        self.assertTrue(all(item["checks"]["sha256"] for item in report["assets"]))

    def test_short_sfx_remain_short_and_pass_padded_loudness_measurement(self):
        assets = [self.asset(f"Click{round(duration * 1000)}", duration_seconds=duration) for duration in (.05, .1, .25)]
        run, manifest = self.pipeline(assets)
        self.assertEqual(manifest["status"], "ready_for_import", manifest)
        self.assertEqual(len(manifest["assets"]), 3)
        for item in manifest["assets"]:
            with wave.open(item["path"], "rb") as audio:
                self.assertAlmostEqual(audio.getnframes() / audio.getframerate(), item["duration_seconds"], places=3)
            self.assertTrue(item["qa"]["passed"], item["qa"])
        self.assertTrue(cad.qa_run(run)["passed"])

    def test_local_source_is_copied_and_never_modified(self):
        source = self.root / "original sound.wav"
        cad.mock_wave(source, 1.2, 2, "bgm")
        original_hash = cad.sha256(source)
        run, manifest = self.pipeline([self.asset("LocalBell", source_path=source.name)], "local")
        self.assertEqual(manifest["status"], "ready_for_import", manifest)
        self.assertEqual(cad.sha256(source), original_hash)
        self.assertFalse(manifest["mock"])
        self.assertEqual(manifest["assets"][0]["provenance"]["source_sha256"], original_hash)
        self.assertTrue(cad.qa_run(run)["passed"])

    def test_short_loop_source_fails_with_manifest_and_no_import_plan(self):
        source = self.root / "short.wav"
        cad.mock_wave(source, 1.0, 2, "bgm")
        run, manifest = self.pipeline([self.asset("ShortBgm", "bgm", source_path=source.name)], "local")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["errors"][0]["id"], "ShortBgm")
        self.assertIn("including loop overlap", manifest["errors"][0]["error"])
        self.assertFalse((run / "import_plan.json").exists())
        self.assertIn("asset_failed", (run / "logs.jsonl").read_text(encoding="utf-8"))
        self.assertFalse(cad.qa_run(run)["passed"])

    def test_silent_source_fails_without_nonfinite_json(self):
        source = self.root / "silence.wav"
        with wave.open(str(source), "wb") as audio:
            audio.setparams((1, 2, 48000, 48000, "NONE", "not compressed"))
            audio.writeframes(b"\x00\x00" * 48000)
        run, manifest = self.pipeline([self.asset("Silent", source_path=source.name)], "local")
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("Silent/non-finite", manifest["errors"][0]["error"])
        self.assertFalse((run / "import_plan.json").exists())
        json.loads((run / "manifest.json").read_text(encoding="utf-8"), parse_constant=lambda value: self.fail(value))

    def test_file_tampering_is_detected_even_when_pcm_checks_pass(self):
        run, manifest = self.pipeline([self.asset()])
        self.assertEqual(manifest["status"], "ready_for_import", manifest)
        final = Path(manifest["assets"][0]["path"])
        # Trailing data preserves the playable samples but changes file identity.
        with final.open("ab") as stream:
            stream.write(b"CAT_AUDIO_TAMPER")
        report = cad.qa_run(run)
        self.assertFalse(report["passed"])
        self.assertFalse(report["assets"][0]["checks"]["sha256"])

    def test_qa_rejects_manifest_path_outside_run_final(self):
        run, manifest = self.pipeline([self.asset()])
        outside = self.root / "elsewhere.wav"
        outside.write_bytes(Path(manifest["assets"][0]["path"]).read_bytes())
        manifest["assets"][0]["path"] = str(outside)
        cad.save_json(run / "manifest.json", manifest)
        report = cad.qa_run(run)
        self.assertFalse(report["passed"])
        self.assertIn("outside run final", report["assets"][0]["error"])

    def test_qa_detects_requested_asset_omitted_from_manifest(self):
        run, manifest = self.pipeline([self.asset("RequestedOne"), self.asset("RequestedTwo")])
        self.assertEqual(manifest["status"], "ready_for_import", manifest)
        manifest["assets"].pop()
        cad.save_json(run / "manifest.json", manifest)
        report = cad.qa_run(run)
        self.assertFalse(report["passed"], "QA must compare the completed IDs with the original brief")


if __name__ == "__main__":
    unittest.main(verbosity=2)
