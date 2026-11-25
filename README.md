# croptool

Bringt JPG- und PNG-Bilder auf eine feste Größe (Standard **1244 × 700**), ohne sie zu verzerren:

1. Das Bild wird so skaliert, dass es komplett in die Zielgröße passt (Seitenverhältnis bleibt erhalten; kleine Bilder werden vergrößert).
2. Es wird mittig platziert.
3. Die freien Ränder werden **transparent** aufgefüllt, bei Hochkant-Bildern links und rechts, bei sehr breiten Bildern oben und unten.

Die Ausgabe ist immer PNG (JPG kann keine Transparenz), z. B. `foto.jpg` → `foto_1244x700.png` im selben Ordner. Das Original bleibt unverändert.

Das Tool arbeitet komplett offline. Nur bei der Einrichtung wird einmal Pillow aus dem Internet geladen.

## Einrichtung (macOS, einmalig)

Den Ordner an einen festen Ort legen, z. B. `~/Tools/croptool`. Das geht per `git clone` oder als ZIP von GitHub. Am besten nicht in „Schreibtisch“ oder „Dokumente“ ablegen, sonst fragt macOS beim Kurzbefehl nach Ordnerzugriff. Danach im Terminal:

```bash
cd ~/Tools/croptool
```

```bash
bash install.sh
```

Das Skript legt in `croptool/.venv` eine eigene Python-Umgebung an und installiert Pillow dort hinein. Das restliche System wird nicht verändert. Am Ende zeigt es die genaue Zeile für den Kurzbefehl an.

Ist kein Python vorhanden, kommt es mit den Apple Command Line Tools (`xcode-select --install`) oder über Homebrew (`brew install python`).

Wer `croptool` als Terminalbefehl nutzen möchte, ruft das Skript mit `--link` auf. Dann wird `~/.local/bin/croptool` angelegt:

```bash
bash install.sh --link
```

## Kurzbefehl (Rechtsklick im Finder und/oder Tastenkürzel)

1. App **Kurzbefehle** öffnen und **Kurzbefehle → Einstellungen… → Erweitert** wählen. Dort **„Ausführen von Skripts erlauben“** einschalten (engl. *Allow Running Scripts*).
2. Mit **+** einen neuen Kurzbefehl anlegen, z. B. mit dem Namen „Auf 1244×700 bringen“.
3. Rechts unter **Details des Kurzbefehls (ⓘ)** diese Optionen setzen:
   - **Als Schnellaktion verwenden** anhaken und dabei **Finder** wählen.
   - Optional über **Tastaturkurzbefehl hinzufügen** ein Kürzel festlegen.
4. Oben steht jetzt „Eingabe von *Schnellaktionen* empfangen“. Den Eingabetyp auf **Bilder** und **Dateien** einschränken.
5. Die Aktion **„Shell-Skript ausführen“** (*Run Shell Script*) hinzufügen und so einstellen:
   - Shell: `zsh`
   - Eingabe: **Kurzbefehleingabe**
   - Eingabe übergeben: **als Argumente**
   - Skript (Pfad anpassen bzw. die Zeile aus der Ausgabe von `install.sh` übernehmen):

     ```bash
     "$HOME/Tools/croptool/croptool" --notify "$@"
     ```

Benutzung: Ein oder mehrere Bilder im Finder markieren und per Rechtsklick **Schnellaktionen → Auf 1244×700 bringen** wählen (oder das Tastenkürzel drücken). Die PNGs landen neben den Originalen, eine Mitteilung meldet das Ergebnis.

Varianten:

- Andere Größe: Im Skript `--size 1920x1080` ergänzen. Man kann auch mehrere Kurzbefehle für verschiedene Größen anlegen.
- Festen Zielordner nutzen: `--output-dir "$HOME/Desktop/Fertig"` ergänzen. Das ist sinnvoll, wenn Bilder über das Teilen-Menü (z. B. aus „Fotos“) kommen, weil diese nur als temporäre Dateien vorliegen.
- Das Skript gibt die erzeugten Pfade zeilenweise aus. Weitere Aktionen im Kurzbefehl können sie verwenden, z. B. „Im Finder zeigen“.
- Auf älteren macOS-Versionen funktioniert dasselbe mit **Automator**: eine Schnellaktion mit „Shell-Skript ausführen“ anlegen und die Eingabe „als Argumente“ übergeben.

## Kommandozeile

```text
croptool BILD [BILD ...] [Optionen]

  -s, --size BxH        Zielgröße (Standard: 1244x700)
  -o, --output DATEI    Ausgabedatei (nur bei genau einem Bild)
  -d, --output-dir DIR  Zielordner (Standard: Ordner des Originals)
  --suffix TEXT         Namenszusatz (Standard: _BxH), z. B. --suffix=-web
  --notify              Ergebnis als macOS-Mitteilung anzeigen
```

Beispiele:

```bash
./croptool foto.jpg
```

```bash
./croptool *.jpg --size 1920x1080 --output-dir ~/Desktop/fertig
```

```bash
./croptool screenshot.png -o ~/Desktop/titelbild.png
```

`croptool.py` läuft auch direkt mit jedem Python 3.8+, in dem Pillow installiert ist (macOS, Linux, Windows).

## Details

- Die EXIF-Ausrichtung wird beachtet, damit Hochkant-Fotos vom Smartphone richtig herum erscheinen.
- Farbprofile (z. B. Display P3 vom iPhone) werden übernommen. CMYK-JPGs werden nach sRGB umgerechnet.
- Vorhandene Transparenz in PNGs bleibt erhalten. Für die Skalierung wird Lanczos verwendet.
- Eine bereits vorhandene Ausgabedatei wird überschrieben, das Original aber nie.
- HEIC-Fotos werden nicht unterstützt. Man kann sie vorher im Finder per Schnellaktion „Bild konvertieren“ in JPG/PNG umwandeln.

## Tests

```bash
.venv/bin/python3 -m unittest discover -s tests -v
```
