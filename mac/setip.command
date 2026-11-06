#!/bin/bash
# 双击 SetIP.app 时由启动器调用；在终端中运行主程序
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/SetIP-bin"
status=$?
if [ $status -eq 0 ]; then
  # 正常退出（输入 q）：主动关闭本窗口，不依赖终端"shell 退出时"的偏好设置
  # nohup + 后台执行，避免 osascript 随 shell 退出被挂断
  nohup osascript -e 'tell application "Terminal" to close (every window whose name contains "setip.command")' >/dev/null 2>&1 &
fi
exit $status
