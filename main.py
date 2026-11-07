#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SetIP - macOS IP 快速切换工具
# 菜单：1、公司  2、家里  3、DHCP
# 配置文件：config.yaml（首次运行自动生成）

import os
import subprocess
import sys
import time

try:
    import yaml
except ImportError:
    print("缺少依赖 PyYAML，请先执行: pip3 install pyyaml")
    sys.exit(1)

APP_NAME = "IP 管理器 SetIP"

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
            print(">> 未找到配置文件，已自动生成模板: %s" % path)
            return path
        except OSError:
            continue
    print(">> 错误：无法创建配置文件")
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
        print(">> 配置文件 YAML 格式有误，请检查: %s\n%s" % (path, e))
        sys.exit(1)

    profiles = {}
    for key in ("company", "home"):
        item = data.get(key)
        if not isinstance(item, dict):
            print('>> 配置文件缺少 "%s" 配置段，请检查 %s' % (key, path))
            sys.exit(1)
        missing = [k for k in ("ip", "netmask", "gateway", "dns") if not item.get(k)]
        if key == "company" and missing:
            print('>> "%s" 缺少字段: %s，请检查配置文件' % (key, ", ".join(missing)))
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
    """获取网卡（网络服务）列表"""
    out = run_cmd(["networksetup", "-listallnetworkservices"])
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return lines[1:]  # 第一行是标题 "An asterisk (*) denotes ..."


def show_info(service):
    """显示当前网卡信息"""
    print("=" * 50)
    print("【%s】当前配置：" % service)
    print(run_cmd(["networksetup", "-getinfo", service]))
    print("-" * 50)
    print("DNS: %s" % (" ".join(get_dns_list(service)) or "（未设置）"))
    print("搜索域: %s" % (" ".join(get_search_domains(service)) or "（未设置）"))
    enabled, url = get_pac_state(service)
    print("PAC代理: %s%s" % ("已启用 -> %s" % url if enabled else "已关闭",
                             "" if enabled or not url else "（残留链接: %s）" % url))
    print("=" * 50)


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
    return enabled, url


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
        print(">> 存在未生效项！请稍后重试；反复失败请检查是否需要管理员权限")
    print("=" * 50)


def apply_manual(service, ip, netmask, gateway, dns_list, search_domains):
    """设置为手动 IP。search_domains 为空列表时清除搜索域设置。"""
    print(">> 正在设置 IP ...")
    out = run_cmd(["networksetup", "-setmanual", service, ip, netmask, gateway])
    if out:
        print(out)

    print(">> 正在设置 DNS ...")
    out = run_cmd(["networksetup", "-setdnsservers", service] + (dns_list or ["empty"]))
    if out:
        print(out)

    print(">> 正在设置搜索域 ...")
    out = run_cmd(["networksetup", "-setsearchdomains", service] + (search_domains or ["Empty"]))
    if out:
        print(out)

    # 回读校验，展示应用情况
    time.sleep(1)
    info = run_cmd(["networksetup", "-getinfo", service])
    report([
        ("IP 地址", parse_getinfo(info, "IP address"), ip),
        ("子网掩码", parse_getinfo(info, "Subnet mask"), netmask),
        ("网关", parse_getinfo(info, "Router"), gateway),
        ("DNS", " ".join(get_dns_list(service)) or "（已清除）", " ".join(dns_list) if dns_list else "（已清除）"),
        ("搜索域", " ".join(get_search_domains(service)) or "（已清除）", " ".join(search_domains) if search_domains else "（已清除）"),
    ])


def apply_pac(service, url):
    """启用 PAC 自动代理"""
    print(">> 正在设置 PAC 代理: %s" % url)
    out = run_cmd(["networksetup", "-setautoproxyurl", service, url])
    if out:
        print(out)

    time.sleep(1)
    enabled, actual_url = get_pac_state(service)
    report([
        ("PAC 代理", "已启用" if enabled else "未启用", "已启用"),
        ("代理链接", actual_url, url),
    ])


def apply_pac_off(service):
    """关闭 PAC 自动代理"""
    print(">> 正在关闭 PAC 代理 ...")
    out = run_cmd(["networksetup", "-setautoproxystate", service, "off"])
    if out:
        print(out)

    time.sleep(1)
    enabled, actual_url = get_pac_state(service)
    report([
        ("PAC 代理", "已启用" if enabled else "已关闭", "已关闭"),
    ])
    if actual_url:
        print("  （代理链接 %s 已保留，但处于关闭状态）" % actual_url)


def apply_dhcp(service):
    """设置为 DHCP 自动获取，并清除 DNS / 搜索域的手动设置"""
    print(">> 正在切换为 DHCP 自动获取 ...")
    out = run_cmd(["networksetup", "-setdhcp", service])
    if out:
        print(out)
    run_cmd(["networksetup", "-setdnsservers", service, "empty"])
    run_cmd(["networksetup", "-setsearchdomains", service, "Empty"])

    # 回读校验，展示应用情况
    time.sleep(1)
    info = run_cmd(["networksetup", "-getinfo", service])
    mode = "DHCP" if "DHCP Configuration" in info else (parse_getinfo(info, "DHCP / Bootp / Manual") or "Manual")
    report([
        ("配置模式", mode, "DHCP"),
        ("DNS", " ".join(get_dns_list(service)) or "（已清除）", "（已清除）"),
        ("搜索域", " ".join(get_search_domains(service)) or "（已清除）", "（已清除）"),
    ])


# ---------------------------------------------------------------- 交互 UI --

def print_config_items():
    print("  ── 修改配置 ──")
    print("  5、修改公司配置")
    print("  6、修改家里配置")
    print("  7、修改 PAC 代理链接")
    print("  8、打开配置文件")


def config_summary(profiles):
    """列出当前配置，方便在选网卡前确认参数"""
    c, h, proxy = profiles["company"], profiles["home"], profiles["proxy"]
    print("当前配置：")
    print("  公司: %s/%s  网关 %s  DNS %s  搜索域 %s" % (
        c["ip"] or "空", c["netmask"] or "空", c["gateway"] or "空",
        " ".join(c["dns"]) or "无", " ".join(c["search_domains"]) or "无"))
    print("  家里: %s/%s  网关 %s  DNS %s  搜索域 %s" % (
        h["ip"] or "空", h["netmask"] or "空", h["gateway"] or "空",
        " ".join(h["dns"]) or "无", " ".join(h["search_domains"]) or "无"))
    print("  PAC:  WAN %s" % (proxy["wan"] or "未配置"))
    print("        LAN %s" % (proxy["lan"] or "未配置"))


def choose_service(profiles):
    """选择网卡。返回 ("run", 网卡名) / ("edit", c/h/p/o) / ("quit", None)"""
    services = list_services()
    if not services:
        print(">> 未找到任何网络服务，请检查系统设置")
        sys.exit(1)

    print("可操作的网卡：")
    for i, name in enumerate(services):
        print("  [%d] %s" % (i, name))
    print("")
    config_summary(profiles)
    print("\n也可以直接在这里改配置：")
    print("  c、修改公司配置    h、修改家里配置")
    print("  p、修改 PAC 链接   o、打开配置文件")

    last = len(services) - 1
    while True:
        raw = input("\n请输入网卡序号 (0-%d)，或 c/h/p/o 改配置，q 退出: " % last).strip().lower()
        if raw.isdigit() and 0 <= int(raw) <= last:
            return "run", services[int(raw)]
        if raw == "c":
            return "edit", "c"
        if raw == "h":
            return "edit", "h"
        if raw == "p":
            return "edit", "p"
        if raw == "o":
            return "edit", "o"
        if raw in ("q", "quit", "exit"):
            return "quit", None
        print(">> 输入无效，请输入网卡序号或 c/h/p/o")


def prompt_ip(profile):
    """公司/家里模式：可临时修改 IP，直接回车使用配置默认值"""
    raw = input("请输入IP（直接回车使用配置默认 %s）: " % profile["ip"]).strip()
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
    while True:
        raw = input("  %-14s [%s]: " % (label, shown)).strip()
        if not raw:
            return list(current) if list_value else current
        if list_value:
            return parse_list(raw)
        if validator and not validator(raw):
            print("  >> 格式不正确，请重新输入")
            continue
        return raw


def edit_profile(profiles, key, label):
    p = profiles[key]
    print("\n修改【%s】配置（回车保持不变，列表中输入 - 表示清空）：" % label)
    ip = ask("IP 地址", p["ip"], valid_ip)
    netmask = ask("子网掩码", p["netmask"], valid_netmask)
    gateway = ask("网关", p["gateway"], valid_ip)
    dns = ask("DNS", p["dns"], list_value=True)
    domains = ask("搜索域", p["search_domains"], list_value=True)
    profiles[key] = {"ip": ip, "netmask": netmask, "gateway": gateway,
                     "dns": dns, "search_domains": domains}


def edit_proxy(profiles):
    p = profiles["proxy"]
    print("\n修改 PAC 代理链接（回车保持不变）：")
    wan = ask("WAN-PROXY", p["wan"], valid_url)
    lan = ask("LAN-PROXY", p["lan"], valid_url)
    profiles["proxy"] = {"wan": wan, "lan": lan}


def open_config_in_editor(path):
    """用系统默认文本编辑器打开配置文件"""
    print(">> 正在用文本编辑器打开: %s" % path)
    subprocess.run(["open", "-t", path])
    input("修改并保存后，按回车键重新加载配置...")


def commit_config(config_path, profiles):
    """保存配置并重新加载，返回 (config_path, profiles)"""
    saved = save_config(config_path, profiles)
    if not saved:
        print(">> 保存失败：配置文件和 ~/.setip 都不可写，请检查 app 所在位置权限")
        return config_path, profiles
    config_path = saved
    profiles = load_config(config_path)
    print(">> 已保存并生效: %s" % config_path)
    print("   公司: %s/%s  网关 %s  DNS %s" % (
        profiles["company"]["ip"], profiles["company"]["netmask"],
        profiles["company"]["gateway"], " ".join(profiles["company"]["dns"]) or "无"))
    print("   家里: %s/%s  网关 %s  DNS %s" % (
        profiles["home"]["ip"], profiles["home"]["netmask"],
        profiles["home"]["gateway"], " ".join(profiles["home"]["dns"]) or "无"))
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
            print(">> 配置文件有误，已保留内存中的旧配置")
            return config_path, profiles
    return commit_config(config_path, profiles)


def main():
    print("=" * 50)
    print(("%s" % APP_NAME).center(46))
    print("=" * 50)

    config_path = get_config_path()
    profiles = load_config(config_path)
    print(">> 配置文件: %s\n" % config_path)

    # 选网卡界面（同时展示当前配置、可直接改配置）
    service = None
    while service is None:
        action, value = choose_service(profiles)
        if action == "quit":
            print("再见！")
            return
        if action == "edit":
            print("")
            config_path, profiles = handle_edit(value, config_path, profiles)
            print("")
            continue
        service = value

    show_info(service)

    while True:
        print("\n请选择要应用的配置：")
        print("  1、公司")
        print("  2、家里")
        print("  3、DHCP（自动获取）")
        print("  4、代理 PAC")
        print_config_items()
        print("  q、退出")
        choice = input("请选择: ").strip().lower()

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
                print(">> 配置文件中 proxy 段缺少 wan/lan 链接，请先补充: %s" % config_path)
                continue
            print("请选择代理链接：")
            print("  1、WAN-PROXY  (%s)" % proxy["wan"])
            print("  2、LAN-PROXY  (%s)" % proxy["lan"])
            print("  3、关闭 PAC 代理")
            sub = input("请选择: ").strip()
            if sub == "1":
                apply_pac(service, proxy["wan"])
            elif sub == "2":
                apply_pac(service, proxy["lan"])
            elif sub == "3":
                apply_pac_off(service)
            else:
                print(">> 输入无效，请输入 1 / 2 / 3")
        elif choice in ("5", "6", "7", "8"):
            config_path, profiles = handle_edit(choice, config_path, profiles)
        elif choice in ("q", "quit", "exit"):
            print("再见！")
            break
        else:
            print(">> 输入无效，请输入 1-8 / q")


if __name__ == "__main__":
    main()
