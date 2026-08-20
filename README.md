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
| `macos/` | unsigned `.app` / `.dmg` packaging for GitHub Actions |
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
make lib-dev      # Linux only: symlink flatpak/prebuilt/*.so into lib/
```

Expected names in `lib/`:

- `libs2_cpu.so` (Linux) / `libs2_cpu.dylib` (macOS)
- `libs2_vulkan.so` (Linux)
- `libs2_cuda.so` (Linux)
- `libs2_metal.dylib` (macOS)

macOS walkthrough (CLT, Homebrew, venv, Metal, models): [Build on macOS](#build-on-macos).

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

Linux and macOS share the same Python entry point. Start it from the **repository root** so relative paths (`lib/`, `s2.cpp/tokenizer.json`, `dictionaries/`, `voices/`) resolve. Needs `ffmpeg` on `PATH` for the final MP3.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
make libs
python -m ttser
```

On Linux only, you can skip compiling and symlink the Flatpak prebuilts (`make lib-dev`). Do **not** use `make lib-dev` on macOS: it links `flatpak/prebuilt/linux-x86_64/*.so`, which cannot load on Darwin.

Voice: pick **Model default voice** for the model default, or choose a saved profile such as `tankindycast`. Use **Create voice** to encode a new `.s2voice` from reference audio and transcript.

## Build on macOS

ttser on Mac can be used as a native PySide6 checkout (`python -m ttser`) or as an unsigned `.app` from Releases. Settings show **CPU** and **Metal** only. Vulkan (MoltenVK) and CUDA are not built.

Apple Silicon is the intended target. Intel Macs with Metal can compile the same way, but CPU fallback is slow and there is no NVIDIA path.

### What you will have

| Piece | Path |
|---|---|
| GUI + ctypes client | `python -m ttser` from repo root |
| CPU plugin | `lib/libs2_cpu.dylib` |
| Metal plugin | `lib/libs2_metal.dylib` |
| Tokenizer | `s2.cpp/tokenizer.json` (from the submodule) |
| Voice | `voices/tankindycast.s2voice` |
| GGUF models | `s2.cpp/models/` (downloaded, not in git) |

`make libs` copies `s2.cpp/build-cpu/libs2.dylib` and `s2.cpp/build-metal/libs2.dylib` into `lib/` under those names. ggml is a **shared** library by default, so keep both `s2.cpp/build-cpu` and `s2.cpp/build-metal` after the copy: `libs2_*.dylib` still loads `libggml*.dylib` from the CMake rpath in those trees.

### Requirements

- macOS 13+ recommended (Apple Silicon: 16 GiB RAM is comfortable for `q8_0`; 8 GiB → prefer `q4_k_m`)
- [Xcode Command Line Tools](https://developer.apple.com/download/all/?q=command%20line%20tools) (Clang, `cmake` can also come from Homebrew, `patch`, Metal SDK)
- [Homebrew](https://brew.sh)
- Python **≥ 3.11** (Apple `/usr/bin/python3` is often 3.9 — too old)
- Disk: ~1 GiB for the engine build, plus 3.3–9.2 GiB per GGUF

### 1. Command Line Tools and Homebrew packages

```bash
xcode-select --install
```

If CLT are already installed, `xcode-select -p` prints `/Library/Developer/CommandLineTools` or an Xcode.app path.

```bash
brew install git cmake python@3.12 ffmpeg
```

Confirm the toolchain (all three should succeed):

```bash
clang --version
cmake --version          # ≥ 3.14
python3.12 --version     # ≥ 3.11
ffmpeg -version
patch --version          # CMake applies s2.cpp/patches/*.patch; CLT provides patch
uname -m                 # arm64 on Apple Silicon; x86_64 on Intel / Rosetta
```

Add Homebrew to `PATH` if `brew` is missing after install:

- Apple Silicon: `eval "$(/opt/homebrew/bin/brew shellenv)"`
- Intel: `eval "$(/usr/local/bin/brew shellenv)"`

### 2. Clone with submodules

`s2.cpp` is a git submodule; `ggml` is a submodule **inside** `s2.cpp`. Both must be present.

```bash
git clone --recurse-submodules https://github.com/tagantank/ttser.git
cd ttser
```

If the clone already exists without submodules:

```bash
cd ttser
make init-submodule    # git submodule update --init --recursive
```

Check:

```bash
test -f s2.cpp/tokenizer.json && test -f s2.cpp/ggml/CMakeLists.txt && echo "submodules ok"
```

### 3. Python venv and GUI deps

Use the Homebrew interpreter so the venv is 3.12 and matches `uname -m` (do not mix Rosetta Python with an `arm64` dylib).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -c "import platform, sys; print(sys.version); print(platform.machine())"
pip install -U pip
pip install -e .
```

`PySide6` comes from PyPI. First launch needs a logged-in GUI session (not a headless SSH tty).

### 4. Build CPU and Metal plugins

From the repo root, still inside the venv:

```bash
make libs
```

That is `make lib-cpu` plus `make lib-metal` on Darwin. Equivalent by hand:

```bash
# CPU
cmake -S s2.cpp -B s2.cpp/build-cpu \
  -DCMAKE_BUILD_TYPE=Release \
  -DS2_BUILD_SHARED_LIBRARIES=ON
cmake --build s2.cpp/build-cpu --config Release -j "$(sysctl -n hw.ncpu)"

# Metal (Apple GPU)
cmake -S s2.cpp -B s2.cpp/build-metal \
  -DCMAKE_BUILD_TYPE=Release \
  -DS2_METAL=ON \
  -DS2_BUILD_SHARED_LIBRARIES=ON
cmake --build s2.cpp/build-metal --config Release -j "$(sysctl -n hw.ncpu)"

mkdir -p lib
cp s2.cpp/build-cpu/libs2.dylib   lib/libs2_cpu.dylib
cp s2.cpp/build-metal/libs2.dylib lib/libs2_metal.dylib
```

Do **not** run `make lib-vulkan` / `make lib-cuda` / `make lib-dev` here.

Expected:

```text
lib/libs2_cpu.dylib
lib/libs2_metal.dylib
```

Metal shaders are embedded (`GGML_METAL_EMBED_LIBRARY` defaults on when Metal is on). You do not copy a separate `.metallib`.

### 5. Verify the dylibs

Architecture of Python, Clang, and the plugins must match:

```bash
file lib/libs2_cpu.dylib lib/libs2_metal.dylib
python -c "import platform; print(platform.machine())"
```

Load test (from repo root, venv active):

```bash
python -c "import ctypes; ctypes.CDLL('lib/libs2_cpu.dylib'); print('cpu ok')"
python -c "import ctypes; ctypes.CDLL('lib/libs2_metal.dylib'); print('metal ok')"
python -c "from ttser.settings import load_settings; from ttser.backends import available_backends; s=load_settings(); print(s.tokenizer_path, [b.id for b in available_backends(s)])"
```

The last line should print `s2.cpp/tokenizer.json` and `['cpu', 'metal']` once both dylibs exist. CPU is listed even if `libs2_cpu.dylib` is missing; Metal appears only when `lib/libs2_metal.dylib` is a real file.

If load fails with `image not found` / `Library not loaded: …libggml…`, inspect rpath and keep the CMake build directories:

```bash
otool -L lib/libs2_metal.dylib
otool -l lib/libs2_metal.dylib | grep -A2 LC_RPATH
```

Do not `rm -rf s2.cpp/build-cpu` or `s2.cpp/build-metal` after `make libs`.

Wrong architecture (`mach-o, but wrong architecture`) means the Terminal is under Rosetta (`uname -m` is `x86_64` on Apple Silicon) or the venv was created with a different Python. Open a native Terminal, recreate `.venv`, rebuild `make libs`.

### 6. Model

Tokenizer is already in the submodule. GGUF files are not. Easiest: start the GUI, open **Settings**, download `s2-pro-q8_0.gguf` (recommended) or `s2-pro-q4_k_m.gguf`. Closing Settings cancels an in-flight download and deletes the `.part` file.

CLI alternative:

```bash
mkdir -p s2.cpp/models
pip install -U "huggingface_hub[cli]"
hf download rodrigomt/s2-pro-gguf --include 's2-pro-q8_0.gguf' --local-dir s2.cpp/models
```

Native default model dir is `s2.cpp/models/`.

### 7. Run

```bash
cd /path/to/ttser
source .venv/bin/activate
python -m ttser
```

In **Settings**:

1. **Backend** → **Metal** (leave **CPU** only for debugging).
2. Confirm **Tokenizer** is `s2.cpp/tokenizer.json`.
3. Download or select a GGUF.
4. **Interface → Language** if you want Russian UI.

Then on the main window pick a voice (`tankindycast` or **Model default voice**), open a UTF-8 text file (`one line = one chunk`), and start synthesis. Metal jobs run in a child process (`python -m engine.s2_synth`); GPU layers default to `-1` (all layers). The audio codec follows the Metal backend (unlike Vulkan on Linux, which keeps the codec on CPU).

`ffmpeg` must be on `PATH` for the final 128k MP3.

### 8. Rebuild / clean

```bash
rm -rf s2.cpp/build-cpu s2.cpp/build-metal lib/libs2_*.dylib
make libs
```

Settings live in `~/Library/Preferences/com.ttser.ttser.plist` (`QSettings("ttser", "ttser")`). User voices stay in `voices/` next to the repo (or the path set in Settings).

### Troubleshooting

| Symptom | What to check |
|---|---|
| Metal missing in Settings | `lib/libs2_metal.dylib` is not a file; run `make lib-metal` |
| `GLIBC` / `.so` errors | You used `make lib-dev` or copied Linux prebuilts; rebuild with `make libs` |
| `image not found` for ggml | Build dirs deleted; rerun `make libs` and leave `s2.cpp/build-*` in place |
| `wrong architecture` | Rosetta vs native mismatch; `uname -m` vs `file lib/*.dylib` vs `platform.machine()` |
| `S2_AUTO_APPLY_LOCAL_PATCHES` / `patch` missing | Install CLT; `which patch` |
| PySide6 / Qt fails to start | Need a GUI login session; Python &lt; 3.11; recreate venv with `python3.12` |
| Final file is WAV-only / concat error | `ffmpeg` not on `PATH` (`brew install ffmpeg`) |
| OOM / beachball on 8 GiB Mac | Use `q4_k_m`, close other apps, or switch backend to CPU |
| Synthesis starts then child dies | Metal abort is isolated in `python -m engine.s2_synth`; the GUI retries the failed line once, then inserts silence |

Unsigned `.app` builds from GitHub Actions are ad-hoc signed, not notarized. After dragging `ttser.app` to Applications, open it with **Right-click → Open**. For day-to-day development, keep the venv and run `python -m ttser` from the checkout.

## Dictionaries

Defaults:

- `dictionaries/s2_terms_ru.json`
- `dictionaries/s2_pronunciation_ru.json`

In GUI (**Dictionaries**): connect JSON files, edit rows (`from`, `to`, `note`), save back to disk. Toggle **Apply dictionaries** on the main window.

Lines of the form `[pause 500ms]` become silence, not model output.

By default each synthesized line also gets **180 ms** of trailing silence before the WAV chunks are concatenated (`Line pause` in the synthesis dialog). Set it to `0` to disable. Explicit `[pause …]` lines are left unchanged, and a speech line is not padded when the next line is already a pause.

## Packages

GitHub Actions builds the Linux Flatpak and an unsigned macOS `.dmg` on `master`/PRs (CI artifacts) and publishes both to [Releases](https://github.com/tagantank/ttser/releases) on a `v*` tag:

```bash
git tag v0.5.0
git push origin v0.5.0
```

Release assets:

- `ttser-<tag>-linux-x86_64.flatpak`
- `ttser-<tag>-macos-arm64.dmg` (unsigned Apple Silicon `.app`)

```bash
flatpak install --user --bundle ttser-v0.5.0-linux-x86_64.flatpak
flatpak run com.tagantank.ttser
```

The macOS DMG is not notarized. Drag `ttser.app` to Applications, then **Right-click → Open**. Models download in Settings into `~/Library/Application Support/ttser/models`.

Local macOS bundle (must run on Darwin):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e . 'PySide6==6.11.2' 'pyinstaller>=6.3'
brew install cmake ffmpeg
bash macos/build_app.sh
```

Local Flatpak build. Offline PySide wheels are gitignored:

```bash
pip download --dest flatpak/wheels 'PySide6==6.11.2'
sudo dnf install flatpak-builder
flatpak-builder --force-clean --repo=repo build-flatpak flatpak/com.tagantank.ttser.yml
flatpak build-bundle repo ttser.flatpak com.tagantank.ttser
flatpak install --user --reinstall --bundle ttser.flatpak -y
flatpak run com.tagantank.ttser
```

## Build Flatpak (Linux)

Manifest: `flatpak/com.tagantank.ttser.yml`. App id: `com.tagantank.ttser`.

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
