#!/bin/bash
# Einmalige Einrichtung: legt eine lokale Python-Umgebung (.venv) im Projektordner an
# und installiert Pillow hinein. Danach arbeitet croptool komplett offline.
#
#   ./install.sh          venv anlegen + Pillow installieren
#   ./install.sh --link   zusätzlich ~/.local/bin/croptool als Befehl anlegen

set -eu

dir=$(cd "$(dirname "$0")" && pwd -P)
cd "$dir"

link=0
while [ $# -gt 0 ]; do
    case $1 in
        --link) link=1 ;;
        -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
    esac
    shift
done

# Python 3.8+ suchen (Homebrew bevorzugt, dann System-Python der Command Line Tools)
python=""
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 /usr/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
        python=$(command -v "$candidate")
        break
    fi
done
if [ -z "$python" ]; then
    echo "Kein Python 3.8+ gefunden." >&2
    echo "Installieren z. B. mit:  xcode-select --install   oder   brew install python" >&2
    exit 1
fi
echo "Verwende Python: $python ($("$python" -c 'import platform; print(platform.python_version())'))"

if [ ! -x .venv/bin/python3 ]; then
    echo "Lege virtuelle Umgebung an: $dir/.venv"
    "$python" -m venv .venv
fi

echo "Installiere Pillow (einmalig, benötigt Internet) ..."
.venv/bin/python3 -m pip install --quiet --upgrade pip
.venv/bin/python3 -m pip install --quiet -r requirements.txt

chmod +x croptool croptool.py

# Selbsttest
.venv/bin/python3 -c 'import PIL; print("Pillow", PIL.__version__, "ist bereit.")'

if [ "$link" -eq 1 ]; then
    mkdir -p "$HOME/.local/bin"
    ln -sf "$dir/croptool" "$HOME/.local/bin/croptool"
    echo "Befehl angelegt: $HOME/.local/bin/croptool"
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) echo "Hinweis: ~/.local/bin ist nicht im PATH. In ~/.zshrc ergänzen:"
           echo "    export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
    esac
fi

cat <<EOF

Fertig! Aufruf im Terminal:
    "$dir/croptool" bild.jpg

Für den macOS-Kurzbefehl („Shell-Skript ausführen“, Eingabe „als Argumente“):
    "$dir/croptool" --notify "\$@"
EOF
