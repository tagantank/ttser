# AGENTS.md

Local engineering reference for agents working on **ttser**. Read this before changing synthesis, backends, downloads, or Flatpak.

`s2.cpp/AGENTS.md` describes the C++ engine. Do not duplicate that work here.

## What this repo is

PySide6 desktop TTS for Fish Audio S2 Pro on Linux and macOS.

- GUI loads a UTF-8 text file (`one line = one chunk`)
- Pronunciation dictionaries can rewrite text before synthesis
- Synthesis goes through ctypes into a selected `libs2_*` plugin (not HTTP)
- WAV chunks are concatenated into one MP3 (`128k`) via ffmpeg
- Models are GGUF files downloaded from Hugging Face (`rodrigomt/s2-pro-gguf`)

This is **not** an HTTP TTS server. The `s2` CLI/server in the submodule is unused at runtime.

## Layout

| Path | Role |
|---|---|
| `ttser/` | GUI, settings, workers, backend detection, model catalog |
| `engine/` | ctypes wrapper, dictionaries, download, MP3 concat |
| `dictionaries/` | default JSON rules (`from` / `to` / `note`) |
| `s2.cpp/` | **git submodule** — official `https://github.com/rodrigomatta/s2.cpp.git` |
| `voices/` | bundled `tankindycast.s2voice` |
| `flatpak/` | manifest, launch script, prebuilt libs, SPIR-V headers, offline wheels |
| `macos/` | unsigned `.app` / `.dmg` (PyInstaller spec + collect script) |
| `lib/` | local plugin copies/symlinks (`make libs` / `make lib-dev`); gitignored |

Never vendor `s2.cpp` as a regular directory. Add it as a submodule (`git submodule add` / `make init-submodule`). Tokenizer is `s2.cpp/tokenizer.json`. The GitLab `s2.cpp` fork is not used.

## Backends

`engine/s2_lib.py` `backend_type` values:

| id | type | library | platforms |
|---|---|---|---|
| `cpu` | `-1` | `libs2_cpu.so` / `.dylib` | all |
| `vulkan` | `0` | `libs2_vulkan.so` | Linux |
| `cuda` | `1` | `libs2_cuda.so` | Linux |
| `metal` | `2` | `libs2_metal.dylib` | macOS |

GUI shows only backends whose library file exists (CPU is always listed). Resolution order: configured path → `lib/` → `flatpak/prebuilt/linux-x86_64/` → `s2.cpp/build-*-sdk/libs2.so`.

Set `LD_LIBRARY_PATH` to the library directory **before** `ctypes.CDLL` (native worker and Flatpak `ttser-launch.sh`). Host-built `.so` files on Fedora 44 fail inside Flatpak 24.08 (`GLIBC_2.43 not found`). Rebuild plugins inside `org.freedesktop.Sdk//24.08`.

`n_gpu_layers`: `-1` for GPU backends, `0` for CPU.

Vulkan `InitializeS2PipelineFromFiles` must pass `codec_follow_backend=0` (CPU codec). Auto-benchmarking the codec onto the GPU creates a second Vulkan context on the same UMA heap; on AMD Radeon 780M / RADV this contributes to `vk::DeviceLostError` during long `eval_cached` runs.

GPU synthesis (Vulkan/CUDA/Metal) runs in a child process (`python -m engine.s2_synth`, or `ttser-synth` inside the macOS `.app`). ggml `vk::DeviceLostError` calls `terminate()` and cannot be caught in the GUI process. On abort the worker retries the failed line once in a fresh process, then inserts silence and continues. Flatpak launch sets `GGML_VK_DISABLE_COOPMAT=1` and `GGML_VK_ALLOW_SYSMEM_FALLBACK=1` (RADV coopmat DeviceLost on Phoenix).

CPU synthesis stays in the GUI worker thread.

## ctypes / s2 export API

- `InitializeS2PipelineFromFiles` success is `1`, not `0`
- `S2Synthesize` success is `> 0` (frame count)
- Voice clone loads a bundled or user `.s2voice` profile selected in the main-window **Voice** dropdown. Default item uses the model's built-in voice (no profile). Profile transcripts come from the `.s2voice` file.
- New profiles are created via **Create voice** (reference audio + transcript) and saved as user `.s2voice` files
- UI language: English default; Russian via **Settings → Interface → Language** (`ui_language` in `QSettings`, catalogs in `ttser/i18n.py`)
- Cancel synthesis between lines via `should_cancel` → `SynthesisCancelled`. GPU jobs cancel by terminating the child process
- Lines like `[pause 500ms]` become silence WAVs, not model calls
- After synthesis, `line_pause_ms` (default 180) appends trailing silence to each speech chunk before MP3 concat, unless the next line is already `[pause …]`
- Vulkan: `codec_follow_backend=0`. GPU jobs use `python -m engine.s2_synth` with `skip_existing` so a DeviceLost abort can resume. Speech chunks that are silent or far shorter than the generated PCM are treated as incomplete and retried.

## Qt pitfalls

PySide `Signal(int, …)` is a 32-bit signed `int`. File sizes over ~2 GiB overflow. Model download progress must emit percent (`0–1000`) plus a **string** label, never raw byte counts.

`QProgressBar` range must stay in 32-bit range. Do not set maximum to file size in bytes.

Closing the settings dialog must cancel an in-flight model download (`DownloadCancelled`), delete the `.part` file, and not keep the incomplete GGUF.

## Settings

`QSettings("ttser", "ttser")`. Flatpak defaults:

- libs: `/app/lib/ttser/libs2_*.so`
- tokenizer: `/app/share/ttser/tokenizer.json`
- dictionaries: `/app/share/ttser/dictionaries/`
- models dir: `~/.var/app/com.tagantank.ttser/data/models`

Native tokenizer default: `s2.cpp/tokenizer.json` (migrate old `s2.cpp/models/tokenizer.json`).
Native voice dir: bundled `voices/tankindycast.s2voice` (native) or `/app/share/ttser/voices` (Flatpak). User-created profiles: same `voices/` on native, `~/.var/app/com.tagantank.ttser/data/voices` on Flatpak.

## Model download

Catalog: `ttser/model_catalog.py`. Resolve size with `Range: bytes=0-0` / `Content-Range` before trusting catalog `size_bytes`.

| id | file | size |
|---|---|---|
| `q4_k_m` | `s2-pro-q4_k_m.gguf` | 3 566 165 088 |
| `q8_0` | `s2-pro-q8_0.gguf` | 5 630 037 088 |
| `f16` | `s2-pro-f16.gguf` | 9 906 568 704 |

## Commands

```bash
make init-submodule
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
make lib-dev          # symlink prebuilt .so into lib/ for native GUI
python -m ttser
```

Host plugins (glibc of this machine, not for Flatpak):

```bash
make lib-cpu
make lib-vulkan       # Linux
make lib-cuda         # Linux, CUDA toolkit
make lib-metal        # macOS
```

Flatpak (Linux):

GitHub Actions (`.github/workflows/`):

- `ci.yml` — build Linux Flatpak and unsigned macOS `.dmg` on `master` and pull requests (artifacts only)
- `release.yml` — on tag `v*` build the same bundles and attach them to a GitHub Release

Wheels are not in git. CI runs `pip download --dest flatpak/wheels 'PySide6==6.11.2'` before `flatpak-builder`.

```bash
pip download --dest flatpak/wheels 'PySide6==6.11.2'    # if wheels/ is empty
flatpak-builder --force-clean --repo=repo build-flatpak flatpak/com.tagantank.ttser.yml
flatpak build-bundle repo ttser.flatpak com.tagantank.ttser
flatpak install --user --reinstall --bundle ttser.flatpak -y
```

Rebuild prebuilt libs **inside the SDK** — see README section “Rebuild prebuilt s2 libraries”. Copy `tokenizer.json` from `s2.cpp/tokenizer.json`.

Smoke:

```bash
python3 -c "from ttser.settings import load_settings; from ttser.backends import available_backends; s=load_settings(); print(s.tokenizer_path, [b.id for b in available_backends(s)])"
flatpak run --command=python3 com.tagantank.ttser -c "from ttser.backends import available_backends; from ttser.settings import load_settings; print([b.id for b in available_backends(load_settings())])"
```

## Do not

- Copy host `libs2_*.so` into `flatpak/prebuilt/`
- Pass multi-gigabyte ints through Qt `Signal(int, int)`
- Show CUDA/Metal/Vulkan when the matching library is missing
- Require reference text in the GUI
- Commit `/lib/`, `repo/`, `.flatpak-builder/`, `*.flatpak`, `flatpak/wheels/`, `*.gguf`, `*.dmg`
- Treat `s2.cpp/` as gitignored source; it is a submodule gitlink
