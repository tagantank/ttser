# ttser — Desktop TTS for Fish Audio S2 Pro

PySide6 desktop app for Linux and macOS that turns prepared UTF-8 text into MP3 using Fish Audio S2 Pro.

Agent-oriented notes: [`AGENTS.md`](AGENTS.md). C++ engine: [`s2.cpp/AGENTS.md`](s2.cpp/AGENTS.md) after `make init-submodule`. Release notes: [`CHANGELOG.md`](CHANGELOG.md).

## What it does

- Loads prepared UTF-8 text (`one line = one chunk`)
- Optionally applies pronunciation dictionaries before synthesis
- Uses one selected `libs2_*` plugin (`cpu`, `vulkan`, `cuda`, or `metal`)
- Selects a voice profile from the main window (**Model default voice**, bundled `tankindycast`, or user `.s2voice` files)
- English UI by default; switch to Russian in **Settings → Interface → Language**
- Can stop synthesis (GPU jobs terminate the child process)
- Downloads GGUF models from Hugging Face in Settings, with cancel on dialog close
- Writes WAV chunks and concatenates a final MP3 (`128k`, needs `ffmpeg`)
- Lets you add/edit/delete dictionary entries in the GUI

This is a desktop ctypes client of `s2.cpp`, not an HTTP TTS server.

## Platform / backend matrix

Only backends whose library file exists are shown in Settings (CPU is always listed).

- Linux: `CPU`, `Vulkan`, `CUDA`
- macOS: `CPU`, `Metal`
- Vulkan on macOS (MoltenVK) is not included
- Vulkan on AMD iGPUs (RADV) keeps the audio codec on CPU and disables ggml coopmat; a GPU device-lost abort no longer kills the GUI

## Repository layout

| Path | Role |
|---|---|
| `ttser/` | GUI, settings, download/synthesis workers |
| `engine/` | ctypes wrapper, dictionaries, download, MP3 concat |
| `dictionaries/` | default JSON pronunciation rules |
| `s2.cpp/` | git submodule — official engine |
| `voices/` | bundled voice profile (`tankindycast.s2voice`) |
| `flatpak/` | Linux package: manifest, prebuilt libs, icon |
| `lib/` | local plugin copies (gitignored; `make libs` / `make lib-dev`) |

## s2.cpp submodule

```text
https://github.com/rodrigomatta/s2.cpp.git
```

Initialize:

```bash
make init-submodule
```

Do not copy the engine in as a normal directory. Add it as a submodule so git stores a gitlink.

Tokenizer and CUDA/Vulkan ggml patches come from that official tree (`s2.cpp/tokenizer.json`, `s2.cpp/patches/`). The bundled voice profile is `voices/tankindycast.s2voice` in this repository.

## Build s2 plugins

Native plugins use the host glibc (fine for `python -m ttser`, **not** for Flatpak):

```bash
make libs
```

Or:

```bash
make lib-cpu
make lib-vulkan   # Linux only
make lib-cuda     # Linux only, CUDA toolkit
make lib-metal    # macOS only
make lib-dev      # symlink flatpak/prebuilt/*.so into lib/
```

Expected names in `lib/`:

- `libs2_cpu.so` (Linux) / `libs2_cpu.dylib` (macOS)
- `libs2_vulkan.so` (Linux)
- `libs2_cuda.so` (Linux)
- `libs2_metal.dylib` (macOS)

## Model and tokenizer

Tokenizer (official submodule):

- `s2.cpp/tokenizer.json`

Models (not in git; download in Settings or with `hf`):

- native default dir: `s2.cpp/models/`
- Flatpak: `~/.var/app/com.tagantank.ttser/data/models/`

| Variant | Size | When to use |
|---|---|---|
| `s2-pro-q4_k_m.gguf` | ~3.3 GiB | faster on CPU, fallback |
| `s2-pro-q8_0.gguf` | ~5.2 GiB | recommended quality |
| `s2-pro-f16.gguf` | ~9.2 GiB | max quality, much slower on CPU |

```bash
hf download rodrigomt/s2-pro-gguf --include 's2-pro-q8_0.gguf' --local-dir s2.cpp/models
```

## Voice profile

Bundled `.s2voice` file:

- `voices/tankindycast.s2voice`
- Settings **Voice dir**: bundled path (`voices/` native, `/app/share/ttser/voices` Flatpak)

Extra user profiles live in the same directory on native builds, or in `~/.var/app/com.tagantank.ttser/data/voices` on Flatpak. Only `tankindycast.s2voice` is tracked in git.

## Run (native)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
make lib-dev    # or make libs
python -m ttser
```

Needs `ffmpeg` on `PATH` for the final MP3.

Voice: pick **Model default voice** for the model default, or choose a saved profile such as `tankindycast`. Use **Create voice** to encode a new `.s2voice` from reference audio and transcript.

## Dictionaries

Defaults:

- `dictionaries/s2_terms_ru.json`
- `dictionaries/s2_pronunciation_ru.json`

In GUI (**Dictionaries**): connect JSON files, edit rows (`from`, `to`, `note`), save back to disk. Toggle **Apply dictionaries** on the main window.

Lines of the form `[pause 500ms]` become silence, not model output.

## Build Flatpak (Linux)

Manifest: `flatpak/com.tagantank.ttser.yml`. App id: `com.tagantank.ttser`.

GitHub Actions builds the bundle on `master`/PRs (CI artifact) and publishes it to [Releases](https://github.com/tagantank/ttser/releases) on a `v*` tag:

```bash
git tag v0.2.0
git push origin v0.2.0
```

Asset name: `ttser-<tag>-linux-x86_64.flatpak`.

```bash
flatpak install --user --bundle ttser-v0.2.0-linux-x86_64.flatpak
flatpak run com.tagantank.ttser
```

Local build. Offline PySide wheels are gitignored:

```bash
pip download --dest flatpak/wheels 'PySide6==6.11.2'
sudo dnf install flatpak-builder
flatpak-builder --force-clean --repo=repo build-flatpak flatpak/com.tagantank.ttser.yml
flatpak build-bundle repo ttser.flatpak com.tagantank.ttser
flatpak install --user --reinstall --bundle ttser.flatpak -y
flatpak run com.tagantank.ttser
```

### Rebuild prebuilt s2 libraries (Flatpak SDK)

The manifest installs binaries from `flatpak/prebuilt/linux-x86_64/`.

Do **not** copy `libs2_*.so` built on the host (e.g. Fedora 44 / glibc 2.43). Inside runtime 24.08 they fail with:

```text
GLIBC_2.43 not found
```

Rebuild inside `org.freedesktop.Sdk//24.08`.

```bash
make init-submodule
flatpak install org.freedesktop.Sdk//24.08 org.freedesktop.Platform//24.08
```

Vulkan SDK is missing `spirv/unified1/spirv.hpp`. Copy once from the host (Fedora: `spirv-tools-devel` / `vulkan-headers`):

```bash
mkdir -p flatpak/deps/spirv-include
cp -a /usr/include/spirv flatpak/deps/spirv-include/
```

From repo root:

```bash
REPO="$(pwd)"
SPIRV_INC="$REPO/flatpak/deps/spirv-include"
OUT="$REPO/flatpak/prebuilt/linux-x86_64"

flatpak run \
  --filesystem="$REPO" \
  --command=sh \
  org.freedesktop.Sdk//24.08 -lc "
set -euo pipefail
cd \"$REPO/s2.cpp\"
git submodule update --init --recursive 2>/dev/null || true

cmake -S . -B build-flatpak-sdk -DCMAKE_BUILD_TYPE=Release -DS2_BUILD_SHARED_LIBRARIES=ON
cmake --build build-flatpak-sdk -j \"\$(nproc)\"

cmake -S . -B build-flatpak-vulkan-sdk \
  -DCMAKE_BUILD_TYPE=Release \
  -DS2_VULKAN=ON \
  -DS2_BUILD_SHARED_LIBRARIES=ON \
  -DCMAKE_CXX_FLAGS=\"-I${SPIRV_INC}\" \
  -DCMAKE_C_FLAGS=\"-I${SPIRV_INC}\"
cmake --build build-flatpak-vulkan-sdk -j \"\$(nproc)\"

mkdir -p \"$OUT\"
cp build-flatpak-sdk/libs2.so \"$OUT/libs2_cpu.so\"
cp build-flatpak-vulkan-sdk/libs2.so \"$OUT/libs2_vulkan.so\"
cp build-flatpak-vulkan-sdk/ggml/src/libggml-base.so \"$OUT/\"
cp build-flatpak-vulkan-sdk/ggml/src/libggml-cpu.so \"$OUT/\"
cp build-flatpak-vulkan-sdk/ggml/src/libggml.so \"$OUT/\"
cp build-flatpak-vulkan-sdk/ggml/src/ggml-vulkan/libggml-vulkan.so \"$OUT/\"
cp tokenizer.json \"$OUT/tokenizer.json\"
ls -lh \"$OUT\"
"
```

Expected in `flatpak/prebuilt/linux-x86_64/`:

- `libs2_cpu.so`, `libs2_vulkan.so`
- `libggml-base.so`, `libggml-cpu.so`, `libggml.so`, `libggml-vulkan.so`
- `tokenizer.json` (from `s2.cpp/tokenizer.json`)

Then rebuild and reinstall the bundle (commands above).

Smoke test:

```bash
flatpak run --command=sh com.tagantank.ttser -lc '
export LD_LIBRARY_PATH=/app/lib/ttser
python3 -c "import ctypes; ctypes.CDLL(\"/app/lib/ttser/libs2_cpu.so\"); print(\"OK\")"
'
```

## License

Weights are under the Fish Audio Research License (non-commercial by default). Commercial use needs a separate agreement with Fish Audio.
