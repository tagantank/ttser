import sys
import unittest
from pathlib import Path
from unittest import mock

from engine.runtime import (
    default_output_mp3,
    ffmpeg_binary,
    is_frozen,
    prepend_library_path,
    resource_root,
    run_entry,
    synth_child_command,
    user_data_dir,
)


class RuntimeTests(unittest.TestCase):
    def test_checkout_root_contains_engine(self) -> None:
        root = resource_root()
        self.assertTrue((root / "engine" / "runtime.py").is_file())
        self.assertFalse(is_frozen())

    def test_synth_command_uses_module_outside_bundle(self) -> None:
        job = Path("/tmp/job.json")
        self.assertEqual(
            synth_child_command(job),
            [sys.executable, "-m", "engine.s2_synth", "--job", str(job)],
        )

    def test_frozen_synth_prefers_helper(self) -> None:
        job = Path("/tmp/job.json")
        helper = Path("/tmp/Contents/MacOS/ttser-synth")
        with (
            mock.patch("engine.runtime.is_frozen", return_value=True),
            mock.patch("sys.executable", "/tmp/Contents/MacOS/ttser"),
            mock.patch.object(Path, "is_file", lambda self: self.name == "ttser-synth"),
        ):
            cmd = synth_child_command(job)
        self.assertEqual(cmd[0], str(helper))
        self.assertEqual(cmd[1:], ["--job", str(job)])

    def test_prepend_sets_dyld_and_ld(self) -> None:
        env = prepend_library_path({}, Path("/opt/ttser/lib/metal"))
        self.assertEqual(env["LD_LIBRARY_PATH"], "/opt/ttser/lib/metal")
        self.assertEqual(env["DYLD_LIBRARY_PATH"], "/opt/ttser/lib/metal")

    def test_ffmpeg_falls_back_to_path(self) -> None:
        self.assertEqual(ffmpeg_binary(), "ffmpeg")

    def test_default_output_stays_relative_in_checkout(self) -> None:
        self.assertEqual(default_output_mp3(), "output/result.mp3")

    def test_frozen_user_data_on_darwin(self) -> None:
        with (
            mock.patch("engine.runtime.is_frozen", return_value=True),
            mock.patch("engine.runtime.is_flatpak", return_value=False),
            mock.patch("sys.platform", "darwin"),
        ):
            path = user_data_dir()
        self.assertEqual(path, Path.home() / "Library" / "Application Support" / "ttser")

    def test_run_entry_dispatches_synth_job(self) -> None:
        with mock.patch("engine.s2_synth.main", return_value=0) as synth:
            rc = run_entry(["ttser", "--synth-job", "/tmp/job.json"])
        self.assertEqual(rc, 0)
        synth.assert_called_once_with(["--job", "/tmp/job.json"])


if __name__ == "__main__":
    unittest.main()
