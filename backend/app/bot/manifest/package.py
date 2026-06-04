"""
package.py — generates the Teams app manifest.zip.

Run from the backend directory:
    python app/bot/manifest/package.py

Produces: app/bot/manifest/manifest.zip
Upload this zip in Teams → Apps → Manage your apps → Upload an app.
"""

import os
import struct
import zipfile
import zlib

# ── Paths ─────────────────────────────────────────────────────────────────
MANIFEST_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_JSON = os.path.join(MANIFEST_DIR, "manifest.json")
COLOR_PNG = os.path.join(MANIFEST_DIR, "color.png")
OUTLINE_PNG = os.path.join(MANIFEST_DIR, "outline.png")
OUTPUT_ZIP = os.path.join(MANIFEST_DIR, "manifest.zip")


def _make_png(width: int, height: int, r: int, g: int, b: int) -> bytes:
    """
    Generate a minimal valid PNG of a solid-colour square.
    No external libraries required.
    """
    def _chunk(name: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
        return length + name + data + crc

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR: width, height, bit depth=8, colour type=2 (RGB), ...
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT: raw pixel rows, each prefixed with filter byte 0
    raw_row = b"\x00" + bytes([r, g, b] * width)
    raw_image = raw_row * height
    compressed = zlib.compress(raw_image, 9)
    idat = _chunk(b"IDAT", compressed)

    # IEND
    iend = _chunk(b"IEND", b"")

    return sig + ihdr + idat + iend


def _ensure_icons() -> None:
    """Create placeholder icon PNGs if they don't already exist."""
    if not os.path.exists(COLOR_PNG):
        print(f"  Creating placeholder color.png (192x192 dark navy)...")
        png_data = _make_png(192, 192, 26, 26, 46)   # #1a1a2e
        with open(COLOR_PNG, "wb") as f:
            f.write(png_data)

    if not os.path.exists(OUTLINE_PNG):
        print(f"  Creating placeholder outline.png (32x32 white)...")
        png_data = _make_png(32, 32, 255, 255, 255)
        with open(OUTLINE_PNG, "wb") as f:
            f.write(png_data)


def package() -> None:
    """Bundle manifest.json + icons into manifest.zip."""
    print("CloudComply AI - Teams Manifest Packager")
    print("=" * 45)

    _ensure_icons()

    # Verify manifest exists
    if not os.path.exists(MANIFEST_JSON):
        raise FileNotFoundError(f"manifest.json not found at {MANIFEST_JSON}")

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(MANIFEST_JSON, arcname="manifest.json")
        zf.write(COLOR_PNG, arcname="color.png")
        zf.write(OUTLINE_PNG, arcname="outline.png")

    size_kb = os.path.getsize(OUTPUT_ZIP) / 1024
    print(f"\n  ✅ manifest.zip created ({size_kb:.1f} KB)")
    print(f"     → {OUTPUT_ZIP}")
    print()
    print("Next step:")
    print("  Teams → Apps → Manage your apps → Upload an app")
    print("  → Upload a custom app → select manifest.zip")


if __name__ == "__main__":
    package()
