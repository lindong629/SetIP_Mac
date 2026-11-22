#!/bin/bash
# 组装 SetIP.app：原生宿主窗口（无 Terminal）+ PyInstaller 主程序
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/SetIP.app"
BIN="$ROOT/dist/SetIP"

if [ ! -x "$BIN" ]; then
  echo "找不到 $BIN，请先运行：pyinstaller --onefile --name SetIP --icon icon.icns --clean -y main.py"
  exit 1
fi

# 配置：重新打包时保留 App 内已有的 config.yaml（用户可能通过面板 o 改过），
# 没有才用项目根目录模板。先备份再重建，避免被 rm -rf 删掉。
OLD_CONFIG=""
if [ -f "$APP/Contents/Resources/config.yaml" ]; then
  OLD_CONFIG="$(mktemp)"
  cp "$APP/Contents/Resources/config.yaml" "$OLD_CONFIG"
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$BIN" "$APP/Contents/MacOS/SetIP-bin"
cp "$ROOT/mac/Info.plist" "$APP/Contents/Info.plist"
cp "$ROOT/icon.icns" "$APP/Contents/Resources/icon.icns"
if [ -n "$OLD_CONFIG" ] && [ -f "$OLD_CONFIG" ]; then
  cp "$OLD_CONFIG" "$APP/Contents/Resources/config.yaml"
  rm -f "$OLD_CONFIG"
  echo "沿用 App 内已有配置（未覆盖用户修改）"
else
  cp "$ROOT/config.yaml" "$APP/Contents/Resources/config.yaml"
  echo "使用项目根目录配置"
fi

# 版本号从 Info.plist 读取，注入到宿主（单点真值）
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$ROOT/mac/Info.plist")"

# 宿主本身用系统 clang 编译，支持 Intel / Apple Silicon
clang -fobjc-arc -framework Cocoa -framework QuartzCore -O2 \
  -arch x86_64 -arch arm64 \
  -mmacosx-version-min=10.13 \
  -DSETIP_VERSION='"'"$VERSION"'"' \
  "$ROOT/mac/SetIPHost.m" -o "$APP/Contents/MacOS/SetIP"

chmod +x "$APP/Contents/MacOS/SetIP" "$APP/Contents/MacOS/SetIP-bin"
codesign --force --deep --sign - "$APP"
echo "已生成 $APP"
