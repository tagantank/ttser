#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${TTSER_VERSION:-${1:-}}"
if [[ -z "${VERSION}" ]]; then
  VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
fi
ARCH="$(uname -m)"
JOBS="${JOBS:-$(sysctl -n hw.ncpu)}"
PAYLOAD="${ROOT}/macos/payload"
DIST="${ROOT}/dist"
WORK="${ROOT}/build/pyinstaller"
DMG_ROOT="${ROOT}/build/dmg-root"
ARTIFACT="${DIST}/ttser-${VERSION}-macos-${ARCH}.dmg"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "macos/build_app.sh must run on macOS" >&2
  exit 1
fi

export TTSER_VERSION="${VERSION}"

git submodule update --init --recursive

python3 -m pip install -e .
python3 -m pip install 'PySide6==6.11.2' 'pyinstaller>=6.3'

make libs JOBS="${JOBS}"

rm -rf "${PAYLOAD}"
mkdir -p "${PAYLOAD}/ttser/resources"
cp "${ROOT}/flatpak/com.tagantank.ttser.png" "${PAYLOAD}/ttser/resources/icon.png"

python3 "${ROOT}/macos/collect_native_libs.py" --repo "${ROOT}" --payload "${PAYLOAD}"

ICONSET="${ROOT}/macos/icon.iconset"
rm -rf "${ICONSET}"
mkdir -p "${ICONSET}"
sips -z 16 16 "${ROOT}/flatpak/com.tagantank.ttser.png" --out "${ICONSET}/icon_16x16.png" >/dev/null
sips -z 32 32 "${ROOT}/flatpak/com.tagantank.ttser.png" --out "${ICONSET}/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "${ROOT}/flatpak/com.tagantank.ttser.png" --out "${ICONSET}/icon_32x32.png" >/dev/null
sips -z 64 64 "${ROOT}/flatpak/com.tagantank.ttser.png" --out "${ICONSET}/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "${ROOT}/flatpak/com.tagantank.ttser.png" --out "${ICONSET}/icon_128x128.png" >/dev/null
sips -z 256 256 "${ROOT}/flatpak/com.tagantank.ttser.png" --out "${ICONSET}/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "${ROOT}/flatpak/com.tagantank.ttser.png" --out "${ICONSET}/icon_256x256.png" >/dev/null
iconutil -c icns "${ICONSET}" -o "${ROOT}/macos/ttser.icns"

rm -rf "${DIST}/ttser" "${DIST}/ttser.app" "${WORK}"
python3 -m PyInstaller "${ROOT}/macos/ttser.spec" --noconfirm --clean --distpath "${DIST}" --workpath "${WORK}"

APP="${DIST}/ttser.app"
if [[ ! -d "${APP}" ]]; then
  APP="${DIST}/ttser/ttser.app"
fi
if [[ ! -d "${APP}" ]]; then
  echo "PyInstaller did not produce ttser.app" >&2
  ls -la "${DIST}" >&2
  exit 1
fi

missing=0
for pattern in ttser-synth libs2_metal.dylib libs2_cpu.dylib ffmpeg tokenizer.json tankindycast.s2voice; do
  if ! find "${APP}" -name "${pattern}" | grep -q .; then
    echo "missing ${pattern} in ${APP}" >&2
    missing=1
  fi
done
if [[ "${missing}" -ne 0 ]]; then
  find "${APP}" | sed -n '1,200p' >&2
  exit 1
fi

# Ad-hoc signature so Apple Silicon will load the unsigned bundle after Gatekeeper bypass.
find "${APP}" -name '*.dylib' -o -name 'ffmpeg' -o -name 'ttser' -o -name 'ttser-synth' | while read -r bin; do
  codesign --force --sign - --timestamp=none "${bin}" >/dev/null 2>&1 || true
done
codesign --force --deep --sign - --timestamp=none "${APP}"

rm -rf "${DMG_ROOT}"
mkdir -p "${DMG_ROOT}"
cp -R "${APP}" "${DMG_ROOT}/ttser.app"
ln -s /Applications "${DMG_ROOT}/Applications"
cat > "${DMG_ROOT}/README.txt" <<EOF
ttser ${VERSION} for macOS (${ARCH})

This build is unsigned and not notarized.

1. Drag ttser.app to Applications.
2. Right-click ttser.app → Open, then confirm Open (Gatekeeper).
3. In Settings, download a GGUF model. Models are stored in
   ~/Library/Application Support/ttser/models
4. ffmpeg is bundled. CPU and Metal backends are included.

Do not upload GGUF files into the app bundle.
EOF

mkdir -p "${DIST}"
rm -f "${ARTIFACT}"
hdiutil create -volname "ttser ${VERSION}" -srcfolder "${DMG_ROOT}" -ov -format UDZO "${ARTIFACT}"
shasum -a 256 "${ARTIFACT}" | tee "${ARTIFACT}.sha256"
echo "Built ${ARTIFACT}"
