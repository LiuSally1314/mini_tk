#!/bin/bash
# ============================================================
# 文件名: adb设备查看2.sh  (修正版 v2)
# 用途: 自动识别 ADB 设备: 真机 / 标准AVD / 云手机-投屏
# 兼容 macOS 自带 Bash 3.2
# ============================================================

set -uo pipefail

ADB="${ADB:-adb}"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[0;33m'
RED='\033[0;31m';   BLUE='\033[0;34m'; NC='\033[0m'

print_title() {
    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}============================================================${NC}"
}
print_kv() {
    printf "  ${GREEN}%-24s${NC}: %s\n" "$1" "$2"
}

if ! command -v "$ADB" >/dev/null 2>&1; then
    echo -e "${RED}错误: 找不到 adb 命令${NC}"; exit 1
fi

# ---------- 获取设备 ----------
DEVICES=()
while IFS= read -r line; do
    [ -n "$line" ] && DEVICES+=("$line")
done < <("$ADB" devices | awk 'NR>1 && $2=="device" {print $1}')

if [ ${#DEVICES[@]} -eq 0 ]; then
    echo -e "${RED}没有检测到任何在线设备${NC}"; exit 1
fi
echo -e "${BLUE}发现 ${#DEVICES[@]} 个在线设备${NC}"

# ---------- 读取单个属性 ----------
gp() {
    "$ADB" -s "$1" shell getprop "$2" 2>/dev/null | tr -d '\r\n'
}

# ---------- 识别单个设备 ----------
detect_one() {
    local serial="$1"

    local brand model device name serialno abi
    local fingerprint manufacturer qemu
    local miui_ver miui_code

    brand=$(gp "$serial" ro.product.brand)
    model=$(gp "$serial" ro.product.model)
    device=$(gp "$serial" ro.product.device)
    name=$(gp "$serial" ro.product.name)
    serialno=$(gp "$serial" ro.serialno)
    abi=$(gp "$serial" ro.product.cpu.abi)
    fingerprint=$(gp "$serial" ro.build.fingerprint)
    manufacturer=$(gp "$serial" ro.product.manufacturer)
    qemu=$(gp "$serial" ro.kernel.qemu)
    miui_ver=$(gp "$serial" ro.miui.ui.version.name)
    miui_code=$(gp "$serial" ro.miui.ui.version.code)

    # ---------- 判定逻辑 ----------
    local type="未知"
    local reason=""

    # ============ 关键判定规则 ============

    # A. 标准 AVD: serial 是 emulator-* 且 ro.kernel.qemu=1
    #    (真正的 AVD 一定有 qemu 标记)
    if [[ "$serial" == emulator-* ]] && [ "$qemu" = "1" ]; then
        type="标准 Android 模拟器 (AVD)"
        reason="serial=emulator-*, ro.kernel.qemu=1"

    # B. 云手机/投屏: serial 是 emulator-* 但 qemu != 1
    #    并且 abi 是 arm64 (真机架构), 或 brand 与 manufacturer 异常
    elif [[ "$serial" == emulator-* ]] && [ "$qemu" != "1" ]; then
        type="云手机 / 投屏 (伪装成 emulator)"
        reason="serial=emulator-* 但 ro.kernel.qemu='${qemu:-空}', abi=$abi"

    # C. mDNS 无线调试的真机: serial 形如 adb-xxx._adb-tls-connect._tcp.
    elif [[ "$serial" == adb-*._adb-tls-connect._tcp.* ]]; then
        # 进一步区分: 有 MIUI 就是小米真机
        if [ -n "$miui_ver" ]; then
            type="小米真机 (无线调试)"
            reason="mDNS 连接, MIUI $miui_ver"
        else
            type="真机 (无线调试)"
            reason="mDNS 连接, brand=$brand"
        fi

    # D. 序列号是 EMULATOR 开头 -> 标准模拟器
    elif [[ "$serialno" == EMULATOR* ]]; then
        type="标准 Android 模拟器"
        reason="serialno=$serialno"

    # E. x86 架构 -> 多半是模拟器
    elif [[ "$abi" == x86* ]]; then
        type="模拟器 (x86 架构)"
        reason="abi=$abi"

    # F. MIUI 真机 (USB)
    elif [ -n "$miui_ver" ]; then
        type="小米真机 (USB)"
        reason="MIUI $miui_ver"

    # G. 普通真机
    elif [ -n "$brand" ] && [ "$brand" != "unknown" ]; then
        type="真机"
        reason="brand=$brand, manufacturer=$manufacturer"

    else
        type="未知"
        reason="无法匹配任何规则"
    fi

    # ---------- 输出 ----------
    echo ""
    echo -e "${YELLOW}>>> 设备: $serial${NC}"
    print_kv "类型"           "$type"
    print_kv "判定依据"       "$reason"
    echo "  ---"
    print_kv "brand"          "${brand:-unknown}"
    print_kv "manufacturer"   "${manufacturer:-unknown}"
    print_kv "model"          "${model:-unknown}"
    print_kv "device"         "${device:-unknown}"
    print_kv "product.name"   "${name:-unknown}"
    print_kv "serialno"       "${serialno:-unknown}"
    print_kv "abi"            "${abi:-unknown}"
    print_kv "ro.kernel.qemu" "${qemu:-空}"
    print_kv "MIUI"           "${miui_ver:-N/A} (${miui_code:-N/A})"
    print_kv "fingerprint"    "${fingerprint:-unknown}"
}

# ---------- 主流程 ----------
print_title "ADB 设备类型识别"

for d in "${DEVICES[@]}"; do
    detect_one "$d"
done

print_title "识别完成"