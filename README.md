# SetIP_Mac - macOS IP 快速切换工具

双击 `SetIP.app` 即可运行（会自动打开终端窗口）。

> Windows 版在 [`windows/`](windows/) 目录，功能与菜单完全一致（含设置菜单、配置内置），见 [windows/README.md](windows/README.md)。

## 功能

- 1、公司 —— 按配置中的 `company` 段设置静态 IP
- 2、家里 —— 按配置中的 `home` 段设置静态 IP
- 3、DHCP —— 自动获取 IP，并清除手动 DNS / 搜索域
- 4、代理 PAC —— 子选项 WAN-PROXY / LAN-PROXY / 关闭代理
- 5、修改公司配置 / 6、修改家里配置 / 7、修改 PAC 代理链接 / 8、打开配置文件 —— 都在主菜单，直接改，保存即生效

每次设置后都会回读系统实际配置并逐项对比显示 ✓ / ✗（应用情况）。

选网卡的那个界面也会列出当前配置（公司 / 家里 / PAC 链接），并可直接在那里改：

```
可操作的网卡：
  [0] USB 10/100/1000 LAN
  [1] Wi-Fi

当前配置：
  公司: 10.91.140.5/255.255.254.0  网关 10.91.140.1  DNS 10.91.140.1  搜索域 无
  家里: 192.168.168.3/255.255.255.0  网关 192.168.168.1  DNS 114.114.114.114 8.8.8.8  搜索域 无
  PAC:  WAN https://.../go.js
        LAN https://.../golan.js

也可以直接在这里改配置：
  c、修改公司配置    h、修改家里配置
  p、修改 PAC 链接   o、打开配置文件

请输入网卡序号 (0-1)，或 c/h/p/o 改配置，q 退出：
```

改完自动保存并回到这个界面，配置立即生效。

## 配置文件

配置文件**打包在 app 内部**：`SetIP.app/Contents/Resources/config.yaml`

- 优先使用包内配置（配置跟着 app 走，复制/移动 app 不会丢配置）
- 包内不可写时自动回退到 `~/.setip/config.yaml`
- 修改方式：程序里选 `5、设置`，或用文本编辑器打开配置文件（设置菜单第 4 项）

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
