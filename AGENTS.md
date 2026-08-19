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
| `voices/` | bundled `tankvoice.s2voice` |
| `flatpak/` | manifest, launch script, prebuilt libs, SPIR-V headers, offline wheels |
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

## ctypes / s2 export API

- `InitializeS2PipelineFromFiles` success is `1`, not `0`
- `S2Synthesize` success is `> 0` (frame count)
- Voice clone uses `InitializeAudioPromptCodes`. The C API requires a non-empty reference transcript; GUI does not ask for one — pass `REFERENCE_PROMPT_PLACEHOLDER` (`"."`)
- Reference voice is optional: checkbox `Использовать пример голоса`. Unchecked → do not pass reference audio
- Cancel synthesis between lines via `should_cancel` → `SynthesisCancelled`
- Lines like `[pause 500ms]` become silence WAVs, not model calls

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
Native voice dir: `voices/` (bundled `voices/tankvoice.s2voice`). Flatpak: `/app/share/ttser/voices`.

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

```bash
pip download --dest flatpak/wheels PySide6    # if wheels/ is empty
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
- Commit `/lib/`, `repo/`, `.flatpak-builder/`, `*.flatpak`, `flatpak/wheels/`, `*.gguf`
- Treat `s2.cpp/` as gitignored source; it is a submodule gitlink
