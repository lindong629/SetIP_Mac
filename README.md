# SetIP_Mac - macOS IP 快速切换工具

双击 `SetIP.app` 即可运行（会自动打开终端窗口）。

## 功能

- 1、公司 —— 按 config.yaml 中 `company` 配置设置静态 IP
- 2、家里 —— 按 config.yaml 中 `home` 配置设置静态 IP
- 3、DHCP —— 自动获取 IP，并清除手动 DNS / 搜索域
- 4、代理 PAC —— 子选项 WAN-PROXY / LAN-PROXY（链接在 config.yaml 的 `proxy` 段）

## 配置文件

程序启动时按以下顺序查找 `config.yaml`：

1. `SetIP.app` 所在目录（推荐：把 config.yaml 和 SetIP.app 放一起）
2. `~/.setip/config.yaml`（首次运行会自动生成模板）

模板格式：

```yaml
company:
  ip: 10.91.140.5
  netmask: 255.255.254.0
  gateway: 10.91.140.1
  dns:
    - 10.91.140.1
  search_domains: []      # 可留空

home:
  ip: 192.168.168.3
  netmask: 255.255.255.0
  gateway: 192.168.168.1
  dns:
    - 114.114.114.114
    - 8.8.8.8
  search_domains: []

proxy:                  # PAC 自动代理链接（WAN / LAN 地址不同）
  wan: https://www.wlgo.cc/st/go.js
  lan: https://www.wlgo.cc/st/golan.js
```

## 修改配置后重新打包 App（仅开发时需要）

```shell
python3 -m venv .build-venv
.build-venv/bin/pip install pyyaml pyinstaller
.build-venv/bin/pyinstaller --onefile --name SetIP --icon icon.icns --clean -y main.py
# dist/SetIP 即为可执行文件，再按 SetIP.app 内部结构打包（见仓库内 SetIP.app）
```

## 注意

- 修改网络设置需要管理员权限；若提示权限不足，在弹出的终端里用 `sudo` 运行程序内的可执行文件。
- 旧版 `IPSet.sh` 与 click 依赖已不再需要。
