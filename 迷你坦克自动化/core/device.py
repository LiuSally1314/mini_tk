# ============================================
# 设备管理模块 - 处理 Android 设备连接和基本操作
# ============================================

from airtest.core.api import *
import time
from typing import Optional, Tuple


class DeviceManager:
    """Android 设备管理器"""

    def __init__(self):
        self.device = None
        self._connected = False

    def connect(self, uri: str = "Android:///") -> bool:
        try:
            self.device = connect_device(uri)
            self._connected = True
            print("✅ 设备连接成功")
            return True
        except Exception as e:
            print(f"❌ 设备连接失败: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected and self.device is not None

    def disconnect(self):
        if self.device:
            try:
                self.device.disconnect()
            except Exception:
                pass
        self._connected = False
        print("📱 设备已断开连接")

    def touch(self, coords: Tuple[float, float], duration: float = 0.1) -> bool:
        if not self.is_connected():
            print("❌ 设备未连接，无法执行点击")
            return False
        try:
            print(f"  👆 点击坐标: ({coords[0]:.1f}, {coords[1]:.1f})")
            touch(coords, duration=duration)
            return True
        except Exception as e:
            print(f"❌ 点击失败: {e}")
            return False

    def double_click(self, coords: Tuple[float, float]) -> bool:
        if not self.is_connected():
            print("❌ 设备未连接，无法执行双击")
            return False
        try:
            print(f"  👆👆 双击坐标: ({coords[0]:.1f}, {coords[1]:.1f})")
            double_click(coords)
            return True
        except Exception as e:
            print(f"❌ 双击失败: {e}")
            return False

    def swipe(self, start: Tuple[float, float], end: Tuple[float, float],
              duration: float = 1.0) -> bool:
        if not self.is_connected():
            print("❌ 设备未连接，无法执行滑动")
            return False
        try:
            print(f"  👆➡️ 滑动: ({start[0]:.1f}, {start[1]:.1f}) -> "
                  f"({end[0]:.1f}, {end[1]:.1f})")
            swipe(start, end, duration=duration)
            return True
        except Exception as e:
            print(f"❌ 滑动失败: {e}")
            return False

    def input_text(self, text_str: str, enter: bool = True) -> bool:
        if not self.is_connected():
            print("❌ 设备未连接，无法输入文本")
            return False
        try:
            airtest = __import__('airtest.core.api', fromlist=['text'])
            airtest.text(text_str, enter=enter)
            print(f"  ⌨️ 输入文本: {text_str}")
            return True
        except Exception as e:
            print(f"❌ 输入文本失败: {e}")
            return False

    def adb_shell(self, command: list) -> str:
        if not self.is_connected():
            print("❌ 设备未连接，无法执行ADB命令")
            return ""
        try:
            return self.device.adb.shell(command)
        except Exception as e:
            print(f"❌ ADB命令执行失败: {e}")
            return ""

    def adb_pull(self, remote_path: str, local_path: str) -> bool:
        if not self.is_connected():
            print("❌ 设备未连接，无法拉取文件")
            return False
        try:
            self.device.adb.pull(remote_path, local_path)
            return True
        except Exception as e:
            print(f"❌ 拉取文件失败: {e}")
            return False

    def adb_push(self, local_path: str, remote_path: str) -> bool:
        if not self.is_connected():
            print("❌ 设备未连接，无法推送文件")
            return False
        try:
            self.device.adb.push(local_path, remote_path)
            return True
        except Exception as e:
            print(f"❌ 推送文件失败: {e}")
            return False

    def snapshot(self, filename: str = None) -> Optional[str]:
        if not self.is_connected():
            print("❌ 设备未连接，无法截屏")
            return None
        try:
            if filename:
                snapshot(filename)
                return filename
            else:
                return snapshot()
        except Exception as e:
            print(f"❌ 截屏失败: {e}")
            return None