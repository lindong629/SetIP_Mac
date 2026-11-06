#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SetIP for Windows - IP 快速切换工具
# 菜单：1、公司  2、家里  3、DHCP  4、代理 PAC
# 配置文件：config.yaml（与 macOS 版格式完全一致，首次运行自动生成）
# 需要 Python 3.8+ 与 PyYAML；打包为 exe 后双击运行，退出后窗口自动关闭。

import ctypes
import os
import subprocess
import sys

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


def config_search_dirs():
    dirs = []
    if is_frozen():
        dirs.append(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(os.path.join(os.path.expanduser("~"), ".setip"))
    return dirs


def get_config_path():
    for d in config_search_dirs():
        path = os.path.join(d, "config.yaml")
        if os.path.isfile(path):
            return path
    for d in config_search_dirs():
        path = os.path.join(d, "config.yaml")
        try:
            os.makedirs(d, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(CONFIG_TEMPLATE)
            print(">> 未找到配置文件，已自动生成模板: %s" % path)
            print(">> 请编辑该文件填入实际参数后重新运行。本次使用模板默认值。")
            return path
        except OSError:
            continue
    print(">> 错误：无法创建配置文件")
    sys.exit(1)


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(">> 配置文件 YAML 格式有误，请检查: %s\n%s" % (path, e))
        sys.exit(1)

    profiles = {}
    for key in ("company", "home"):
        item = data.get(key)
        if not isinstance(item, dict):
            print('>> 配置文件缺少 "%s" 配置段，请检查 %s' % (key, path))
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
        print(">> 需要管理员权限才能修改网络设置，本次退出。")
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
    import json
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
    """打印应用情况校验结果，checks 为 [(名称, 实际值, 期望值), ...]"""
    print("-" * 50)
    print("应用情况：")
    all_ok = True
    for name, actual, expect in checks:
        ok = (actual == expect)
        all_ok = all_ok and ok
        if ok:
            print("  ✓ %s: %s" % (name, actual))
        else:
            print("  ✗ %s: 实际 %s / 期望 %s" % (name, actual or "（空）", expect))
    if all_ok:
        print(">> 全部生效")
    else:
        print(">> 存在未生效项！请稍后重试；反复失败请检查是否以管理员身份运行")
    print("=" * 50)


def netsh(args):
    out = run_cmd(["netsh"] + args)
    if out:
        print(out)


def apply_manual(service, ip, netmask, gateway, dns_list, search_domains):
    print(">> 正在设置 IP ...")
    netsh(["interface", "ipv4", "set", "address", "name=%s" % service,
           "source=static", "addr=%s" % ip, "mask=%s" % netmask,
           "gateway=%s" % (gateway or "none")])

    print(">> 正在设置 DNS ...")
    if dns_list:
        netsh(["interface", "ipv4", "set", "dnsservers", "name=%s" % service,
               "source=static", "addr=%s" % dns_list[0], "validate=no"])
        for d in dns_list[1:]:
            netsh(["interface", "ipv4", "add", "dnsservers", "name=%s" % service,
                   "addr=%s" % d, "validate=no"])
    else:
        netsh(["interface", "ipv4", "set", "dnsservers", "name=%s" % service,
               "source=static", "addr=none", "validate=no"])

    print(">> 正在设置搜索域 ...")
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
        ("子网掩码", "/%d" % prefix if prefix >= 0 else "（空）", "/%d (%s)" % (expect_prefix, netmask)),
        ("网关", gw or "（空）", gateway or "On-link"),
        ("DNS", " ".join(cur_dns) or "（已清除）", " ".join(dns_list) if dns_list else "（已清除）"),
        ("搜索域", " ".join(cur_suffix) or "（已清除）", " ".join(search_domains) if search_domains else "（已清除）"),
    ])


def apply_dhcp(service):
    print(">> 正在切换为 DHCP 自动获取 ...")
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
    print(">> 正在设置 PAC 代理: %s" % url)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, url)
        winreg.CloseKey(key)
        refresh_internet_settings()
    except OSError as e:
        print(">> 设置失败: %s" % e)

    time_sleep()
    enabled, actual_url = get_pac_state()
    report([
        ("PAC 代理", "已启用" if enabled else "未启用", "已启用"),
        ("代理链接", actual_url, url),
    ])


def apply_pac_off():
    print(">> 正在关闭 PAC 代理 ...")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "AutoConfigURL")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        refresh_internet_settings()
    except OSError as e:
        print(">> 关闭失败: %s" % e)

    time_sleep()
    enabled, _url = get_pac_state()
    report([
        ("PAC 代理", "已启用" if enabled else "已关闭", "已关闭"),
    ])


def time_sleep():
    import time
    time.sleep(2)  # 等待系统应用网络配置


# ---------------------------------------------------------------- 交互 UI --

def show_info(service):
    ip, prefix, gw, origin = get_ipv4_info(service)
    dns = get_dns(service)
    suffix = get_search_domains(service)
    enabled, url = get_pac_state()
    print("=" * 50)
    print("【%s】当前配置：" % service)
    print("  地址来源: %s" % (origin or "（空）"))
    print("  IP 地址: %s" % (ip or "（空）"))
    print("  前缀长度: /%s" % (prefix if prefix >= 0 else "（空）"))
    print("  网关: %s" % (gw or "（空）"))
    print("  DNS: %s" % (" ".join(dns) or "（未设置）"))
    print("  搜索域: %s" % (" ".join(suffix) or "（未设置）"))
    print("  PAC代理: %s" % ("已启用 -> %s" % url if enabled else "已关闭"))
    print("=" * 50)


def choose_service():
    adapters = list_adapters()
    if not adapters:
        print(">> 未找到任何网卡，请检查设备管理器")
        sys.exit(1)

    print("可操作的网卡：")
    for i, (name, status, desc) in enumerate(adapters):
        print("  [%d] %-12s (%s) %s" % (i, name, status, desc))

    while True:
        raw = input("请输入网卡序号 (0-%d): " % (len(adapters) - 1)).strip()
        if raw.isdigit() and 0 <= int(raw) < len(adapters):
            return adapters[int(raw)][0]
        print(">> 输入无效，请重新输入")


def prompt_ip(profile):
    raw = input("请输入IP（直接回车使用配置默认 %s）: " % profile["ip"]).strip()
    return raw or profile["ip"]


def main():
    print("=" * 50)
    print(("%s" % APP_NAME).center(46))
    print("=" * 50)

    if not is_admin():
        print(">> 修改网络设置需要管理员权限，正在请求提权（请在 UAC 弹窗中点\"是\"）...")
        run_as_admin()
        return  # 提权后的新进程接管，本进程退出

    config_path = get_config_path()
    profiles = load_config(config_path)
    print(">> 配置文件: %s\n" % config_path)

    service = choose_service()
    show_info(service)

    while True:
        print("\n请选择要应用的配置：")
        print("  1、公司")
        print("  2、家里")
        print("  3、DHCP（自动获取）")
        print("  4、代理 PAC")
        print("  q、退出")
        choice = input("请选择: ").strip().lower()

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
                print(">> 配置文件中 proxy 段缺少 wan/lan 链接，请先补充: %s" % config_path)
                continue
            print("请选择代理链接：")
            print("  1、WAN-PROXY  (%s)" % proxy["wan"])
            print("  2、LAN-PROXY  (%s)" % proxy["lan"])
            print("  3、关闭 PAC 代理")
            sub = input("请选择: ").strip()
            if sub == "1":
                apply_pac(proxy["wan"])
            elif sub == "2":
                apply_pac(proxy["lan"])
            elif sub == "3":
                apply_pac_off()
            else:
                print(">> 输入无效，请输入 1 / 2 / 3")
        elif choice in ("q", "quit", "exit"):
            print("再见！")
            break
        else:
            print(">> 输入无效，请输入 1 / 2 / 3 / 4 / q")


if __name__ == "__main__":
    main()
