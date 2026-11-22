# SetIP for Windows

与 macOS 版逻辑一致的 IP 快速切换工具：公司 / 家里 / DHCP / 代理 PAC（含关闭入口）/ 设置，每次设置后回读系统实际状态并逐项显示"应用情况"。

**每按一次回车进入下一步，屏幕都会清屏，只显示当前步骤的内容**，上一步的输出不再保留；看完本步结果后按回车进入下一步。

**任意步骤输入 `m` 可一键返回主界面**（选网卡界面），未保存的编辑中途状态会丢弃并重新读盘。

> 说明：Windows 版是控制台程序，选择列表靠输入序号；`↑`/`↓` 方向键高亮选择是 macOS 原生窗口专属能力，控制台下未提供。

## 目录结构

- `setip_windows.py` —— 主程序源码
- `config.yaml` —— 内置配置模板（打包时塞进 exe，与 macOS 版格式完全通用）
- `build.bat` —— 一键打包脚本（生成单个 exe）

## 使用方式

### 方式一：直接运行（需要 Python）

```shell
pip install pyyaml
python setip_windows.py
```

### 方式二：打包成 exe 后双击运行（推荐）

在一台 Windows 电脑上（需要 Python 3.8+）双击 `build.bat`，产物为 `dist\SetIP.exe`。

- **只有一个 exe 文件**，配置已内置其中，双击即可，不需要旁边放 config.yaml
- 控制台程序退出后窗口自动关闭，无需任何配置
- 启动时弹 UAC 提权提示，点"是"（netsh 改 IP 必须管理员权限）

## 配置文件

配置模板打包在 exe 内部，首次运行时自动释放成可编辑文件：

1. 若 `SetIP.exe` 同目录存在 `config.yaml`（便携模式/旧版遗留）→ 用它，改动也写回这里
2. 否则使用 `%APPDATA%\SetIP\config.yaml`，首次运行由程序从内置配置生成

格式与 macOS 版完全一致，可直接复制。**程序内置「5、设置」菜单**，不用手动编辑文件：

```
  应用 1 公司  2 家里  3 DHCP  4 代理 PAC
  5 改公司 · 6 改家里 · 7 改 PAC · 8 配置文件 · m 主界面 · q 退出
选择:
```

表单式修改（回车保留原值，列表输入 `-` 清空），保存后立即生效，无需重启。

选网卡的那个界面同样会列出当前配置（公司 / 家里 / PAC 链接），并可直接按 `c` / `h` / `p` / `o` 修改，改完自动回到该界面。**当前有默认路由的网卡自动识别并标 ★，直接回车选中；仍可输入序号选其他网卡。**识别失败不会误选，会提示手动输入。

```
── 网卡
  [0] 以太网 Up   Intel(R) Ethernet
  [1] WLAN   Up   Intel(R) Wi-Fi  ★ 当前活动
  公司 10.91.140.5/255.255.254.0  网关 10.91.140.1  DNS 10.91.140.1
  家里 192.168.168.3/255.255.255.0  网关 192.168.168.1  DNS 114.114.114.114 8.8.8.8
  PAC WAN https://.../go.js  LAN https://.../golan.js
  c 改公司 · h 改家里 · p 改 PAC · o 配置文件 · m 主界面 · q 退出
序号 (0-1，回车=WLAN):
```

选中后只显示两行状态概览，菜单压缩为两行；应用结果只有一行，例如 `✓ 已生效  IP 地址 10.91.140.5  子网掩码 /23  网关 ...`。失败时只列不一致项。

## 输出配色

与 macOS 版同一套配色：绿色 ✓ 生效、红色 ✗ 未生效、黄色 ⚠ 警告、青色标题与菜单编号。

- 关掉颜色：`set SETIP_COLOR=never`
- 强制开启：`set SETIP_COLOR=always`
- 程序启动时会自动为控制台开启 ANSI 支持（`SetConsoleMode` + `ENABLE_VIRTUAL_TERMINAL_PROCESSING`）；Windows 8 及更早不支持，会自动回退成无颜色输出

## 与 macOS 版的实现差异

| 功能 | macOS | Windows |
|------|-------|---------|
| 设置 IP/DNS/DHCP | networksetup | `netsh interface ipv4`（管理员权限） |
| 状态回读校验 | networksetup -getinfo | PowerShell `Get-NetIPAddress` / `Get-DnsClientServerAddress`（不受系统语言影响） |
| 搜索域 | networksetup -setsearchdomains | 注册表 `SearchList`（每网卡，逗号分隔） |
| PAC 代理 | networksetup -setautoproxyurl | 注册表 `AutoConfigURL`（HKCU Internet Settings）+ WinINET 刷新 |
| 配置位置 | `SetIP.app/Contents/Resources/config.yaml` | `%APPDATA%\SetIP\config.yaml`（由 exe 内置模板释放） |
| 提权 | 一般不需要 | 启动时自动弹 UAC |
| 退出关窗 | .command + AppleScript 关窗 | 控制台 exe 退出即自动关窗，天然支持 |

## 注意

- PAC 代理是**用户级全局**设置（影响当前用户所有浏览器的 WinINET/系统代理），不区分网卡——这是 Windows 的代理模型决定的
- 部分环境下"搜索域"写入注册表后需重启网卡/电脑才完全生效
