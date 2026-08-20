import math
import struct
import tempfile
import unittest
from pathlib import Path

from engine.s2_lib import (
    first_incomplete_index,
    is_complete_wav,
    is_usable_speech_wav,
    read_wav_stats,
    write_silence,
)


def _write_float_wav(path: Path, samples: list[float], sample_rate: int = 44100) -> None:
    data = struct.pack(f"<{len(samples)}f", *samples)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(data),
        b"WAVE",
        b"fmt ",
        16,
        3,
        1,
        sample_rate,
        sample_rate * 4,
        4,
        32,
        b"data",
        len(data),
    )
    path.write_bytes(header + data)


class WavChunkTests(unittest.TestCase):
    def test_pause_silence_is_complete_but_not_speech(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "pause.wav"
            write_silence(path, 0.5)
            self.assertTrue(is_complete_wav(path))
            self.assertFalse(is_usable_speech_wav(path))

    def test_speech_sine_is_usable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "speech.wav"
            samples = [0.2 * math.sin(2 * math.pi * 220 * i / 44100) for i in range(44100)]
            _write_float_wav(path, samples)
            self.assertTrue(is_usable_speech_wav(path, generated_samples=44100))

    def test_all_zero_speech_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "empty.wav"
            _write_float_wav(path, [0.0] * 319488)
            self.assertFalse(is_usable_speech_wav(path, generated_samples=319488))

    def test_overtrimmed_speech_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "short.wav"
            samples = [0.2 * math.sin(2 * math.pi * 220 * i / 44100) for i in range(65977)]
            _write_float_wav(path, samples)
            self.assertFalse(is_usable_speech_wav(path, generated_samples=378980))
            self.assertTrue(is_usable_speech_wav(path))

    def test_first_incomplete_skips_pauses_and_finds_silent_speech(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            lines = [
                "hello",
                "[pause 0.5s]",
                "world",
            ]
            speech = [0.2 * math.sin(2 * math.pi * 220 * i / 44100) for i in range(22050)]
            _write_float_wav(output / "output_001.wav", speech)
            write_silence(output / "output_002.wav", 0.5)
            _write_float_wav(output / "output_003.wav", [0.0] * 22050)
            self.assertEqual(first_incomplete_index(lines, output), 3)

    def test_skipped_silence_is_not_incomplete(self) -> None:
        from engine.s2_lib import mark_chunk_skipped

        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            lines = ["hello", "world"]
            speech = [0.2 * math.sin(2 * math.pi * 220 * i / 44100) for i in range(22050)]
            _write_float_wav(output / "output_001.wav", speech)
            write_silence(output / "output_002.wav", 0.4)
            mark_chunk_skipped(output / "output_002.wav")
            self.assertIsNone(first_incomplete_index(lines, output))

    def test_read_wav_stats_matches_header(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "a.wav"
            write_silence(path, 0.5)
            stats = read_wav_stats(path)
            assert stats is not None
            self.assertEqual(stats["n_samples"], 22050)
            self.assertEqual(stats["sample_rate"], 44100)
            self.assertEqual(stats["peak"], 0.0)

    def test_append_silence_extends_duration(self) -> None:
        from engine.s2_lib import append_silence

        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "speech.wav"
            samples = [0.2 * math.sin(2 * math.pi * 220 * i / 44100) for i in range(44100)]
            _write_float_wav(path, samples)
            append_silence(path, 0.18)
            stats = read_wav_stats(path)
            assert stats is not None
            self.assertEqual(stats["n_samples"], 44100 + 7938)
            self.assertGreater(stats["peak"], 0.1)

    def test_pad_speech_chunks_skips_pause_neighbors(self) -> None:
        from engine.s2_lib import pad_speech_chunks

        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            lines = ["hello", "[pause 0.5s]", "world"]
            speech = [0.2 * math.sin(2 * math.pi * 220 * i / 44100) for i in range(22050)]
            _write_float_wav(output / "output_001.wav", speech)
            write_silence(output / "output_002.wav", 0.5)
            _write_float_wav(output / "output_003.wav", speech)
            pad_speech_chunks(lines, output, 180)
            first = read_wav_stats(output / "output_001.wav")
            pause = read_wav_stats(output / "output_002.wav")
            last = read_wav_stats(output / "output_003.wav")
            assert first is not None and pause is not None and last is not None
            self.assertEqual(first["n_samples"], 22050)
            self.assertEqual(pause["n_samples"], 22050)
            self.assertEqual(last["n_samples"], 22050 + 7938)


if __name__ == "__main__":
    unittest.main()
