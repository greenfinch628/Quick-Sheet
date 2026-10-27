#!/bin/sh
# Run after copying the app into ~/Applications/Quick-Sheet.
set -eu
app_dir="$HOME/Applications/Quick-Sheet"
icon_dir="$HOME/Pictures/icons"
mkdir -p "$icon_dir" "$HOME/.local/share/applications"
chmod +x "$app_dir/launch.sh"
cp "$app_dir/assets/Quick-Sheet.png" "$icon_dir/Quick-Sheet.png"
cp "$app_dir/assets/Quick-Sheet.svg" "$icon_dir/Quick-Sheet.svg"
cp "$app_dir/Quick-Sheet.desktop" "$HOME/.local/share/applications/Quick-Sheet.desktop"
desktop-file-validate "$HOME/.local/share/applications/Quick-Sheet.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications"
fi
printf 'Installed Quick-Sheet in %s\n' "$app_dir"
