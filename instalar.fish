#!/usr/bin/env fish
# SPDX-License-Identifier: AGPL-3.0-only
# Instala el programa solo para el usuario actual.
set -l origin (dirname (realpath (status filename)))
if not command -q pacman
    echo 'Instalador pensado para CachyOS/Arch' >&2
    exit 1
end
if not /usr/bin/python -c 'import PySide6' >/dev/null 2>&1
    echo 'Instala: sudo pacman -S pyside6' >&2
    exit 1
end
if not command -q nvidia-smi; or not command -q pkexec
    echo 'Se requieren nvidia-smi y pkexec' >&2
    exit 1
end
set -l target "$HOME/.local/share/gpu-profiles"
mkdir -p "$target/icons" "$HOME/.local/share/applications"
or exit 1
cp "$origin/gpu_profiles.py" "$target/gpu_profiles.py"
or exit 1
cp "$origin/icons/nvidia-power-control.svg" "$target/icons/nvidia-power-control.svg"
or exit 1
printf '[Desktop Entry]\nType=Application\nName=NVIDIA Power Control\nComment=Perfiles de potencia NVIDIA\nExec=/usr/bin/python %s/gpu_profiles.py\nIcon=%s/icons/nvidia-power-control.svg\nTerminal=false\nCategories=Settings;System;\nStartupNotify=true\n' "$target" "$target" > "$HOME/.local/share/applications/local.gpu-profiles.desktop"
if command -q kbuildsycoca6
    kbuildsycoca6 >/dev/null 2>&1
end
echo 'NVIDIA Power Control instalado para el usuario actual.'
