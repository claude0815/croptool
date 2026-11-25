import io
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import croptool  # noqa: E402


def alpha_at(img, x, y):
    return img.getpixel((x, y))[3]


class FitSizeTest(unittest.TestCase):
    def test_portrait_scales_to_height(self):
        self.assertEqual(croptool.fit_size(1000, 2000, 1244, 700), (350, 700))

    def test_wide_scales_to_width(self):
        self.assertEqual(croptool.fit_size(4000, 1000, 1244, 700), (1244, 311))

    def test_exact_ratio(self):
        self.assertEqual(croptool.fit_size(2488, 1400, 1244, 700), (1244, 700))

    def test_upscale_small(self):
        self.assertEqual(croptool.fit_size(100, 100, 1244, 700), (700, 700))

    def test_never_zero(self):
        self.assertEqual(croptool.fit_size(10000, 1, 1244, 700), (1244, 1))


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, name, img, **save):
        path = self.tmp / name
        img.save(path, **save)
        return path

    def run_main(self, *args):
        return croptool.main([str(a) for a in args])

    def test_jpg_portrait_gets_transparent_sides(self):
        src = self.make("foto.jpg", Image.new("RGB", (600, 900), (200, 30, 30)))
        self.assertEqual(self.run_main(src), 0)
        out = Image.open(self.tmp / "foto_1244x700.png")
        self.assertEqual(out.size, (1244, 700))
        self.assertEqual(out.mode, "RGBA")
        # Bildbreite: 600 * 700/900 = 466.67 -> 467, Rand links (1244-467)//2 = 388
        self.assertEqual(alpha_at(out, 0, 350), 0)
        self.assertEqual(alpha_at(out, 387, 350), 0)
        self.assertEqual(alpha_at(out, 389, 350), 255)
        self.assertEqual(alpha_at(out, 622, 0), 255)
        self.assertEqual(alpha_at(out, 622, 699), 255)
        self.assertEqual(alpha_at(out, 1243, 350), 0)
        r, g, b, _ = out.getpixel((622, 350))
        self.assertTrue(r > 180 and g < 60 and b < 60)

    def test_wide_image_gets_top_bottom_padding(self):
        src = self.make("pano.png", Image.new("RGB", (4000, 1000), "blue"))
        self.run_main(src)
        out = Image.open(self.tmp / "pano_1244x700.png")
        self.assertEqual(out.size, (1244, 700))
        self.assertEqual(alpha_at(out, 622, 0), 0)
        self.assertEqual(alpha_at(out, 622, 350), 255)
        self.assertEqual(alpha_at(out, 0, 350), 255)

    def test_small_image_is_upscaled(self):
        src = self.make("klein.png", Image.new("RGB", (70, 70), "green"))
        self.run_main(src)
        out = Image.open(self.tmp / "klein_1244x700.png")
        self.assertEqual(out.getbbox(), (272, 0, 972, 700))

    def test_existing_transparency_is_kept(self):
        img = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
        img.paste((255, 255, 0, 255), (200, 200, 500, 500))
        src = self.make("logo.png", img)
        self.run_main(src)
        out = Image.open(self.tmp / "logo_1244x700.png")
        self.assertEqual(alpha_at(out, 272 + 50, 50), 0)
        self.assertEqual(alpha_at(out, 622, 350), 255)

    def test_palette_png_with_transparency(self):
        img = Image.new("P", (100, 200), 0)
        img.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
        img.paste(1, (0, 0, 100, 100))
        src = self.make("pal.png", img, transparency=0)
        self.run_main(src)
        out = Image.open(self.tmp / "pal_1244x700.png")
        self.assertEqual(out.size, (1244, 700))
        self.assertEqual(alpha_at(out, 622, 100), 255)  # rote obere Hälfte
        self.assertEqual(alpha_at(out, 622, 600), 0)    # transparente untere Hälfte

    def test_grayscale_and_16bit(self):
        self.run_main(self.make("gray.jpg", Image.new("L", (300, 600), 128)))
        out = Image.open(self.tmp / "gray_1244x700.png")
        self.assertEqual(out.getpixel((622, 350))[:3], (128, 128, 128))

        img16 = Image.frombytes("I;16", (300, 600), (40000).to_bytes(2, "little") * 300 * 600)
        self.run_main(self.make("deep.png", img16))
        out = Image.open(self.tmp / "deep_1244x700.png")
        self.assertAlmostEqual(out.getpixel((622, 350))[0], 40000 // 256, delta=1)

    def test_cmyk_jpg(self):
        src = self.make("print.jpg", Image.new("CMYK", (500, 1000), (0, 255, 255, 0)))
        self.assertEqual(self.run_main(src), 0)
        out = Image.open(self.tmp / "print_1244x700.png")
        self.assertEqual(out.size, (1244, 700))
        r, g, b, a = out.getpixel((622, 350))
        self.assertEqual(a, 255)
        self.assertTrue(r > 200 and g < 60 and b < 60)

    def test_exif_orientation_is_applied(self):
        # Gespeichert quer (900x600), EXIF sagt "um 90° drehen" -> eigentlich hochkant.
        img = Image.new("RGB", (900, 600), "white")
        exif = Image.Exif()
        exif[0x0112] = 6
        src = self.make("iphone.jpg", img, exif=exif.tobytes())
        self.run_main(src)
        out = Image.open(self.tmp / "iphone_1244x700.png")
        # Hochkant 600x900 -> 467x700, also transparente Seiten
        self.assertEqual(alpha_at(out, 10, 350), 0)
        self.assertEqual(out.getbbox(), (388, 0, 855, 700))

    def test_icc_profile_is_preserved(self):
        from PIL import ImageCms
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        src = self.make("p3.jpg", Image.new("RGB", (800, 800), "red"), icc_profile=icc)
        self.run_main(src)
        out = Image.open(self.tmp / "p3_1244x700.png")
        self.assertEqual(out.info.get("icc_profile"), icc)

    def test_custom_size_suffix_and_dirs(self):
        src = self.make("a.jpg", Image.new("RGB", (100, 100), "red"))
        self.assertEqual(self.run_main(src, "-s", "1920x1080", "-d", self.tmp / "out"), 0)
        self.assertEqual(Image.open(self.tmp / "out" / "a_1920x1080.png").size, (1920, 1080))

        self.assertEqual(self.run_main(src, "--suffix=-web"), 0)
        self.assertTrue((self.tmp / "a-web.png").exists())

        self.assertEqual(self.run_main(src, "-o", self.tmp / "x" / "ziel"), 0)
        self.assertEqual(Image.open(self.tmp / "x" / "ziel.png").size, (1244, 700))

    def test_multiple_files_and_errors(self):
        a = self.make("a.jpg", Image.new("RGB", (100, 100)))
        b = self.make("b.png", Image.new("RGB", (100, 50)))
        broken = self.tmp / "kaputt.jpg"
        broken.write_bytes(b"kein bild")
        self.assertEqual(self.run_main(a, b, broken, self.tmp / "fehlt.png"), 1)
        self.assertTrue((self.tmp / "a_1244x700.png").exists())
        self.assertTrue((self.tmp / "b_1244x700.png").exists())
        self.assertFalse((self.tmp / "kaputt_1244x700.png").exists())
        self.assertEqual([p.name for p in self.tmp.glob(".croptool-*")], [])

    def test_refuses_to_overwrite_original(self):
        src = self.make("bild.png", Image.new("RGB", (100, 100), "red"))
        before = src.read_bytes()
        self.assertEqual(self.run_main(src, "--suffix", ""), 1)
        self.assertEqual(src.read_bytes(), before)

    def test_output_with_multiple_inputs_rejected(self):
        a = self.make("a.jpg", Image.new("RGB", (10, 10)))
        self.assertEqual(self.run_main(a, a, "-o", self.tmp / "x.png"), 2)

    def test_invalid_size(self):
        with self.assertRaises(SystemExit):
            croptool.main(["x.jpg", "-s", "1244"])
        self.assertEqual(croptool.parse_size("1244 × 700"), (1244, 700))

    def test_launcher_script_prints_output_paths(self):
        src = self.make("cli.jpg", Image.new("RGB", (300, 300)))
        res = subprocess.run([str(ROOT / "croptool"), str(src)],
                             capture_output=True, text=True, check=True)
        self.assertEqual(res.stdout.strip(), str(self.tmp / "cli_1244x700.png"))


class InputHandlingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name) / "Ordner mit Leerzeichen"
        self.tmp.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, name):
        path = self.tmp / name
        Image.new("RGB", (300, 600), "red").save(path)
        return path

    def run_cli(self, *args, stdin=b""):
        return subprocess.run([str(ROOT / "croptool"), *map(str, args)], input=stdin,
                              capture_output=True, cwd=self.tmp)

    def test_quoted_name_with_spaces(self):
        self.make("Mein Foto.jpg")
        res = self.run_cli("Mein Foto.jpg")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.tmp / "Mein Foto_1244x700.png").exists())

    def test_unquoted_name_with_spaces_is_rejoined(self):
        self.make("Mein schönes Foto.jpg")
        self.make("b.png")
        # wie: croptool Mein schönes Foto.jpg b.png  (ohne Anführungszeichen)
        res = self.run_cli("Mein", "schönes", "Foto.jpg", "b.png")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.tmp / "Mein schönes Foto_1244x700.png").exists())
        self.assertTrue((self.tmp / "b_1244x700.png").exists())

    def test_macos_screenshot_narrow_space(self):
        real = "Screenshot 2026-11-25 at 10.15.30 AM.png"
        self.make(real)
        res = self.run_cli("Screenshot 2026-11-25 at 10.15.30 AM.png")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.tmp / real.replace(".png", "_1244x700.png")).exists())

    def test_decomposed_umlauts(self):
        nfd = unicodedata.normalize("NFD", "Bärchen.jpg")
        self.make(nfd)
        res = self.run_cli(unicodedata.normalize("NFC", "Bärchen.jpg"))
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_missing_file_shows_quote_hint(self):
        res = self.run_cli("gibt", "es", "nicht.jpg")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Anführungszeichen", res.stderr.decode())

    def test_no_input_gives_german_hint(self):
        res = self.run_cli()
        self.assertEqual(res.returncode, 2)
        err = res.stderr.decode()
        self.assertIn("Keine Bilder übergeben", err)
        self.assertIn("als Argumente", err)
        self.assertNotIn("required", err)

    def test_paths_via_stdin(self):
        self.make("über stdin.jpg")
        self.make("url name.png")
        url = "file://" + str(self.tmp / "url name.png").replace(" ", "%20")
        res = self.run_cli(stdin=f"{self.tmp / 'über stdin.jpg'}\n{url}\n".encode())
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.tmp / "über stdin_1244x700.png").exists())
        self.assertTrue((self.tmp / "url name_1244x700.png").exists())

    def test_image_bytes_via_stdin_gives_hint(self):
        buf = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buf, "JPEG")
        res = self.run_cli(stdin=buf.getvalue())
        self.assertEqual(res.returncode, 2)
        self.assertIn("als Argumente", res.stderr.decode())

    def test_output_option_with_unquoted_input(self):
        self.make("Mein Foto.jpg")
        res = self.run_cli("-o", "ziel.png", "Mein", "Foto.jpg")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.tmp / "ziel.png").exists())


if __name__ == "__main__":
    unittest.main()
