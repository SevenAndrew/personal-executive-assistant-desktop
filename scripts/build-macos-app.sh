#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="${0:A:h:h}"
SOURCE_ICON="$PROJECT_ROOT/pea_app/assets/pea-logo.png"
FALLBACK_ICON="$PROJECT_ROOT/pea_app/assets/PEA.icns"
BUILD_DIRECTORY="$PROJECT_ROOT/build/macos"
ICONSET="$BUILD_DIRECTORY/PEA.iconset"
ICON_FILE="$BUILD_DIRECTORY/PEA.icns"
APP="$PROJECT_ROOT/dist/PEA.app"
VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$PROJECT_ROOT/pea_app/__init__.py")"
ARCHITECTURE="$(uname -m)"
ARCHIVE="$PROJECT_ROOT/dist/PEA-$VERSION-macos-$ARCHITECTURE.zip"

if [[ "$ARCHITECTURE" != "arm64" ]]; then
    print -u2 "This build configuration currently supports Apple silicon Macs only."
    exit 1
fi

mkdir -p "$ICONSET"
for specification in \
    "16 icon_16x16.png" \
    "32 icon_16x16@2x.png" \
    "32 icon_32x32.png" \
    "64 icon_32x32@2x.png" \
    "128 icon_128x128.png" \
    "256 icon_128x128@2x.png" \
    "256 icon_256x256.png" \
    "512 icon_256x256@2x.png" \
    "512 icon_512x512.png" \
    "1024 icon_512x512@2x.png"; do
    size="${specification%% *}"
    filename="${specification#* }"
    sips -z "$size" "$size" "$SOURCE_ICON" --out "$ICONSET/$filename" >/dev/null
done
if ! iconutil --convert icns --output "$ICON_FILE" "$ICONSET"; then
    print -u2 "iconutil rejected the generated iconset; using the reviewed bundled icon."
    cp "$FALLBACK_ICON" "$ICON_FILE"
fi

cd "$PROJECT_ROOT"
uv sync --group build --group test
uv run --group build pyinstaller --noconfirm --clean packaging/PEA.spec
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARCHIVE"

print "Created $APP"
print "Created $ARCHIVE"
