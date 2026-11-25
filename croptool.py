#!/usr/bin/env python3
"""croptool – Bilder auf eine feste Zielgröße bringen, ohne sie zu verzerren.

Das Bild wird unter Beibehaltung des Seitenverhältnisses so skaliert, dass es
vollständig in die Zielgröße passt (Standard: 1244 × 700), mittig platziert und
mit transparenten Rändern aufgefüllt. Ausgabe ist immer PNG (wegen der
Transparenz). Arbeitet komplett offline.

Beispiele:
    croptool.py foto.jpg                  -> foto_1244x700.png (neben dem Original)
    croptool.py a.png b.jpg -s 1920x1080  -> a_1920x1080.png, b_1920x1080.png
    croptool.py foto.jpg -o ~/Desktop/ergebnis.png
    croptool.py *.jpg -d ~/Desktop/fertig
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

__version__ = "1.0.0"

DEFAULT_WIDTH = 1244
DEFAULT_HEIGHT = 700

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - hängt von der Installation ab
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]


class CropToolError(Exception):
    """Fehler, der dem Benutzer als verständliche Meldung angezeigt wird."""


# --------------------------------------------------------------------------- #
# Bildverarbeitung
# --------------------------------------------------------------------------- #

def fit_size(src_w: int, src_h: int, dst_w: int, dst_h: int) -> tuple[int, int]:
    """Größe, auf die (src_w, src_h) skaliert wird, um in (dst_w, dst_h) zu passen."""
    scale = min(dst_w / src_w, dst_h / src_h)
    new_w = min(dst_w, max(1, round(src_w * scale)))
    new_h = min(dst_h, max(1, round(src_h * scale)))
    return new_w, new_h


def _to_rgba(img: "Image.Image") -> tuple["Image.Image", bytes | None]:
    """Bild in RGBA umwandeln. Liefert zusätzlich das passende ICC-Profil (oder None)."""
    icc = img.info.get("icc_profile")

    if img.mode == "RGBA":
        return img, icc
    if img.mode in ("RGB", "P", "PA"):
        # RGB-Profile (z. B. Display P3 vom iPhone) bleiben gültig.
        return img.convert("RGBA"), icc

    if img.mode == "CMYK":
        if icc:
            try:
                from PIL import ImageCms

                srgb = ImageCms.createProfile("sRGB")
                rgb = ImageCms.profileToProfile(
                    img, io.BytesIO(icc), srgb, outputMode="RGB"
                )
                return rgb.convert("RGBA"), None
            except Exception:
                pass
        return img.convert("RGB").convert("RGBA"), None

    if img.mode.startswith("I;16") or img.mode == "I":
        # 16-Bit-Graustufen auf 8 Bit herunterrechnen statt abzuschneiden.
        img = img.convert("I").point(lambda v: v * (1 / 256)).convert("L")

    # Graustufen-/sonstige Profile passen nicht zu einem RGBA-Bild -> verwerfen.
    return img.convert("RGBA"), None


def letterbox(img: "Image.Image", width: int, height: int) -> "Image.Image":
    """Bild einpassen, zentrieren und mit transparenten Rändern auf width × height bringen."""
    img = ImageOps.exif_transpose(img)  # Hochkant-Fotos richtig drehen
    rgba, icc = _to_rgba(img)

    new_size = fit_size(rgba.width, rgba.height, width, height)
    if new_size != rgba.size:
        rgba = rgba.resize(new_size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    offset = ((width - rgba.width) // 2, (height - rgba.height) // 2)
    canvas.paste(rgba, offset)
    if icc:
        canvas.info["icc_profile"] = icc
    return canvas


def process_file(src: Path, dst: Path, width: int, height: int) -> Path:
    """Eine Datei verarbeiten und als PNG nach dst schreiben."""
    if not src.is_file():
        raise CropToolError(f"Datei nicht gefunden: {src}")
    if src.resolve() == dst.resolve():
        raise CropToolError(f"Ausgabe würde das Original überschreiben: {src}")

    try:
        with Image.open(src) as img:
            img.load()
            result = letterbox(img, width, height)
    except CropToolError:
        raise
    except Exception as exc:
        raise CropToolError(f"Kann {src.name} nicht lesen: {exc}") from exc

    dst.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs = {"format": "PNG", "optimize": True}
    if result.info.get("icc_profile"):
        save_kwargs["icc_profile"] = result.info["icc_profile"]

    # Erst in eine temporäre Datei schreiben, dann umbenennen -> keine halben Dateien.
    fd, tmp_name = tempfile.mkstemp(prefix=".croptool-", suffix=".png", dir=dst.parent)
    os.close(fd)
    try:
        result.save(tmp_name, **save_kwargs)
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, dst)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return dst


# --------------------------------------------------------------------------- #
# Kommandozeile
# --------------------------------------------------------------------------- #

def parse_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*[x×X*]\s*(\d+)\s*", value)
    if not match:
        raise argparse.ArgumentTypeError(
            f"ungültige Größe '{value}', erwartet z. B. 1244x700"
        )
    w, h = int(match.group(1)), int(match.group(2))
    if w < 1 or h < 1:
        raise argparse.ArgumentTypeError("Breite und Höhe müssen größer als 0 sein")
    return w, h


def output_path(src: Path, width: int, height: int, suffix: str | None,
                out_dir: Path | None) -> Path:
    if suffix is None:
        suffix = f"_{width}x{height}"
    directory = out_dir if out_dir is not None else src.parent
    return directory / f"{src.stem}{suffix}.png"


def notify(message: str, title: str = "croptool") -> None:
    """macOS-Mitteilung anzeigen (nützlich beim Start über Kurzbefehle)."""
    if platform.system() != "Darwin":
        return
    script = [
        "-e", "on run argv",
        "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
        "-e", "end run",
    ]
    try:
        subprocess.run(["osascript", *script, message, title],
                       check=False, capture_output=True, timeout=10)
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="croptool",
        description=(
            "Skaliert Bilder (JPG/PNG) unter Beibehaltung des Seitenverhältnisses auf "
            "eine Zielgröße, zentriert sie und füllt die Ränder transparent auf. "
            "Ausgabe immer als PNG."
        ),
    )
    parser.add_argument("inputs", nargs="+", type=Path, metavar="BILD",
                        help="eine oder mehrere JPG/PNG-Dateien")
    parser.add_argument("-s", "--size", type=parse_size,
                        default=(DEFAULT_WIDTH, DEFAULT_HEIGHT), metavar="BxH",
                        help=f"Zielgröße, Standard: {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
    parser.add_argument("-o", "--output", type=Path, metavar="DATEI",
                        help="Ausgabedatei (nur bei genau einem Eingabebild)")
    parser.add_argument("-d", "--output-dir", type=Path, metavar="ORDNER",
                        help="Zielordner (Standard: Ordner des Originals)")
    parser.add_argument("--suffix", metavar="TEXT",
                        help="Namenszusatz der Ausgabedatei (Standard: _BxH, z. B. _1244x700)")
    parser.add_argument("--notify", action="store_true",
                        help="Ergebnis als macOS-Mitteilung anzeigen (für Kurzbefehle)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    width, height = args.size

    def fail(message: str) -> int:
        print(f"Fehler: {message}", file=sys.stderr)
        if args.notify:
            notify(message, "croptool – Fehler")
        return 2

    if Image is None:
        return fail("Pillow ist nicht installiert. Bitte install.sh ausführen "
                    "(oder: python3 -m pip install Pillow).")
    if args.output and len(args.inputs) != 1:
        return fail("--output geht nur mit genau einem Eingabebild (sonst --output-dir).")
    if args.output and args.output_dir:
        return fail("--output und --output-dir bitte nicht gleichzeitig angeben.")

    out_dir = args.output_dir.expanduser() if args.output_dir else None
    done: list[Path] = []
    errors: list[str] = []

    for src in args.inputs:
        src = src.expanduser()
        if args.output:
            dst = args.output.expanduser()
            if dst.suffix.lower() != ".png":
                dst = dst.with_name(dst.name + ".png")
        else:
            dst = output_path(src, width, height, args.suffix, out_dir)
        try:
            done.append(process_file(src, dst, width, height))
            print(dst)  # stdout: nur Pfade -> im Kurzbefehl weiterverwendbar
        except CropToolError as exc:
            errors.append(str(exc))
            print(f"Fehler: {exc}", file=sys.stderr)

    if args.notify:
        if errors:
            notify(f"{len(done)} fertig, {len(errors)} fehlgeschlagen: {errors[0]}",
                   "croptool – Fehler")
        elif len(done) == 1:
            notify(f"{done[0].name} erstellt ({width}×{height})")
        else:
            notify(f"{len(done)} Bilder erstellt ({width}×{height})")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
