"""Exercise package acquisition against isolated copies and real POSIX files."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from audio_processing import Analysis, analyze_fixture
from audio_processing.assets import MAX_MANIFEST_BYTES, load_assets
from audio_processing.core import MAX_INPUT_BYTES


class PackageResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = Path(__file__).resolve().parents[1] / "src" / "audio_processing"

    def copy_package(self, name):
        root = self.directory / name
        package = root / "audio_processing"
        shutil.copytree(self.source, package, ignore=shutil.ignore_patterns("__pycache__"))
        return root, package

    def assert_cli_rejects_assets(self, root):
        environment = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-m", "audio_processing", "--fixture", "complaint"],
            cwd=root, env=environment, capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["kind"], "rejected")
        self.assertEqual(report["code"], "invalid_assets")
        self.assertNotIn("metrics", report)
        self.assertEqual(result.stderr, b"")
        self.assertNotIn(str(root).encode(), result.stdout)
        self.assertNotIn(b"PRIVATE", result.stdout)

    def test_real_fifo_directory_final_symlink_and_missing_resources_fail_closed(self):
        for filename in ("manifest.json", "complaint.wav", "silence.wav"):
            for kind in ("fifo", "directory", "symlink", "missing"):
                with self.subTest(filename=filename, kind=kind):
                    root, package = self.copy_package(f"{filename}-{kind}")
                    resource = package / "data" / filename
                    original = resource.read_bytes()
                    resource.unlink()
                    if kind == "fifo":
                        os.mkfifo(resource)
                    elif kind == "directory":
                        resource.mkdir()
                    elif kind == "symlink":
                        target = resource.with_name("PRIVATE-SYMLINK-TARGET")
                        target.write_bytes(original)
                        resource.symlink_to(target)
                    self.assert_cli_rejects_assets(root)

    def test_real_oversized_resources_fail_closed(self):
        for filename, limit in (
            ("manifest.json", MAX_MANIFEST_BYTES),
            ("complaint.wav", MAX_INPUT_BYTES),
            ("silence.wav", MAX_INPUT_BYTES),
        ):
            with self.subTest(filename=filename):
                root, package = self.copy_package(filename)
                with (package / "data" / filename).open("wb") as stream:
                    stream.truncate(limit + 1)
                self.assert_cli_rejects_assets(root)

    def test_regular_files_in_an_isolated_resource_copy_are_supported(self):
        _root, package = self.copy_package("regular")
        with patch("audio_processing.assets.resources.files", return_value=package):
            result = analyze_fixture("complaint")
        self.assertIsInstance(result, Analysis)
        self.assertEqual(result.transcript.full_text, "my parcel is late. please check its status.")

    def test_nonfilesystem_resources_fail_closed_without_open_or_extraction(self):
        class UnsupportedResource:
            def joinpath(self, *parts):
                raise AssertionError("An unsupported resource must not be opened or extracted.")

        with patch("audio_processing.assets.resources.files", return_value=UnsupportedResource()):
            result = analyze_fixture("complaint")
        self.assertEqual(result.code, "invalid_assets")

    def test_resource_acquisition_value_and_unicode_errors_are_private_rejections(self):
        for boundary in ("audio_processing.assets.resources.files", "audio_processing.assets.os.open"):
            for error in (ValueError("PRIVATE resource failure"), UnicodeError("PRIVATE encoding failure")):
                with self.subTest(boundary=boundary, error=type(error)), patch(boundary, side_effect=error):
                    result = analyze_fixture("complaint")
                self.assertEqual(result.code, "invalid_assets")
                self.assertNotIn("PRIVATE", result.message)

    def test_resource_discovery_does_not_mask_programming_defects(self):
        with patch("audio_processing.assets.resources.files", side_effect=TypeError("programming defect")):
            with self.assertRaises(TypeError):
                load_assets()

    def test_opened_resource_descriptor_is_checked_and_closed(self):
        _root, package = self.copy_package("substitution")
        fifo = self.directory / "substituted.fifo"
        os.mkfifo(fifo)
        descriptor = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        with patch("audio_processing.assets.resources.files", return_value=package), patch("audio_processing.assets.os.open", return_value=descriptor):
            result = analyze_fixture("complaint")
        self.assertEqual(result.code, "invalid_assets")
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_resource_limit_still_applies_after_file_growth(self):
        _root, package = self.copy_package("growth")
        (package / "data" / "manifest.json").write_bytes(b" " * (2 * MAX_MANIFEST_BYTES))
        small_regular = type("Info", (), {"st_mode": 0o100600, "st_size": 1})()
        consumed = 0
        real_read = os.read

        def observe_read(*args):
            nonlocal consumed
            part = real_read(*args)
            consumed += len(part)
            return part

        with patch("audio_processing.assets.resources.files", return_value=package), patch("audio_processing.assets.os.fstat", return_value=small_regular), patch("audio_processing.assets.os.read", side_effect=observe_read):
            result = analyze_fixture("complaint")
        self.assertEqual(result.code, "invalid_assets")
        self.assertLessEqual(consumed, MAX_MANIFEST_BYTES + 1)

    def test_cancelled_resource_read_closes_owned_descriptor(self):
        _root, package = self.copy_package("cancelled")
        opened = []
        real_open = os.open

        def capture(*args):
            descriptor = real_open(*args)
            opened.append(descriptor)
            return descriptor

        with patch("audio_processing.assets.resources.files", return_value=package), patch("audio_processing.assets.os.open", side_effect=capture), patch("audio_processing.assets.os.read", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                load_assets()
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError):
            os.fstat(opened[0])


if __name__ == "__main__":
    unittest.main()
