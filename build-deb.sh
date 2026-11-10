#!/usr/bin/env bash
# Rebuild the Kali .deb from this source tree. No root required.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(python3 -c 'import sys; sys.path.insert(0, "."); from glass_uninstaller import __version__; print(__version__)' 2>/dev/null || true)"
if [ -z "${VERSION:-}" ]; then
  VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/glass_uninstaller/__init__.py")"
fi
BUILD="$ROOT/.build/pkg"
OUT="$ROOT/dist"
rm -rf -- "$BUILD"
mkdir -p "$BUILD"/DEBIAN
install -d "$BUILD"/usr/bin "$BUILD"/usr/lib/miaomiao/assets \
  "$BUILD"/usr/share/applications "$BUILD"/usr/share/doc/liquid-uninstaller \
  "$BUILD"/usr/share/icons/hicolor/{128x128,256x256,512x512}/apps

cp "$ROOT/app.py" "$BUILD/usr/lib/miaomiao/app.py"
cp -a "$ROOT/glass_uninstaller" "$BUILD/usr/lib/miaomiao/glass_uninstaller"
cp "$ROOT/assets/icon-256.png" "$BUILD/usr/lib/miaomiao/assets/icon-256.png"
find "$BUILD/usr/lib/miaomiao" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$BUILD/usr/lib/miaomiao" -name '*.pyc' -delete
cc -O3 -std=c11 -fPIC -fvisibility=hidden -shared \
  -o "$BUILD/usr/lib/miaomiao/libmiaomiao.so" "$ROOT/native/core.c"
install -m755 "$ROOT/packaging/miaomiao" "$BUILD/usr/bin/miaomiao"
install -m644 "$ROOT/packaging/miaomiao.desktop" "$BUILD/usr/share/applications/miaomiao.desktop"
for s in 128 256 512; do
  install -m644 "$ROOT/packaging/icons/icon-${s}.png" \
    "$BUILD/usr/share/icons/hicolor/${s}x${s}/apps/miaomiao.png"
done
install -m644 "$ROOT/README.md" "$ROOT/README.en.md" "$BUILD/usr/share/doc/liquid-uninstaller/"
install -m644 "$ROOT/LICENSE" "$BUILD/usr/share/doc/liquid-uninstaller/LICENSE"
install -m644 "$ROOT/screenshot.png" "$ROOT/intro.png" "$ROOT/loading.png" "$ROOT/self-uninstall.png" \
  "$BUILD/usr/share/doc/liquid-uninstaller/"
install -m644 "$ROOT/debian/copyright" "$BUILD/usr/share/doc/liquid-uninstaller/copyright"
install -m644 "$ROOT/debian/changelog.Debian.gz" \
  "$BUILD/usr/share/doc/liquid-uninstaller/changelog.Debian.gz"
install -m755 "$ROOT/debian/postinst" "$BUILD/DEBIAN/postinst"
install -m755 "$ROOT/debian/postrm" "$BUILD/DEBIAN/postrm"

find "$BUILD/usr" -type d -exec chmod 755 {} +
find "$BUILD/usr" -type f -exec chmod 644 {} +
chmod 755 "$BUILD/usr/bin/miaomiao" "$BUILD/usr/lib/miaomiao/app.py" \
  "$BUILD/usr/lib/miaomiao/libmiaomiao.so"

INSTALLED_KB=$(du -sk "$BUILD/usr" | awk '{print $1}')
sed -e "s/^Version: .*/Version: $VERSION/" \
    -e "s/^Installed-Size: .*/Installed-Size: $INSTALLED_KB/" \
    "$ROOT/debian/control" > "$BUILD/DEBIAN/control"
(cd "$BUILD" && find usr -type f -print0 | sort -z | xargs -0 md5sum > DEBIAN/md5sums)
chmod 644 "$BUILD/DEBIAN/control" "$BUILD/DEBIAN/md5sums"

mkdir -p "$OUT"
DEB="$OUT/miaomiao_${VERSION}_amd64.deb"
rm -f "$DEB"
dpkg-deb --build --root-owner-group "$BUILD" "$DEB"
rm -rf -- "$ROOT/.build"
echo "built: $DEB"
