# Changelog

All notable changes to ttser are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] — 2026-08-20

### Added

- Unsigned macOS Intel `.dmg` (`x86_64`) from GitHub Actions alongside the Apple Silicon build
- **Create dictionary** in the Dictionaries dialog, writing a new JSON file (bundled apps use the user data directory)
- Cursor skills for Fish Audio S2 Pro text prep (`ttser-s2-text-prep`) and a ChatGPT-oriented podcast brief (`ttser-s2-podcast-chatgpt`)

### Changed

- macOS CI and Release jobs build both `macos-arm64` and `macos-x86_64` packages

## [0.5.0] — 2026-08-20

### Added

- Unsigned macOS `.app` / `.dmg` (Apple Silicon, CPU + Metal, bundled ffmpeg) built on GitHub Actions and attached to Releases
- Frozen-app layout: bundled tokenizer, dictionaries, voices, and `libs2_*` dylibs; user models and extra voices under `~/Library/Application Support/ttser`

### Changed

- GPU synthesis in a packaged Mac app launches the bundled `ttser-synth` helper instead of `python -m engine.s2_synth`

## [0.4.0] — 2026-08-20

### Added

- Synthesis parameters dialog before starting synthesis: sampling, threads, log level, GPU layers, codec placement, and device index filtered by the selected backend (CPU / Vulkan / CUDA / Metal)
- Configurable trailing silence after each synthesized line (`line_pause_ms`, default 180) so concatenated MP3 chunks do not butt together
- Per-parameter help buttons with English and Russian explanations from the s2.cpp README
- Reset button that restores synthesis parameter defaults without changing the selected backend, model, or voice

### Changed

- Generation parameters are no longer hard-coded in `engine/s2_lib.py`; confirmed dialog values are saved in QSettings and reused on the next run
- Vulkan keeps the audio codec on CPU even if a previous run saved GPU codec placement; the synthesis dialog no longer offers GPU codec for Vulkan

### Fixed

- Speech WAV chunks that are silence or much shorter than the generated PCM are no longer treated as complete after a GPU abort, so they are resynthesized instead of concatenated into the MP3

## [0.3.0] — 2026-08-20

### Added

- English UI (default) and Russian UI; switch language in **Settings → Interface → Language** without restart
- In-process translation catalog in `ttser/i18n.py` with live `retranslate()` for the main window and dialogs

### Changed

- GUI strings no longer hardcoded in Russian; English is the default for new installs and when `ui_language` is unset

## [0.2.0] — 2026-08-20

### Added

- Voice profile picker on the main window: model default, bundled `tankindycast`, or a user `.s2voice` file
- **Создать голос** dialog to encode a new `.s2voice` from reference audio and a transcript
- Flatpak user voice directory: `~/.var/app/com.tagantank.ttser/data/voices`
- Isolated GPU synthesis job (`python -m engine.s2_synth`) so a native abort cannot take down the GUI
- One automatic retry of a crashed line in a fresh process; a second failure inserts silence and continues
- Vulkan launch flags `GGML_VK_DISABLE_COOPMAT=1` and `GGML_VK_ALLOW_SYSMEM_FALLBACK=1` for RADV on AMD iGPUs

### Changed

- Bundled voice profile renamed from `tankvoice.s2voice` to `tankindycast.s2voice`
- Vulkan keeps the audio codec on CPU (`codec_follow_backend=0`) so AR inference does not share a second Vulkan context on UMA memory
- Settings download button is disabled when the selected GGUF is already on disk (label: **Модель уже скачана**)
- Starting synthesis disables all main-window fields and buttons except **Стоп**
- Stop on a GPU job terminates the child process immediately

### Fixed

- `vk::DeviceLostError` / RADV “context is lost” on AMD Radeon 780M no longer kills the whole application during long synthesis

## [0.1.0] — 2026-08-19

### Added

- First public release: PySide6 desktop TTS for Fish Audio S2 Pro on Linux and macOS
- Official `s2.cpp` git submodule and ctypes `libs2_*` backends (CPU, Vulkan, CUDA, Metal)
- Line-oriented UTF-8 input, pronunciation dictionaries, WAV chunks concatenated to MP3 via ffmpeg
- In-app Hugging Face download for `s2-pro-q4_k_m`, `s2-pro-q8_0`, and `s2-pro-f16`
- Linux Flatpak (`com.tagantank.ttser`, Freedesktop 24.08)
- GitHub Actions CI on `master`/PRs and Release publishing on `v*` tags

[0.6.0]: https://github.com/tagantank/ttser/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tagantank/ttser/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tagantank/ttser/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tagantank/ttser/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tagantank/ttser/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tagantank/ttser/releases/tag/v0.1.0
