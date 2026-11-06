# SetIP for Windows

与 macOS 版逻辑一致的 IP 快速切换工具：公司 / 家里 / DHCP / 代理 PAC（含关闭入口），每次设置后回读系统实际状态并逐项显示"应用情况"。

## 目录结构

- `setip_windows.py` —— 主程序源码
- `config.yaml` —— 配置文件（与 macOS 版格式完全通用）
- `build.bat` —— 一键打包脚本（生成单个 exe）

## 使用方式

### 方式一：直接运行（需要 Python）

```shell
pip install pyyaml
python setip_windows.py
```

### 方式二：打包成 exe 后双击运行（推荐）

在一台 Windows 电脑上（需要 Python 3.8+）双击 `build.bat`，产物为 `dist\SetIP.exe`。

- 把 `SetIP.exe` 和 `config.yaml` 放同一个文件夹，双击 `SetIP.exe` 即可
- 控制台程序退出后窗口自动关闭，无需任何配置
- 启动时弹 UAC 提权提示，点"是"（netsh 改 IP 必须管理员权限）

## 配置文件

查找顺序：`SetIP.exe` 同目录 → `~/.setip/config.yaml`（不存在则自动生成模板）。格式与 macOS 版完全一致，可直接复制。

## 与 macOS 版的实现差异

| 功能 | macOS | Windows |
|------|-------|---------|
| 设置 IP/DNS/DHCP | networksetup | `netsh interface ipv4`（管理员权限） |
| 状态回读校验 | networksetup -getinfo | PowerShell `Get-NetIPAddress` / `Get-DnsClientServerAddress`（不受系统语言影响） |
| 搜索域 | networksetup -setsearchdomains | 注册表 `SearchList`（每网卡，逗号分隔） |
| PAC 代理 | networksetup -setautoproxyurl | 注册表 `AutoConfigURL`（HKCU Internet Settings）+ WinINET 刷新 |
| 提权 | 一般不需要 | 启动时自动弹 UAC |
| 退出关窗 | .command + AppleScript 关窗 | 控制台 exe 退出即自动关窗，天然支持 |

## 注意

- PAC 代理是**用户级全局**设置（影响当前用户所有浏览器的 WinINET/系统代理），不区分网卡——这是 Windows 的代理模型决定的
- 部分环境下"搜索域"写入注册表后需重启网卡/电脑才完全生效
