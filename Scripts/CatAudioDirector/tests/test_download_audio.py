"""Downloader tests use fake HTTP responses; never contact a provider or spend credits."""
from __future__ import annotations

from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import download_audio as download


HOST = "audio.example.com"
URL = f"https://{HOST}/clip.wav?signature=PRIVATE_SECRET"
PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))]


class Response(io.BytesIO):
    def __init__(self, data=b"RIFF_test_audio", content_type="audio/wav"):
        super().__init__(data)
        self.headers = Message()
        self.headers.set_type(content_type)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cat_audio_download_tests_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.destination = self.root / "clip.wav"
        self.dns = patch.object(download.socket, "getaddrinfo", return_value=PUBLIC).start()
        self.addCleanup(patch.stopall)
        self.sleep = patch.object(download.time, "sleep").start()
        self.opener = Mock()
        patch.object(download.urllib.request, "build_opener", return_value=self.opener).start()

    def call(self, **kwargs):
        return download.download(URL, self.destination, {HOST}, **kwargs)

    def test_scheme_credentials_port_and_unlisted_host_are_rejected(self):
        for url in (f"http://{HOST}/audio", f"https://user:pass@{HOST}/audio", f"https://{HOST}:444/audio", "https://evil.example.com/audio"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                download.validate_url(url, {HOST})
        self.opener.open.assert_not_called()

    def test_private_or_mixed_dns_addresses_are_rejected(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"):
            self.dns.return_value = PUBLIC + [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))]
            with self.subTest(address=address), self.assertRaises(ValueError):
                download.validate_url(URL, {HOST})

    def test_redirects_validate_new_scheme_and_host(self):
        handler = download.Redirects({HOST})
        request = urllib.request.Request(URL)
        for target in ("http://audio.example.com/other.wav", "https://unlisted.example.com/other.wav"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, target)
        redirected = handler.redirect_request(request, None, 302, "Found", {}, f"https://{HOST}/other.wav")
        self.assertEqual(redirected.full_url, f"https://{HOST}/other.wav")

    def test_success_writes_hash_receipt_without_signed_url(self):
        payload = b"RIFF_test_audio"
        self.opener.open.return_value = Response(payload)
        result = self.call()
        self.assertEqual(self.destination.read_bytes(), payload)
        self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(result["attempts"], 1)
        self.assertFalse(result["verified_audio"])
        receipt = self.destination.with_suffix(".wav.receipt.json").read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE_SECRET", receipt)
        self.assertNotIn("signature", receipt)
        self.assertEqual(json.loads(receipt)["source_host"], HOST)

    def test_retryable_http_error_then_success(self):
        self.opener.open.side_effect = [urllib.error.HTTPError(URL, 503, "PRIVATE_SECRET", {}, None), Response()]
        result = self.call()
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(self.opener.open.call_count, 2)
        self.sleep.assert_called_once_with(1)

    def test_forbidden_is_not_retried_and_error_does_not_expose_url(self):
        self.opener.open.side_effect = urllib.error.HTTPError(URL, 403, "PRIVATE_SECRET", {}, None)
        with self.assertRaises(RuntimeError) as error:
            self.call()
        self.assertNotIn("PRIVATE_SECRET", str(error.exception))
        self.assertNotIn("signature", str(error.exception))
        self.opener.open.assert_called_once()
        self.sleep.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_network_failure_retries_are_bounded_and_redacted(self):
        self.opener.open.side_effect = urllib.error.URLError("PRIVATE_SECRET " + URL)
        with self.assertRaises(RuntimeError) as error:
            self.call()
        self.assertEqual(self.opener.open.call_count, 3)
        self.assertNotIn("PRIVATE_SECRET", str(error.exception))
        self.assertFalse(self.destination.with_suffix(".wav.part").exists())

    def test_existing_destination_receipt_and_partial_are_preserved(self):
        for path in (self.destination, self.destination.with_suffix(".wav.receipt.json"), self.destination.with_suffix(".wav.part")):
            with self.subTest(path=path):
                path.write_bytes(b"existing user file")
                try:
                    with self.assertRaises(ValueError):
                        self.call()
                    self.assertEqual(path.read_bytes(), b"existing user file")
                finally:
                    path.unlink()
        self.opener.open.assert_not_called()

    def test_html_empty_and_oversize_downloads_leave_no_output(self):
        for response, limit in ((Response(b"<html>error</html>", "text/html"), 100), (Response(b""), 100), (Response(b"too big"), 2)):
            with self.subTest(limit=limit, response=response):
                self.opener.open.return_value = response
                with self.assertRaises(ValueError):
                    self.call(max_bytes=limit)
                self.assertFalse(self.destination.exists())
                self.assertFalse(self.destination.with_suffix(".wav.part").exists())

    def test_concurrent_destination_creation_is_not_overwritten(self):
        def open_response(*args, **kwargs):
            self.destination.write_bytes(b"other writer")
            return Response()
        self.opener.open.side_effect = open_response
        with self.assertRaises(FileExistsError):
            self.call()
        self.assertEqual(self.destination.read_bytes(), b"other writer")

    def test_concurrent_receipt_creation_is_not_overwritten(self):
        receipt = self.destination.with_suffix(".wav.receipt.json")
        def open_response(*args, **kwargs):
            receipt.write_bytes(b"other writer receipt")
            return Response()
        self.opener.open.side_effect = open_response
        with self.assertRaises(FileExistsError):
            self.call()
        self.assertEqual(receipt.read_bytes(), b"other writer receipt")

    def test_concurrent_partial_creation_is_not_deleted(self):
        partial = self.destination.with_suffix(".wav.part")
        def open_response(*args, **kwargs):
            partial.write_bytes(b"other writer partial")
            return Response()
        self.opener.open.side_effect = open_response
        with self.assertRaises(FileExistsError):
            self.call()
        self.assertTrue(partial.exists(), "A partial owned by another writer must survive failure cleanup")
        self.assertEqual(partial.read_bytes(), b"other writer partial")


if __name__ == "__main__":
    unittest.main(verbosity=2)
