#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SetIP for Windows - IP 快速切换工具
# 菜单：1、公司  2、家里  3、DHCP  4、代理 PAC  5、设置
# 配置文件：内置在 exe 里，首次运行自动释放到 %APPDATA%\SetIP\config.yaml
# 需要 Python 3.8+ 与 PyYAML；打包为 exe 后双击运行，退出后窗口自动关闭。

import ctypes
import json
import os
import subprocess
import sys
import time
import unicodedata

try:
    import winreg
except ImportError:
    print("本程序仅支持 Windows")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("缺少依赖 PyYAML，请先执行: pip install pyyaml")
    sys.exit(1)

APP_NAME = "IP 管理器 SetIP (Windows)"
INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
RULE = "─" * 54


# ------------------------------------------------------------ 终端配色排版 --

class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GREY = "\033[90m"


def _enable_windows_ansi():
    """Windows 10+ 控制台默认不解析 ANSI，需要显式开启 VT 处理"""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)            # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _detect_color():
    """SETIP_COLOR=always / never 可强制开关；默认跟随终端能力"""
    env = os.environ.get("SETIP_COLOR", "").strip().lower()
    if env in ("always", "1", "true", "yes", "on"):
        return True
    if env in ("never", "0", "false", "no", "off") or "NO_COLOR" in os.environ:
        return False
    if not sys.stdout.isatty():
        return False
    return _enable_windows_ansi()


USE_COLOR = _detect_color()


class GoHome(Exception):
    """用户在任意步骤请求返回主界面（输入 m / home）。"""


class QuitApp(Exception):
    """用户在任意步骤请求退出（q）。"""


HOME_TOKENS = ("m", "home", "主界面")
QUIT_TOKENS = ("q", "quit", "exit")


def is_home(raw):
    return (raw or "").strip().lower() in HOME_TOKENS


def is_quit(raw):
    return (raw or "").strip().lower() in QUIT_TOKENS


def read_line(prompt=""):
    """读取一行；统一识别「返回主界面」与「退出」，任意步骤都生效。"""
    raw = input(prompt)
    if is_home(raw):
        raise GoHome()
    if is_quit(raw):
        raise QuitApp()
    return raw


def c(text, *styles):
    """给文本加颜色/样式；未启用颜色时原样返回"""
    if not USE_COLOR or not styles:
        return str(text)
    return "".join(styles) + str(text) + Style.RESET


def dlen(text):
    """按终端显示宽度计长度（中文按 2 计）"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in str(text))


def pad(text, width):
    text = str(text)
    return text + " " * max(0, width - dlen(text))


def row(label, value, label_width=12, value_style=None, label_style=Style.GREY):
    shown = c(value, value_style) if value_style else str(value)
    print("  %s %s" % (c(pad(label, label_width), label_style), shown))


def info(msg):
    print("  " + msg)


def step(msg):
    print(c("  ▸ " + msg + " ...", Style.BLUE))


def hint(msg):
    print(c("  " + msg, Style.DIM))


def warn(msg):
    print(c("  ⚠ " + msg, Style.YELLOW))


def error(msg):
    print(c("  ✗ " + msg, Style.RED))


def success(msg):
    print(c("  ✓ " + msg, Style.GREEN))


def section(title, style=Style.CYAN):
    print(c(RULE, Style.GREY))
    print(c(" " + title, Style.BOLD, style))


def print_caption(title, note=""):
    print(c("  " + title, Style.BOLD, Style.CYAN)
          + (c("   " + note, Style.DIM) if note else ""))


def menu_item(key, label, key_style=Style.CYAN):
    print("  %s %s" % (c(pad(key, 2), Style.BOLD, key_style), label))


def banner(subtitle=""):
    print(c("  " + APP_NAME + (("  ·  " + subtitle) if subtitle else ""),
            Style.BOLD, Style.CYAN))


def clear():
    """清屏并归位光标：进入下一步时抹掉上一步的输出。"""
    if not (USE_COLOR or sys.stdout.isatty()):
        return
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def pause():
    """停驻一步，让用户看完本步结果后再按回车进入下一步。"""
    read_line(c("\n  按回车继续 ...", Style.DIM))

CONFIG_TEMPLATE = """\
# ==========================================================
# SetIP 配置文件（YAML 格式，与 macOS 版通用）
# 直接用记事本修改保存即可，下次启动程序生效。
# dns / search_domains 支持多个值，一行一个（用 "- " 开头）；
# search_domains 不需要就留空 []。
# ==========================================================

company:                # 公司
  ip: 10.91.140.5
  netmask: 255.255.254.0
  gateway: 10.91.140.1
  dns:
    - 10.91.140.1
  search_domains: []    # 示例: [buyabs.corp]

home:                   # 家里
  ip: 192.168.168.3
  netmask: 255.255.255.0
  gateway: 192.168.168.1
  dns:
    - 114.114.114.114
    - 8.8.8.8
  search_domains: []

proxy:                  # PAC 自动代理链接（WAN / LAN 地址不同，按需修改）
  wan: https://www.wlgo.cc/st/go.js
  lan: https://www.wlgo.cc/st/golan.js
"""

# ---------------------------------------------------------------- 配置文件 --

def is_frozen():
    return getattr(sys, "frozen", False)


def exe_dir():
    """exe（或源码）所在目录"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def user_config_dir():
    """用户可写配置目录：%APPDATA%\\SetIP"""
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "SetIP")


def bundled_config():
    """打包时塞进 exe 的 config.yaml（PyInstaller 解压到临时目录 _MEIPASS）"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        for path in (os.path.join(base, "config.yaml"),
                     os.path.join(base, "_internal", "config.yaml")):
            if os.path.isfile(path):
                return path
    # 兼容 onedir 打包/开发环境
    for path in (os.path.join(exe_dir(), "config.yaml"),
                 os.path.join(exe_dir(), "_internal", "config.yaml")):
        if os.path.isfile(path):
            return path
    return None


def config_candidates():
    """配置文件候选路径（按优先级）：
    1. exe 同级 config.yaml —— 便携模式/旧版遗留，存在就用它并写回它
    2. %APPDATA%\\SetIP\\config.yaml —— 默认位置，首次运行由程序自动释放
    """
    return [os.path.join(exe_dir(), "config.yaml"),
            os.path.join(user_config_dir(), "config.yaml")]


def get_config_path():
    for path in config_candidates():
        if os.path.isfile(path):
            return path

    # 首次运行：把 exe 内置的配置释放成可编辑的真实文件
    target = config_candidates()[-1]
    source = bundled_config()
    try:
        text = open(source, "r", encoding="utf-8").read() if source else CONFIG_TEMPLATE
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(text)
        success("首次运行，已从程序内置配置初始化: %s" % target)
        return target
    except OSError:
        pass

    target = config_candidates()[0]
    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE)
        success("未找到配置文件，已自动生成模板: %s" % target)
        return target
    except OSError:
        error("无法创建配置文件")
        sys.exit(1)


def save_config(path, profiles):
    """写回配置文件（带注释头）。成功返回实际写入路径，失败返回 None。"""
    data = {
        "company": dict(profiles["company"]),
        "home": dict(profiles["home"]),
        "proxy": dict(profiles["proxy"]),
    }
    header = ("# ==========================================================\n"
              "# SetIP 配置文件（YAML 格式，与 macOS 版通用）\n"
              "# 由程序「设置」菜单生成，也可以直接用记事本修改。\n"
              "# ==========================================================\n\n")
    text = header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                                  default_flow_style=False)

    targets = [path] + [p for p in config_candidates() if p != path]
    for target in targets:
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
            return target
        except OSError:
            continue
    return None


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        error("配置文件 YAML 格式有误，请检查: %s\n%s" % (path, e))
        sys.exit(1)

    profiles = {}
    for key in ("company", "home"):
        item = data.get(key)
        if not isinstance(item, dict):
            error('配置文件缺少 "%s" 配置段，请检查 %s' % (key, path))
            sys.exit(1)
        missing = [k for k in ("ip", "netmask", "gateway", "dns") if not item.get(k)]
        if key == "company" and missing:
            error('"%s" 缺少字段: %s，请检查配置文件' % (key, ", ".join(missing)))
            sys.exit(1)
        profiles[key] = {
            "ip": str(item.get("ip", "")),
            "netmask": str(item.get("netmask", "")),
            "gateway": str(item.get("gateway", "")),
            "dns": [str(d) for d in item.get("dns", []) if str(d).strip()],
            "search_domains": [str(d) for d in (item.get("search_domains") or []) if str(d).strip()],
        }

    proxy = data.get("proxy") or {}
    profiles["proxy"] = {
        "wan": str(proxy.get("wan", "")).strip(),
        "lan": str(proxy.get("lan", "")).strip(),
    }
    return profiles


# -------------------------------------------------------------- 管理员权限 --

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_as_admin():
    """通过 UAC 重新以管理员身份启动自身"""
    params = " ".join('"%s"' % a for a in sys.argv)
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1)  # SW_SHOWNORMAL
    if ret <= 32:
        error("需要管理员权限才能修改网络设置，本次退出。")
        input("按回车键退出...")
        sys.exit(1)


# ------------------------------------------------------------ 命令封装 --

def run_cmd(args):
    """执行命令并返回 stdout（netsh 输出按系统默认编码解码）"""
    result = subprocess.run(args, capture_output=True)
    return result.stdout.decode("mbcs", errors="replace").strip()


def ps(script):
    """执行 PowerShell 脚本，返回 UTF-8 解码的 stdout（数据与界面语言无关）"""
    full = '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; ' + script
    result = subprocess.run(["powershell", "-NoProfile", "-Command", full],
                            capture_output=True)
    return result.stdout.decode("utf-8", errors="replace").strip()


def ps_json(script):
    """执行 PowerShell 并解析 JSON 输出，统一返回 list"""
    out = ps(script + " | ConvertTo-Json -Depth 3 -Compress")
    if not out:
        return []
    try:
        data = json.loads(out)
    except ValueError:
        return []
    if isinstance(data, dict):
        return [data]
    return data if isinstance(data, list) else []


def list_adapters():
    """网卡列表：[(名称, 状态, 描述), ...]"""
    items = ps_json("Get-NetAdapter | Sort-Object Status -Descending | "
                    "Select-Object Name, Status, InterfaceDescription")
    result = []
    for it in items:
        name = str(it.get("Name", "")).strip()
        status = str(it.get("Status", "")).strip()
        desc = str(it.get("InterfaceDescription", "")).strip()
        if name:
            result.append((name, status, desc))
    return result


def active_adapter():
    """识别当前承载默认路由的网卡名；识别失败返回 None。"""
    idx = ps("Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
             "Sort-Object RouteMetric | Select-Object -First 1 -ExpandProperty InterfaceIndex")
    idx = idx.strip().splitlines()[0].strip() if idx.strip() else ""
    if idx.isdigit() and int(idx) > 0:
        name = ps("Get-NetAdapter -InterfaceIndex %s -ErrorAction SilentlyContinue | "
                  "Select-Object -First 1 -ExpandProperty Name" % idx)
        if name:
            return name.strip().splitlines()[0].strip()
    # 兜底：找第一个已连接且拿到有效 IPv4 的网卡
    for name, status, _desc in list_adapters():
        if status.lower() == "up":
            ip, _prefix, _gw, _origin = get_ipv4_info(name)
            if ip and not ip.startswith("169.254"):
                return name
    return None


def mask_to_prefix(mask):
    """子网掩码转前缀长度，如 255.255.254.0 -> 23"""
    try:
        parts = [int(o) for o in mask.split(".")]
        if len(parts) != 4 or any(o < 0 or o > 255 for o in parts):
            return -1
        return sum(bin(o).count("1") for o in parts)
    except ValueError:
        return -1


# ---------------------------------------------------------------- 状态回读 --

def get_ipv4_info(alias):
    """返回 (ip, prefix_len, gateway, origin)，未取到时对应项为空"""
    ips = ps_json("Get-NetIPAddress -InterfaceAlias '%s' -AddressFamily IPv4 "
                  "-ErrorAction SilentlyContinue | "
                  "Select-Object IPAddress, PrefixLength, PrefixOrigin" % alias)
    gw_items = ps_json("Get-NetRoute -InterfaceAlias '%s' -DestinationPrefix '0.0.0.0/0' "
                       "-ErrorAction SilentlyContinue | Select-Object NextHop" % alias)
    gateway = gw_items[0].get("NextHop", "") if gw_items else ""
    if gateway == "0.0.0.0":
        gateway = "On-link"
    if not ips:
        return ("", -1, gateway, "")
    it = ips[0]
    return (str(it.get("IPAddress", "")),
            int(it.get("PrefixLength", -1)),
            gateway,
            str(it.get("PrefixOrigin", "")))


def get_dns(alias):
    items = ps_json("Get-DnsClientServerAddress -InterfaceAlias '%s' -AddressFamily IPv4 "
                    "-ErrorAction SilentlyContinue | Select-Object ServerAddresses" % alias)
    servers = []
    for it in items:
        servers.extend(str(s) for s in (it.get("ServerAddresses") or []))
    return servers


def get_search_domains(alias):
    """读取每网卡的 DNS 后缀搜索列表（注册表 SearchList，逗号分隔）"""
    out = ps("$g=(Get-NetAdapter -InterfaceAlias '%s' -ErrorAction SilentlyContinue).InterfaceGuid; "
             "if($g){ (Get-ItemProperty -Path \"HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\$g\" "
             "-Name SearchList -ErrorAction SilentlyContinue).SearchList }" % alias)
    return [s.strip() for s in out.split(",") if s.strip()]


def get_pac_state():
    """返回 (enabled, url)"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_READ)
        url, _ = winreg.QueryValueEx(key, "AutoConfigURL")
        winreg.CloseKey(key)
        return True, url
    except (FileNotFoundError, OSError):
        return False, ""


def refresh_internet_settings():
    """通知系统代理设置已更改"""
    INTERNET_OPTION_SETTINGS_CHANGED = 39
    INTERNET_OPTION_REFRESH = 37
    wininet = ctypes.windll.wininet
    wininet.InternetSetOptionW(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
    wininet.InternetSetOptionW(None, INTERNET_OPTION_REFRESH, None, 0)


# ---------------------------------------------------------------- 应用设置 --

def report(checks):
    """只输出一行结果；全部生效时列实际值，失败时只列不一致项。"""
    bad = [(name, actual, expect) for name, actual, expect in checks if actual != expect]
    if not bad:
        print(c("  ✓ 已生效  ", Style.GREEN, Style.BOLD)
              + "  ".join("%s %s" % (name, actual) for name, actual, _ in checks))
        return
    print(c("  ✗ 未生效：", Style.RED, Style.BOLD)
          + "；".join("%s 实际 %s / 期望 %s" % (name, actual or "空", expect)
                     for name, actual, expect in bad))
    hint("反复失败请检查是否以管理员身份运行")


def netsh(args):
    out = run_cmd(["netsh"] + args)
    if out:
        print(out)


def apply_manual(service, ip, netmask, gateway, dns_list, search_domains):
    step("正在应用静态 IP")
    netsh(["interface", "ipv4", "set", "address", "name=%s" % service,
           "source=static", "addr=%s" % ip, "mask=%s" % netmask,
           "gateway=%s" % (gateway or "none")])

    if dns_list:
        netsh(["interface", "ipv4", "set", "dnsservers", "name=%s" % service,
               "source=static", "addr=%s" % dns_list[0], "validate=no"])
        for d in dns_list[1:]:
            netsh(["interface", "ipv4", "add", "dnsservers", "name=%s" % service,
                   "addr=%s" % d, "validate=no"])
    else:
        netsh(["interface", "ipv4", "set", "dnsservers", "name=%s" % service,
               "source=static", "addr=none", "validate=no"])

    ps("$g=(Get-NetAdapter -InterfaceAlias '%s' -ErrorAction SilentlyContinue).InterfaceGuid; "
       "if($g){ Set-ItemProperty -Path \"HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\$g\" "
       "-Name SearchList -Value '%s' }" % (service, ",".join(search_domains)))

    time_sleep()
    cur_ip, prefix, gw, _origin = get_ipv4_info(service)
    cur_dns = get_dns(service)
    cur_suffix = get_search_domains(service)
    expect_prefix = mask_to_prefix(netmask)
    report([
        ("IP 地址", cur_ip, ip),
        ("子网掩码", "/%d" % prefix if prefix >= 0 else "（空）", "/%d" % expect_prefix),
        ("网关", gw or "（空）", gateway or "On-link"),
        ("DNS", " ".join(cur_dns) or "（已清除）", " ".join(dns_list) if dns_list else "（已清除）"),
        ("搜索域", " ".join(cur_suffix) or "（已清除）", " ".join(search_domains) if search_domains else "（已清除）"),
    ])


def apply_dhcp(service):
    step("正在切换 DHCP")
    netsh(["interface", "ipv4", "set", "address", "name=%s" % service, "source=dhcp"])
    netsh(["interface", "ipv4", "set", "dnsservers", "name=%s" % service, "source=dhcp"])
    ps("$g=(Get-NetAdapter -InterfaceAlias '%s' -ErrorAction SilentlyContinue).InterfaceGuid; "
       "if($g){ Remove-ItemProperty -Path \"HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\$g\" "
       "-Name SearchList -ErrorAction SilentlyContinue }" % service)

    time_sleep()
    cur_ip, prefix, gw, origin = get_ipv4_info(service)
    cur_dns = get_dns(service)
    cur_suffix = get_search_domains(service)
    report([
        ("地址来源", "Dhcp" if origin == "Dhcp" else (origin or "（空）"), "Dhcp"),
        ("DNS", " ".join(cur_dns) or "（已清除）", "（已清除）"),
        ("搜索域", " ".join(cur_suffix) or "（已清除）", "（已清除）"),
    ])


def apply_pac(url):
    step("正在设置 PAC")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, url)
        winreg.CloseKey(key)
        refresh_internet_settings()
    except OSError as e:
        error("设置失败: %s" % e)

    time_sleep()
    enabled, actual_url = get_pac_state()
    report([
        ("PAC 代理", "已启用" if enabled else "未启用", "已启用"),
        ("代理链接", actual_url, url),
    ])


def apply_pac_off():
    step("正在关闭 PAC 代理")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "AutoConfigURL")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        refresh_internet_settings()
    except OSError as e:
        error("关闭失败: %s" % e)

    time_sleep()
    enabled, _url = get_pac_state()
    report([
        ("PAC 代理", "已启用" if enabled else "已关闭", "已关闭"),
    ])


def time_sleep():
    time.sleep(2)  # 等待系统应用网络配置


# ---------------------------------------------------------------- 交互 UI --

def show_info(service):
    ip, prefix, gw, origin = get_ipv4_info(service)
    dns = get_dns(service)
    suffix = get_search_domains(service)
    enabled, url = get_pac_state()
    print("  %s %s  %s %s/%s  网关 %s" % (
        c("当前 ·", Style.GREY), c(service, Style.BOLD, Style.CYAN),
        c(origin or "手动", Style.DIM), ip or "-",
        (str(prefix) if prefix >= 0 else "-"), gw or "-"))
    pac = c("开 " + url if enabled and url else ("开" if enabled else "关"),
            Style.GREEN if enabled else Style.DIM)
    print("  DNS %s  搜索域 %s  PAC %s" % (
        " ".join(dns) or "无", " ".join(suffix) or "无", pac))


def config_summary(profiles):
    """列出当前配置，方便在选网卡前确认参数"""
    company, home, proxy = profiles["company"], profiles["home"], profiles["proxy"]
    for label, p, color in (("公司", company, Style.GREEN), ("家里", home, Style.CYAN)):
        parts = ["%s/%s" % (p["ip"] or "空", p["netmask"] or "空"),
                 "网关 " + (p["gateway"] or "空"),
                 "DNS " + (" ".join(p["dns"]) or "无")]
        if p["search_domains"]:
            parts.append("搜索域 " + " ".join(p["search_domains"]))
        print("  %s %s" % (c(label, Style.BOLD, color), "  ".join(parts)))
    print("  %s WAN %s  LAN %s" % (c("PAC", Style.BOLD, Style.MAGENTA),
                                   proxy["wan"] or "未配置", proxy["lan"] or "未配置"))


def choose_service(profiles):
    """选择网卡。返回 ("run", 网卡名) / ("edit", c/h/p/o) / ("quit", None)"""
    adapters = list_adapters()
    if not adapters:
        error("未找到任何网卡，请检查设备管理器")
        sys.exit(1)

    active = active_adapter()
    section("网卡")
    for i, (name, status, desc) in enumerate(adapters):
        up = status.lower() == "up"
        mark = c("  ★ 当前活动", Style.GREEN, Style.BOLD) if name == active else ""
        print("  %s %-14s %-5s %s%s" % (c(pad("[%d]" % i, 3), Style.BOLD, Style.CYAN),
                                        c(name, Style.GREEN if up else Style.DIM),
                                        status, c(desc, Style.DIM), mark))
    if not active:
        warn("未识别到活动网卡，请手动选序号")

    config_summary(profiles)
    hint("c 改公司 · h 改家里 · p 改 PAC · o 配置文件 · q 退出")

    last = len(adapters) - 1
    default_hint = ("，回车=" + active) if active else ""
    prompt = c("序号 (0-%d%s): " % (last, default_hint), Style.BOLD, Style.CYAN)
    while True:
        raw = read_line(prompt).strip().lower()
        if not raw:
            if active:
                return "run", active
            warn("未识别到活动网卡，请输入序号选择")
            continue
        if raw.isdigit() and 0 <= int(raw) <= last:
            return "run", adapters[int(raw)][0]
        if raw in ("c", "h", "p", "o"):
            return "edit", raw
        if raw in ("q", "quit", "exit"):
            return "quit", None
        warn("输入无效，请输入网卡序号或 c/h/p/o")


def prompt_ip(profile):
    prompt = c("请输入 IP（回车使用配置默认 %s）: " % profile["ip"], Style.BOLD, Style.CYAN)
    raw = read_line(prompt).strip()
    return raw or profile["ip"]


# ---------------------------------------------------------------- 设置菜单 --

def valid_ip(text):
    parts = text.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def valid_netmask(text):
    if not valid_ip(text):
        return False
    bits = "".join(format(int(p), "08b") for p in text.split("."))
    return "01" not in bits  # 掩码必须是连续的 1


def valid_url(text):
    return text.startswith("http://") or text.startswith("https://")


def parse_list(text):
    """逗号或空格分隔 -> 列表；输入 - 表示清空"""
    if text.strip() == "-":
        return []
    return [s for s in text.replace(",", " ").split() if s]


def ask(label, current, validator=None, list_value=False):
    """带默认值和校验的输入。回车保留原值，输入 - 清空列表。"""
    shown = " ".join(current) if list_value else (current or "空")
    prompt = "  %s %s " % (c(pad(label, 12), Style.GREY),
                           c("[%s]:" % shown, Style.DIM))
    while True:
        raw = read_line(prompt).strip()
        if not raw:
            return list(current) if list_value else current
        if list_value:
            return parse_list(raw)
        if validator and not validator(raw):
            warn("格式不正确，请重新输入")
            continue
        return raw


def edit_profile(profiles, key, label):
    p = profiles[key]
    print("")
    print_caption("修改【%s】配置" % label,
                  "回车保持不变，列表中输入 - 表示清空")
    ip = ask("IP 地址", p["ip"], valid_ip)
    netmask = ask("子网掩码", p["netmask"], valid_netmask)
    gateway = ask("网关", p["gateway"], valid_ip)
    dns = ask("DNS", p["dns"], list_value=True)
    domains = ask("搜索域", p["search_domains"], list_value=True)
    profiles[key] = {"ip": ip, "netmask": netmask, "gateway": gateway,
                     "dns": dns, "search_domains": domains}


def edit_proxy(profiles):
    p = profiles["proxy"]
    print("")
    print_caption("修改 PAC 代理链接", "回车保持不变")
    wan = ask("WAN-PROXY", p["wan"], valid_url)
    lan = ask("LAN-PROXY", p["lan"], valid_url)
    profiles["proxy"] = {"wan": wan, "lan": lan}


def open_config_in_editor(path):
    """用记事本打开配置文件（会等待记事本关闭）"""
    step("用记事本打开: %s" % path)
    subprocess.run(["notepad", path])
    read_line(c("  修改并保存后，按回车键重新加载配置 ... ", Style.BOLD, Style.CYAN))


def commit_config(config_path, profiles):
    """保存配置并重新加载，返回 (config_path, profiles)"""
    saved = save_config(config_path, profiles)
    if not saved:
        error("保存失败：配置目录不可写，请检查 %s 的权限" % config_path)
        return config_path, profiles
    config_path = saved
    profiles = load_config(config_path)
    success("已保存并生效: %s" % config_path)
    config_summary(profiles)
    return config_path, profiles


def handle_edit(code, config_path, profiles):
    """按编号编辑配置并保存，返回 (config_path, profiles)
    code: c=公司 h=家里 p=PAC链接 o=打开配置文件（也可传 "5"-"8"）
    """
    code = {"5": "c", "6": "h", "7": "p", "8": "o"}.get(code, code)
    if code == "c":
        edit_profile(profiles, "company", "公司")
    elif code == "h":
        edit_profile(profiles, "home", "家里")
    elif code == "p":
        edit_proxy(profiles)
    elif code == "o":
        open_config_in_editor(config_path)
        try:
            return config_path, load_config(config_path)
        except SystemExit:
            warn("配置文件有误，已保留内存中的旧配置")
            return config_path, profiles
    return commit_config(config_path, profiles)


def main():
    banner()

    if not is_admin():
        warn("修改网络设置需要管理员权限，正在请求提权（请在 UAC 弹窗中点\"是\"）")
        run_as_admin()
        return  # 提权后的新进程接管，本进程退出

    state = {"config": get_config_path()}
    state["profiles"] = load_config(state["config"])

    # 外层循环：任意步骤输入 m 即整体回到选网卡主界面
    while True:
        try:
            while True:
                clear()
                action, value = choose_service(state["profiles"])
                if action == "quit":
                    print(c("  再见！", Style.DIM))
                    return
                if action == "edit":
                    clear()
                    state["config"], state["profiles"] = handle_edit(
                        value, state["config"], state["profiles"])
                    pause()
                    continue
                service = value
                break

            while True:
                clear()
                show_info(service)
                profiles = state["profiles"]
                print("")
                print("  %s 1 公司  2 家里  3 DHCP  4 代理 PAC" % c("应用", Style.BOLD, Style.CYAN))
                hint("5 改公司 · 6 改家里 · 7 改 PAC · 8 配置文件 · m 主界面 · q 退出")
                choice = read_line(c("选择: ", Style.BOLD, Style.CYAN)).strip().lower()

                if choice in ("q", "quit", "exit"):
                    print(c("  再见！", Style.DIM))
                    return

                clear()  # 进入结果屏：抹掉菜单，本屏只留执行过程与结果
                if choice == "1":
                    p = profiles["company"]
                    apply_manual(service, prompt_ip(p), p["netmask"], p["gateway"],
                                 p["dns"], p["search_domains"])
                elif choice == "2":
                    p = profiles["home"]
                    apply_manual(service, prompt_ip(p), p["netmask"], p["gateway"],
                                 p["dns"], p["search_domains"])
                elif choice == "3":
                    apply_dhcp(service)
                elif choice == "4":
                    proxy = profiles["proxy"]
                    if not proxy["wan"] or not proxy["lan"]:
                        warn("配置文件中 proxy 段缺少 wan/lan 链接，请先补充: %s" % state["config"])
                        pause()
                        continue
                    hint("1 WAN  2 LAN  3 关闭")
                    sub = read_line(c("PAC 选择: ", Style.BOLD, Style.CYAN)).strip()
                    if sub == "1":
                        apply_pac(proxy["wan"])
                    elif sub == "2":
                        apply_pac(proxy["lan"])
                    elif sub == "3":
                        apply_pac_off()
                    else:
                        warn("输入无效，请输入 1 / 2 / 3")
                elif choice in ("5", "6", "7", "8"):
                    clear()
                    state["config"], state["profiles"] = handle_edit(
                        choice, state["config"], state["profiles"])
                else:
                    warn("输入无效，请输入 1-8 / q")
                pause()
        except GoHome:
            try:
                state["profiles"] = load_config(state["config"])
            except SystemExit:
                pass
            hint("已返回主界面")
            continue
        except QuitApp:
            print(c("  再见！", Style.DIM))
            return


if __name__ == "__main__":
    main()
