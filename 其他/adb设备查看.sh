#!/bin/bash
# ============================================================
# 文件名: device_info.sh
# 用途: 查看指定 Android 设备(模拟器)的详细信息
# 用法: ./device_info.sh [serial]
#       默认 serial = emulator-5554
# ============================================================

set -euo pipefail

# ---------- 配置 ----------
SERIAL="${1:-emulator-5554}"
ADB="${ADB:-adb}"

# ---------- 颜色 ----------
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

# ---------- 工具函数 ----------
print_title() {
    echo -e "\n${CYAN}========== $1 ==========${NC}"
}

print_kv() {
    printf "  ${GREEN}%-22s${NC}: %s\n" "$1" "$2"
}

# 执行 adb 命令的封装(带 -s)
adb_s() {
    "$ADB" -s "$SERIAL" "$@"
}

# 获取属性,属性不存在返回 unknown
getprop() {
    local v
    v=$(adb_s shell getprop "$1" 2>/dev/null | tr -d '\r\n')
    echo "${v:-unknown}"
}

# ---------- 前置检查 ----------
if ! command -v "$ADB" >/dev/null 2>&1; then
    echo -e "${RED}错误: 找不到 adb 命令,请先安装 Android SDK Platform Tools 并加入 PATH${NC}"
    exit 1
fi

print_title "ADB 设备列表"
"$ADB" devices -l

if ! "$ADB" devices | awk 'NR>1 && $1=="'"$SERIAL"'"' | grep -q "device$"; then
    echo -e "${RED}错误: 设备 '$SERIAL' 未连接或状态不是 device${NC}"
    echo -e "${YELLOW}提示: 可用设备如下${NC}"
    "$ADB" devices -l
    exit 1
fi

echo -e "\n${GREEN}>>> 正在读取设备: $SERIAL${NC}"

# ---------- 1. 基本设备信息 ----------
print_title "1. 设备基本信息"
print_kv "ADB Serial"        "$SERIAL"
print_kv "厂商 (brand)"      "$(getprop ro.product.brand)"
print_kv "型号 (model)"      "$(getprop ro.product.model)"
print_kv "设备名 (device)"   "$(getprop ro.product.device)"
print_kv "产品名 (name)"     "$(getprop ro.product.name)"
print_kv "序列号 (serialno)" "$(getprop ro.serialno)"
print_kv "Android ID"        "$(adb_s shell settings get secure android_id 2>/dev/null | tr -d '\r\n')"

# ---------- 2. 系统版本信息 ----------
print_title "2. 系统版本"
print_kv "Android 版本"      "$(getprop ro.build.version.release)"
print_kv "API 级别 (SDK)"    "$(getprop ro.build.version.sdk)"
print_kv "安全补丁"          "$(getprop ro.build.version.security_patch)"
print_kv "Build ID"          "$(getprop ro.build.id)"
print_kv "Build 类型"        "$(getprop ro.build.type)"
print_kv "Build 标签"        "$(getprop ro.build.tags)"
print_kv "Fingerprint"       "$(getprop ro.build.fingerprint)"

# ---------- 3. CPU / 架构 ----------
print_title "3. CPU 与架构"
print_kv "主 ABI"            "$(getprop ro.product.cpu.abi)"
print_kv "ABI 列表"          "$(getprop ro.product.cpu.abilist)"
print_kv "CPU 核心数"        "$(adb_s shell cat /proc/cpuinfo 2>/dev/null | grep -c processor)"

# ---------- 4. 屏幕信息 ----------
print_title "4. 屏幕信息"
WM_SIZE=$(adb_s shell wm size 2>/dev/null | tr -d '\r')
WM_DENSITY=$(adb_s shell wm density 2>/dev/null | tr -d '\r')
print_kv "分辨率"            "${WM_SIZE:-unknown}"
print_kv "屏幕密度"          "${WM_DENSITY:-unknown}"

# ---------- 5. 内存信息 ----------
print_title "5. 内存信息"
MEM_TOTAL=$(adb_s shell cat /proc/meminfo 2>/dev/null | awk '/MemTotal/ {printf "%.2f GB", $2/1024/1024}')
MEM_FREE=$(adb_s shell cat /proc/meminfo 2>/dev/null | awk '/MemAvailable/ {printf "%.2f GB", $2/1024/1024}')
print_kv "总内存"            "${MEM_TOTAL:-unknown}"
print_kv "可用内存"          "${MEM_FREE:-unknown}"

# ---------- 6. 电池信息 ----------
print_title "6. 电池信息"
BATTERY=$(adb_s shell dumpsys battery 2>/dev/null | tr -d '\r')
print_kv "电量"              "$(echo "$BATTERY" | awk -F': ' '/ level:/ {print $2"%"}')"
print_kv "状态"              "$(echo "$BATTERY" | awk -F': ' '/ status:/ {print $2}')"
print_kv "健康度"            "$(echo "$BATTERY" | awk -F': ' '/ health:/ {print $2}')"
print_kv "温度"              "$(echo "$BATTERY" | awk -F': ' '/ temperature:/ {print $2/10" °C"}')"
print_kv "充电方式"          "$(echo "$BATTERY" | awk -F': ' '/ powered:/ {print $2}')"

# ---------- 7. 存储信息 ----------
print_title "7. 存储信息"
STORAGE=$(adb_s shell df /data 2>/dev/null | tr -d '\r')
echo "$STORAGE" | awk 'NR==1 {printf "  %-10s %-10s %-10s %-10s %-6s\n", "Filesystem","Size","Used","Avail","Use%"}
                       NR==2 {printf "  %-10s %-10s %-10s %-10s %-6s\n", $1,$2,$3,$4,$5}'

# ---------- 8. 网络信息 ----------
print_title "8. 网络信息"
IP_ADDR=$(adb_s shell ip addr show wlan0 2>/dev/null | awk '/inet / {print $2}' | cut -d/ -f1 | tr -d '\r')
print_kv "WLAN IP"           "${IP_ADDR:-未连接}"
print_kv "WiFi 状态"         "$(adb_s shell settings get global wifi_on 2>/dev/null | tr -d '\r')"

# ---------- 9. 已安装应用数量 ----------
print_title "9. 应用统计"
PKG_COUNT=$(adb_s shell pm list packages 2>/dev/null | wc -l | tr -d ' ')
PKG3_COUNT=$(adb_s shell pm list packages -3 2>/dev/null | wc -l | tr -d ' ')
print_kv "应用总数"          "$PKG_COUNT"
print_kv "第三方应用数"      "$PKG3_COUNT"

# ---------- 10. 当前前台 Activity ----------
print_title "10. 当前前台 Activity"
FOREGROUND=$(adb_s shell dumpsys activity activities 2>/dev/null \
    | grep -m1 "mResumedActivity" \
    | sed 's/.*mResumedActivity: //' | tr -d '\r')
print_kv "前台"              "${FOREGROUND:-unknown}"

# ---------- 结束 ----------
echo -e "\n${GREEN}>>> 信息读取完成${NC}"