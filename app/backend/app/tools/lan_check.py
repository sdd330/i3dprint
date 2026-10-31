# Violet Print — 局域网连通性自检
#
# 用法（backend/ 目录下，服务已启动时）：
#   .venv/bin/python -m app.tools.lan_check
#
# 它会逐项检查：网卡地址 / 监听状态 / macOS 防火墙 / 本机到各地址的 HTTP 可达性，
# 并把「手机/其他设备打不开」最常见的客户端原因列成清单。

from __future__ import annotations

import ipaddress
import json
import platform
import socket
import subprocess
import sys
import urllib.request

from ..core.config import settings


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=8).stdout.strip()
    except Exception:
        return ""


def interfaces() -> list[dict]:
    """解析 ifconfig，列出非回环 IPv4/IPv6 地址与网卡（macOS/Linux 通用近似实现）。"""
    out, cur = [], ""
    for line in sh(["ifconfig"]).splitlines():
        if line and not line.startswith((" ", "\t")):
            cur = line.split(":")[0]
        elif "inet " in line and "127.0.0.1" not in line:
            addr = line.split("inet ")[1].split()[0]
            out.append({"iface": cur, "family": 4, "addr": addr})
        elif "inet6 " in line and "fe80" not in line and "::1" not in line:
            addr = line.split("inet6 ")[1].split()[0].split("%")[0]
            out.append({"iface": cur, "family": 6, "addr": addr})
    return out


def default_iface() -> str:
    route = sh(["route", "-n", "get", "default"])
    for line in route.splitlines():
        if "interface:" in line:
            return line.split(":", 1)[1].strip()
    return ""


def firewall() -> dict:
    if platform.system() != "Darwin":
        return {"platform": platform.system(), "checked": False}
    state = sh(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"])
    blockall = sh(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getblockall"])
    return {
        "checked": True,
        "enabled": "enabled" in state.lower() and "disabled" not in state.lower(),
        "state": state,
        "block_all": "block all" in blockall.lower() and "disabled" not in blockall.lower(),
    }


def listening(port: int) -> list[str]:
    rows = sh(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])
    return [ln for ln in rows.splitlines()[1:] if ln.strip()]


def http_probe(url: str) -> bool:
    # 局域网探测必须绕开 http_proxy：否则会把 192.168.x.x 也丢给代理，误报"失败"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url + "/api/health", timeout=3) as r:
            body = json.loads(r.read().decode())
            return bool(body.get("ok"))
    except Exception:
        return False


def main() -> int:
    port = settings.port
    print(f"Violet Print 局域网自检  ·  平台={platform.system()}  端口={port}")
    import os
    proxy = {k: v for k, v in os.environ.items() if k.lower() in
             ("http_proxy", "https_proxy", "all_proxy") and v}
    if proxy:
        print(f"提示：当前 shell 设置了代理 {proxy}，本工具已自动绕开；"
              f"但请确认服务器进程本身不需要走代理访问本机 LM Studio")
    print("-" * 66)

    ifaces = interfaces()
    primary = default_iface()
    print(f"默认出口网卡：{primary or '未识别'}")
    for i in ifaces:
        tag = "  ← 主网卡" if i["iface"] == primary else ""
        fam = "IPv4" if i["family"] == 4 else "IPv6"
        print(f"  {i['iface']:<8} {fam}  {i['addr']}{tag}")
    if not ifaces:
        print("  （没有找到非回环地址：检查 Wi-Fi/网线是否连上）")

    print("-" * 66)
    lis = listening(port)
    if lis:
        print(f"监听状态：端口 {port} 已监听")
        for ln in lis:
            print("  " + " ".join(ln.split()[:9]))
    else:
        print(f"监听状态：端口 {port} 没有监听进程（服务没启动？）")

    fw = firewall()
    if fw.get("checked"):
        print(f"macOS 防火墙：{'开启（可能拦截入站）' if fw['enabled'] else '关闭'}"
              f"{' · BlockAll=开' if fw.get('block_all') else ''}")
        if fw["enabled"]:
            print("  若手机连不上，请：系统设置 → 网络 → 防火墙 → 选项，允许 Python/uvicorn 接受传入连接")
    else:
        print(f"防火墙：{fw.get('platform')} 未做检查（Linux 可用 ufw status 查看）")

    print("-" * 66)
    v4 = [i["addr"] for i in ifaces if i["family"] == 4]
    v6 = [i["addr"] for i in ifaces if i["family"] == 6]
    for addr in v4:
        ok = http_probe(f"http://{addr}:{port}")
        print(f"本机访问 http://{addr}:{port}  →  {'OK' if ok else '失败'}")
    for addr in v6:
        ok = http_probe(f"http://[{addr}]:{port}")
        print(f"本机访问 http://[{addr}]:{port}  →  {'OK' if ok else '失败'}")

    # 主动做一次"局域网内出站"连接：macOS 15+ 会据此弹出「本地网络」授权提示
    gateway = ""
    for line in sh(["route", "-n", "get", "default"]).splitlines():
        if "gateway:" in line:
            gateway = line.split(":", 1)[1].strip()
    if gateway:
        try:
            s_ = socket.create_connection((gateway, 80), timeout=1.5)
            s_.close()
            print(f"局域网出站测试（到网关 {gateway}）：OK")
        except Exception:
            print(f"局域网出站测试（到网关 {gateway}）：连不上（部分路由器不开放 80，可忽略）")
    if platform.system() == "Darwin":
        print("macOS 15+ 注意：入站访问要「本地网络」权限 —— 系统设置 → 隐私与安全性 → 本地网络，")
        print("  把运行本服务的 App（终端 / iTerm / mimo / VS Code）打开；授权后**重启服务**再试。")

    print("-" * 66)
    print("手机/其他设备打不开时，按顺序排查：")
    print("  1. 确认和设备在同一 Wi-Fi（不是访客网络/不同 SSID，也别用 5G 流量）")
    print("  2. 路由器/校园网可能开了「AP 隔离 / 客户端隔离」，设备之间互相不可见：")
    print("     换一台设备 ping 这个地址试试：ping " + (v4[0] if v4 else "<服务器IP>"))
    print("  3. 手机开了 VPN / 私有中继（iOS：设置 → 蜂窝网络 → 限制 IP 地址跟踪），先关掉")
    print("  4. 服务器地址用上面 IPv4 那条；IPv6-only 校园网请用 --host :: 启动（双栈）")
    print("  5. 手机连的是 6GHz/WPA3 独立网段时，确认与服务器同网段（前三段 IP 相同）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
