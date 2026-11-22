#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SetIP - macOS IP 快速切换工具
# 菜单：1、公司  2、家里  3、DHCP
# 配置文件：config.yaml（首次运行自动生成）

import os
import re
import subprocess
import sys
import time
import unicodedata

try:
    import yaml
except ImportError:
    print("缺少依赖 PyYAML，请先执行: pip3 install pyyaml")
    sys.exit(1)

APP_NAME = "IP 管理器 SetIP"
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
    """Windows 10+ 控制台开启 ANSI 转义支持"""
    try:
        import ctypes
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
    if os.name == "nt":
        return _enable_windows_ansi()
    return os.environ.get("TERM", "") != "dumb"


USE_COLOR = _detect_color()

# 原生 App 窗口模式：输出 \001TYPE\001字段\002字段 结构化指令，
# 由 mac/SetIPHost.m 渲染成卡片/徽章；Windows 控制台与终端仍走 ANSI 文本。
NATIVE = os.environ.get("SETIP_NATIVE") == "1"
SEP = "\x02"


def emit(kind, *fields):
    """向原生窗口发送一行结构化指令（非 native 模式忽略）。"""
    if not NATIVE:
        return
    sys.stdout.write("\x01" + kind + "\x01" + SEP.join(str(f) for f in fields) + "\n")
    sys.stdout.flush()


class GoHome(Exception):
    """用户在任意步骤请求返回主界面（按钮 / Esc / 输入 m）。"""


class QuitApp(Exception):
    """用户在任意步骤请求退出（q）。"""


# 宿主按「主界面」按钮或 Esc 时写入 ESC 字符；手动输入 m/home 也识别
HOME_TOKENS = ("\x1b", "m", "home", "主界面")
QUIT_TOKENS = ("q", "quit", "exit")


def is_home(raw):
    return (raw or "").strip().lower() in HOME_TOKENS


def is_quit(raw):
    return (raw or "").strip().lower() in QUIT_TOKENS


def read_line(prompt=""):
    """读取一行；统一识别「返回主界面」与「退出」，任意步骤都生效。"""
    raw = input(prompt)
    if NATIVE and is_home(raw):
        raise GoHome()
    if is_quit(raw):
        raise QuitApp()
    return raw


def native_input(prompt="", show=True):
    """原生窗口下把提示渲染成灰色小字，真正的输入走底部输入框。
    show=False 用于输入校验的重试循环，避免同一提示在界面上反复堆积。
    """
    if NATIVE:
        if show and prompt:
            emit("sub", prompt.strip())
        return read_line("")
    return read_line(prompt)


def c(text, *styles):
    """给文本加颜色/样式；未启用颜色时原样返回"""
    if not USE_COLOR or not styles:
        return str(text)
    return "".join(styles) + str(text) + Style.RESET


def dlen(text):
    """按终端显示宽度计长度（中日韩字符按 2 计）"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in str(text))


def pad(text, width):
    text = str(text)
    return text + " " * max(0, width - dlen(text))


def row(label, value, label_width=12, value_style=None, label_style=Style.GREY):
    """对齐的一行「标签 + 值」"""
    shown = c(value, value_style) if value_style else str(value)
    print("  %s %s" % (c(pad(label, label_width), label_style), shown))


def info(msg):
    if NATIVE:
        emit("text", msg)
        return
    print("  " + msg)


def step(msg):
    if NATIVE:
        emit("step", msg)
        return
    print(c("  ▸ " + msg + " ...", Style.BLUE))


def hint(msg):
    if NATIVE:
        emit("hint", msg)
        return
    print(c("  " + msg, Style.DIM))


def warn(msg):
    if NATIVE:
        emit("warn", msg)
        return
    print(c("  ⚠ " + msg, Style.YELLOW))


def error(msg):
    if NATIVE:
        emit("fail", msg)
        return
    print(c("  ✗ " + msg, Style.RED))


def success(msg):
    if NATIVE:
        emit("ok", msg)
        return
    print(c("  ✓ " + msg, Style.GREEN))


def section(title, style=Style.CYAN):
    if NATIVE:
        emit("title", title)
        return
    print(c(RULE, Style.GREY))
    print(c(" " + title, Style.BOLD, style))


def print_caption(title, note=""):
    if NATIVE:
        emit("title", title)
        if note:
            emit("sub", note)
        return
    print(c("  " + title, Style.BOLD, Style.CYAN)
          + (c("   " + note, Style.DIM) if note else ""))


def menu_item(key, label, key_style=Style.CYAN):
    if NATIVE:
        emit("menu", key, label)
        return
    print("  %s %s" % (c(pad(key, 2), Style.BOLD, key_style), label))


def banner(subtitle=""):
    if NATIVE:
        return  # 原生窗口已有蓝色标题栏，不再重复
    print(c("  " + APP_NAME + (("  ·  " + subtitle) if subtitle else ""),
            Style.BOLD, Style.CYAN))


def clear():
    """清屏并归位光标：进入下一步时抹掉上一步的输出。"""
    if NATIVE:
        # 原生窗口靠 ESC[2J 判断从哪一行开始重画
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        return
    if not (USE_COLOR or sys.stdout.isatty()):
        return
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def pause():
    """停驻一步，让用户看完本步结果后再按回车进入下一步。"""
    if NATIVE:
        emit("hint", "回车返回菜单  ·  m 返回主界面  ·  q 退出")
        read_line("")
        return
    input(c("\n  按回车继续 ...", Style.DIM))

# ---------------------------------------------------------------- 配置文件 --

CONFIG_TEMPLATE = """\
# ==========================================================
# SetIP 配置文件（YAML 格式）
# 直接用文本编辑器修改保存即可，下次启动程序生效。
# dns / search_domains 支持多个值，一行一个（用 "- " 开头）；
# search_domains 不需要就留空 []。
# ==========================================================

company:                # 公司
  ip: 10.91.140.5
  netmask: 255.255.254.0
  gateway: 10.91.140.1
  dns:
    - 10.91.140.1
  search_domains: []    # 示例: [buyabs.corp] 或写成多行 - buyabs.corp

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


def is_frozen():
    """是否为 PyInstaller 打包后的可执行文件"""
    return getattr(sys, "frozen", False)


def config_candidates():
    """配置文件候选路径（按优先级）。
    .app 内运行时优先用包内 Resources/config.yaml，让配置跟着 app 走；
    包内不可写时回退到 ~/.setip/config.yaml。
    """
    paths = []
    if is_frozen():
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))          # SetIP.app/Contents/MacOS
        res_dir = os.path.join(os.path.dirname(exe_dir), "Resources")       # SetIP.app/Contents/Resources
        paths.append(os.path.join(res_dir, "config.yaml"))
    else:
        paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml"))
    paths.append(os.path.join(os.path.expanduser("~"), ".setip", "config.yaml"))
    return paths


def get_config_path():
    """找到已有配置文件；没有则在第一个可写位置生成模板"""
    for path in config_candidates():
        if os.path.isfile(path):
            return path
    for path in config_candidates():
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(CONFIG_TEMPLATE)
            success("未找到配置文件，已自动生成模板: %s" % path)
            return path
        except OSError:
            continue
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
              "# SetIP 配置文件（YAML 格式）\n"
              "# 由程序「设置」菜单生成，也可以直接用文本编辑器修改。\n"
              "# ==========================================================\n\n")
    text = header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                                  default_flow_style=False)
    for target in (path, os.path.join(os.path.expanduser("~"), ".setip", "config.yaml")):
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
            return target
        except OSError:
            continue
    return None


def load_config(path):
    """读取并校验配置"""
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

    # PAC 代理配置：允许缺省，缺省时选项 4 会提示先去补配置
    proxy = data.get("proxy") or {}
    profiles["proxy"] = {
        "wan": str(proxy.get("wan", "")).strip(),
        "lan": str(proxy.get("lan", "")).strip(),
    }
    return profiles


# ------------------------------------------------------------ 命令封装 --
# 注意：全部使用参数列表调用，不经 shell，网卡名带空格也不会出错；
# 且等待命令真正执行完成后再读取结果。

def run_cmd(args):
    result = subprocess.run(args, capture_output=True, text=True)
    return result.stdout.strip()


def list_services():
    """获取网卡（网络服务）列表；去掉禁用服务前的 * 号"""
    out = run_cmd(["networksetup", "-listallnetworkservices"])
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return [l.lstrip("*").strip() for l in lines[1:]]  # 首行是说明文字


def active_service():
    """识别当前承载默认路由的网卡服务名；识别不出来返回 None。

    优先：默认路由的 interface (如 en0) → 硬件端口名 → 网络服务名；
    兜底：接口 IPv4 地址 → getinfo 里的 IP；再兜底：第一个有 IP 的服务。
    """
    services = list_services()
    if not services:
        return None

    route_out = run_cmd(["route", "-n", "get", "default"])
    dev = ""
    for line in route_out.splitlines():
        m = re.search(r"\binterface:\s*(\S+)", line)
        if m:
            dev = m.group(1)
            break
    if not dev:
        return None

    # 1) 设备名 → 硬件端口 → 服务名
    ports = run_cmd(["networksetup", "-listallhardwareports"])
    blocks = ports.split("Hardware Port:")
    for block in blocks[1:]:
        lines = [x.strip() for x in block.splitlines() if x.strip()]
        if not lines:
            continue
        if any(line.lower() == "device: " + dev.lower() for line in lines):
            port = lines[0]
            if port in services:
                return port

    # 2) 接口 IPv4 → 服务的 IP（VPN 的 utun 接口没有硬件端口，走这条路）
    inet = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)", run_cmd(["ifconfig", dev]))
    if inet:
        for service in services:
            getinfo = run_cmd(["networksetup", "-getinfo", service])
            if parse_getinfo(getinfo, "IP address") == inet.group(1):
                return service

    # 3) 最后兜底：第一个配置了非 APIPA 地址的服务
    for service in services:
        ip = parse_getinfo(run_cmd(["networksetup", "-getinfo", service]), "IP address")
        if ip and not ip.startswith("169.254"):
            return service
    return None


def show_info(service):
    """选中网卡后的单行概览，不转储 getinfo 全文"""
    getinfo = run_cmd(["networksetup", "-getinfo", service])
    ip = parse_getinfo(getinfo, "IP address") or "-"
    mask = parse_getinfo(getinfo, "Subnet mask") or "-"
    gw = parse_getinfo(getinfo, "Router") or "-"
    mode = "DHCP" if "DHCP Configuration" in getinfo else (parse_getinfo(getinfo, "DHCP / Bootp / Manual") or "手动")
    if not NATIVE:
        print("  %s %s  %s %s/%s  网关 %s" % (
            c("当前 ·", Style.GREY), c(service, Style.BOLD, Style.CYAN),
            c(mode, Style.DIM), ip, mask, gw))
    dns_list = get_dns_list(service)
    if not dns_list:
        # DHCP 模式下 -getdnsservers 只返回静态配置（空），实际 DNS 由 DHCP 下发，
        # 回退到 scutil --dns 读取该网卡当前生效的 DNS。
        dns_list = dns_from_scutil(service_device(service))
    dns = " ".join(dns_list) or "无"
    domains = " ".join(get_search_domains(service)) or "无"
    enabled, url = get_pac_state(service)
    pac = c("开 " + url if enabled and url else ("开" if enabled else "关"),
            Style.GREEN if enabled else Style.DIM)
    if NATIVE:
        emit("state", "%s · %s" % (mode, service), "%s/%s  网关 %s" % (ip, mask, gw))
        emit("state", "DNS", dns)
        emit("state", "搜索域", domains)
        emit("state", "PAC", ("开 " + url if enabled and url else ("开" if enabled else "关")))
        return
    print("  DNS %s  搜索域 %s  PAC %s" % (dns, domains, pac))


def parse_getinfo(info, label):
    """从 -getinfo 输出中取某个字段的值"""
    for line in info.splitlines():
        if line.startswith(label):
            return line.split(":", 1)[1].strip()
    return ""


def get_dns_list(service):
    """读取当前 DNS，未设置时返回空列表"""
    out = run_cmd(["networksetup", "-getdnsservers", service])
    if out.startswith("There aren't any DNS Servers set"):
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]


def service_device(service):
    """把 networksetup 服务名映射到 BSD 设备名（如 Wi-Fi -> en0），失败返回空串。"""
    out = run_cmd(["networksetup", "-listallhardwareports"])
    port = ""
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Hardware Port:"):
            port = line.split(":", 1)[1].strip()
        elif line.startswith("Device:") and port:
            dev = line.split(":", 1)[1].strip()
            if service == port or service.startswith(port) or port in service:
                return dev
    return ""


def dns_from_scutil(device):
    """从 scutil --dns 读取某设备当前生效的 DNS（含 DHCP 下发），去重。
    -getdnsservers 只能看到静态配置，DHCP 下发的 DNS 需要通过这里读取。
    """
    if not device:
        return []
    out = run_cmd(["scutil", "--dns"])
    blocks, cur = [], []
    for line in out.splitlines():
        if line.strip().startswith("resolver #"):
            if cur:
                blocks.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        blocks.append(cur)
    result = []
    for block in blocks:
        text = "\n".join(block)
        if not re.search(r"if_index\s*:\s*\d+\s*\(" + re.escape(device) + r"\)", text):
            continue
        for line in block:
            m = re.match(r"\s*nameserver\[\d+\]\s*:\s*(\S+)", line)
            if m and m.group(1) not in result:
                result.append(m.group(1))
    return result


def get_search_domains(service):
    """读取当前搜索域，未设置时返回空列表"""
    out = run_cmd(["networksetup", "-getsearchdomains", service])
    if out.startswith("There aren't any Search Domains set"):
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]


def get_pac_state(service):
    """读取 PAC 代理状态，返回 (enabled, url)"""
    out = run_cmd(["networksetup", "-getautoproxyurl", service])
    enabled = "Enabled: Yes" in out
    url = ""
    for line in out.splitlines():
        if line.startswith("URL:"):
            url = line.split(":", 1)[1].strip()
    if url in ("(null)", "None"):
        url = ""
    return enabled, url


def report(checks):
    """只输出一行结果；全部生效时列实际值，失败时只列不一致项。"""
    bad = [(name, actual, expect) for name, actual, expect in checks if actual != expect]
    if NATIVE:
        if not bad:
            emit("ok", "  ".join("%s %s" % (name, actual) for name, actual, _ in checks))
        else:
            emit("fail", "；".join("%s 实际 %s / 期望 %s" % (name, actual or "空", expect)
                                  for name, actual, expect in bad))
            emit("hint", "反复失败请检查是否需要管理员权限")
        return
    if not bad:
        print(c("  ✓ 已生效  ", Style.GREEN, Style.BOLD)
              + "  ".join("%s %s" % (name, actual) for name, actual, _ in checks))
        return
    print(c("  ✗ 未生效：", Style.RED, Style.BOLD)
          + "；".join("%s 实际 %s / 期望 %s" % (name, actual or "空", expect)
                     for name, actual, expect in bad))
    hint("反复失败请检查是否需要管理员权限")


def apply_manual(service, ip, netmask, gateway, dns_list, search_domains):
    """设置为手动 IP。search_domains 为空列表时清除搜索域设置。"""
    step("正在应用静态 IP")
    out = run_cmd(["networksetup", "-setmanual", service, ip, netmask, gateway])
    if out:
        info(out.strip())
    run_cmd(["networksetup", "-setdnsservers", service] + (dns_list or ["empty"]))
    run_cmd(["networksetup", "-setsearchdomains", service] + (search_domains or ["Empty"]))

    # 回读校验，展示应用情况
    time.sleep(1)
    getinfo = run_cmd(["networksetup", "-getinfo", service])
    report([
        ("IP 地址", parse_getinfo(getinfo, "IP address"), ip),
        ("子网掩码", parse_getinfo(getinfo, "Subnet mask"), netmask),
        ("网关", parse_getinfo(getinfo, "Router"), gateway),
        ("DNS", " ".join(get_dns_list(service)) or "（已清除）", " ".join(dns_list) if dns_list else "（已清除）"),
        ("搜索域", " ".join(get_search_domains(service)) or "（已清除）", " ".join(search_domains) if search_domains else "（已清除）"),
    ])


def apply_pac(service, url):
    """启用 PAC 自动代理"""
    step("正在设置 PAC")
    out = run_cmd(["networksetup", "-setautoproxyurl", service, url])
    if out:
        info(out.strip())

    time.sleep(1)
    enabled, actual_url = get_pac_state(service)
    report([
        ("PAC 代理", "已启用" if enabled else "未启用", "已启用"),
        ("代理链接", actual_url, url),
    ])


def apply_pac_off(service):
    """关闭 PAC 自动代理"""
    step("正在关闭 PAC 代理")
    out = run_cmd(["networksetup", "-setautoproxystate", service, "off"])
    if out:
        info(out.strip())

    time.sleep(1)
    enabled, actual_url = get_pac_state(service)
    report([
        ("PAC 代理", "已启用" if enabled else "已关闭", "已关闭"),
    ])
    if actual_url:
        hint("代理链接 %s 已保留，但处于关闭状态" % actual_url)


def apply_dhcp(service):
    """设置为 DHCP 自动获取，并清除 DNS / 搜索域的手动设置"""
    step("正在切换为 DHCP 自动获取")
    out = run_cmd(["networksetup", "-setdhcp", service])
    if out:
        info(out.strip())
    run_cmd(["networksetup", "-setdnsservers", service, "empty"])
    run_cmd(["networksetup", "-setsearchdomains", service, "Empty"])

    # 回读校验，展示应用情况
    time.sleep(1)
    getinfo = run_cmd(["networksetup", "-getinfo", service])
    mode = "DHCP" if "DHCP Configuration" in getinfo else (parse_getinfo(getinfo, "DHCP / Bootp / Manual") or "Manual")
    report([
        ("配置模式", mode, "DHCP"),
        ("DNS", " ".join(get_dns_list(service)) or "（已清除）", "（已清除）"),
        ("搜索域", " ".join(get_search_domains(service)) or "（已清除）", "（已清除）"),
    ])


# ---------------------------------------------------------------- 交互 UI --

def config_summary(profiles):
    """列出当前配置，方便在选网卡前确认参数"""
    company, home, proxy = profiles["company"], profiles["home"], profiles["proxy"]
    if NATIVE:
        emit("title", "当前配置")
    for label, p, color in (("公司", company, Style.GREEN), ("家里", home, Style.CYAN)):
        parts = ["%s/%s" % (p["ip"] or "空", p["netmask"] or "空"),
                 "网关 " + (p["gateway"] or "空"),
                 "DNS " + (" ".join(p["dns"]) or "无")]
        if p["search_domains"]:
            parts.append("搜索域 " + " ".join(p["search_domains"]))
        if NATIVE:
            emit("kv", label, "  ".join(parts))
        else:
            print("  %s %s" % (c(label, Style.BOLD, color), "  ".join(parts)))
    if NATIVE:
        emit("kv", "PAC", "WAN %s   LAN %s" % (proxy["wan"] or "未配置", proxy["lan"] or "未配置"))
    else:
        print("  %s WAN %s  LAN %s" % (c("PAC", Style.BOLD, Style.MAGENTA),
                                       proxy["wan"] or "未配置", proxy["lan"] or "未配置"))


def choose_service(profiles):
    """选择网卡。返回 ("run", 网卡名) / ("edit", c/h/p/o) / ("quit", None)"""
    services = list_services()
    if not services:
        error("未找到任何网络服务，请检查系统设置")
        sys.exit(1)

    active = active_service()
    section("选择网卡")
    for i, name in enumerate(services):
        if NATIVE:
            emit("adapter", "[%d]" % i, name, "1" if name == active else "0")
        else:
            mark = c("  ★ 当前活动", Style.GREEN, Style.BOLD) if name == active else ""
            print("  %s %s%s" % (c(pad("[%d]" % i, 3), Style.BOLD, Style.CYAN), name, mark))
    if not active:
        warn("未识别到活动网卡，请手动选序号")

    config_summary(profiles)
    hint("c 改公司 · h 改家里 · p 改 PAC · o 配置文件 · q 退出")

    last = len(services) - 1
    default_hint = ("，回车=" + active) if active else ""
    prompt = c("序号 (0-%d%s): " % (last, default_hint), Style.BOLD, Style.CYAN)
    first = True
    while True:
        raw = native_input(prompt, show=first).strip().lower()
        first = False
        if not raw:
            if active:
                return "run", active
            warn("未识别到活动网卡，请输入序号选择")
            continue
        if raw.isdigit() and 0 <= int(raw) <= last:
            return "run", services[int(raw)]
        if raw in ("c", "h", "p", "o"):
            return "edit", raw
        if raw in ("q", "quit", "exit"):
            return "quit", None
        warn("输入无效，请输入网卡序号或 c/h/p/o")


def prompt_ip(profile):
    """公司/家里模式：可临时修改 IP，直接回车使用配置默认值"""
    prompt = c("请输入 IP（回车使用配置默认 %s）: " % profile["ip"], Style.BOLD, Style.CYAN)
    raw = native_input(prompt).strip()
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
    first = True
    while True:
        raw = native_input(prompt, show=first).strip()
        first = False
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
    """用系统默认文本编辑器打开配置文件"""
    step("用文本编辑器打开: %s" % path)
    subprocess.run(["open", "-t", path])
    native_input(c("  修改并保存后，按回车键重新加载配置 ... ", Style.BOLD, Style.CYAN))


def commit_config(config_path, profiles):
    """保存配置并重新加载，返回 (config_path, profiles)"""
    saved = save_config(config_path, profiles)
    if not saved:
        error("保存失败：配置文件和 ~/.setip 都不可写，请检查 app 所在位置权限")
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
    banner("macOS")

    state = {"config": get_config_path()}
    state["profiles"] = load_config(state["config"])

    # 外层循环：GoHome 回选网卡；QuitApp 在任意步骤都能真正退出
    while True:
        try:
            # 选网卡界面（同时展示当前配置、可直接改配置）
            while True:
                clear()
                action, value = choose_service(state["profiles"])
                if action == "quit":
                    info("再见！")
                    return
                if action == "edit":
                    clear()  # 配置编辑另起一屏，不叠在网卡列表上
                    state["config"], state["profiles"] = handle_edit(
                        value, state["config"], state["profiles"])
                    pause()
                    continue
                service = value
                break

            # 应用菜单
            while True:
                clear()
                show_info(service)
                profiles = state["profiles"]
                if NATIVE:
                    emit("title", "应用配置")
                    for k, label in (("1", "公司"), ("2", "家里"), ("3", "DHCP 自动获取"), ("4", "代理 PAC")):
                        emit("menu", k, label)
                    emit("hint", "5 改公司 · 6 改家里 · 7 改 PAC · 8 配置文件 · m 主界面 · q 退出")
                else:
                    print("")
                    print("  %s 1 公司  2 家里  3 DHCP  4 代理 PAC" % c("应用", Style.BOLD, Style.CYAN))
                    hint("5 改公司 · 6 改家里 · 7 改 PAC · 8 配置文件 · q 退出")
                choice = native_input(c("选择: ", Style.BOLD, Style.CYAN)).strip().lower()

                if choice in ("q", "quit", "exit"):
                    info("再见！")
                    return

                clear()  # 进入结果屏：抹掉菜单，本屏只留执行过程与结果
                if choice == "1":
                    apply_manual(service, prompt_ip(profiles["company"]),
                                 profiles["company"]["netmask"], profiles["company"]["gateway"],
                                 profiles["company"]["dns"], profiles["company"]["search_domains"])
                elif choice == "2":
                    apply_manual(service, prompt_ip(profiles["home"]),
                                 profiles["home"]["netmask"], profiles["home"]["gateway"],
                                 profiles["home"]["dns"], profiles["home"]["search_domains"])
                elif choice == "3":
                    apply_dhcp(service)
                elif choice == "4":
                    proxy = profiles["proxy"]
                    if not proxy["wan"] or not proxy["lan"]:
                        warn("配置文件中 proxy 段缺少 wan/lan 链接，请先补充: %s" % state["config"])
                        pause()
                        continue
                    if NATIVE:
                        emit("title", "代理 PAC")
                        emit("menu", "1", "WAN 代理")
                        emit("menu", "2", "LAN 代理")
                        emit("menu", "3", "关闭 PAC")
                    else:
                        print("")
                        print("  " + c("代理 PAC", Style.BOLD, Style.CYAN))
                        print("  1 WAN 代理   2 LAN 代理   3 关闭 PAC")
                    hint("↑↓ 选择或输入 1 / 2 / 3")
                    sub = native_input(c("PAC 选择: ", Style.BOLD, Style.CYAN)).strip()
                    if sub == "1":
                        apply_pac(service, proxy["wan"])
                    elif sub == "2":
                        apply_pac(service, proxy["lan"])
                    elif sub == "3":
                        apply_pac_off(service)
                    else:
                        warn("输入无效，请输入 1 / 2 / 3")
                elif choice in ("5", "6", "7", "8"):
                    clear()  # 配置编辑另起一屏
                    state["config"], state["profiles"] = handle_edit(
                        choice, state["config"], state["profiles"])
                else:
                    warn("输入无效，请输入 1-8 / q")
                pause()
        except GoHome:
            # 一键返回主界面：重新读盘，丢弃未保存的编辑中途状态
            try:
                state["profiles"] = load_config(state["config"])
            except SystemExit:
                pass
            emit("hint", "已返回主界面")
            continue
        except QuitApp:
            info("再见！")
            return


if __name__ == "__main__":
    main()
