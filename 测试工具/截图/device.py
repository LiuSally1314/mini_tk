# ============================================
# 设备管理模块 - 处理Android设备连接和基本操作
# ============================================

from airtest.core.api import *
import time
from typing import Optional, Tuple, Any


class DeviceManager:
    """Android设备管理器"""

    def __init__(self):
        """初始化设备管理器"""
        self.device = None
        self._connected = False

    def connect(self, uri: str = "Android:///") -> bool:
        """
        连接Android设备

        Args:
            uri: 设备连接URI

        Returns:
            是否连接成功
        """
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
        """检查设备是否已连接"""
        return self._connected and self.device is not None

    def disconnect(self):
        """断开设备连接"""
        if self.device:
            try:
                self.device.disconnect()
            except:
                pass
        self._connected = False
        print("📱 设备已断开连接")

    def touch(self, coords: Tuple[float, float], duration: float = 0.1) -> bool:
        """
        点击指定坐标

        Args:
            coords: (x, y)坐标
            duration: 点击持续时间

        Returns:
            是否成功
        """
        if not self.is_connected():
            print("❌ 设备未连接，无法执行点击")
            return False
        try:
            # 输出点击坐标
            print(f"  👆 点击坐标: ({coords[0]:.1f}, {coords[1]:.1f})")
            touch(coords, duration=duration)
            return True
        except Exception as e:
            print(f"❌ 点击失败: {e}")
            return False

    def double_click(self, coords: Tuple[float, float]) -> bool:
        """
        双击指定坐标

        Args:
            coords: (x, y)坐标

        Returns:
            是否成功
        """
        if not self.is_connected():
            print("❌ 设备未连接，无法执行双击")
            return False
        try:
            # 输出双击坐标
            print(f"  👆👆 双击坐标: ({coords[0]:.1f}, {coords[1]:.1f})")
            double_click(coords)
            return True
        except Exception as e:
            print(f"❌ 双击失败: {e}")
            return False

    def swipe(self, start: Tuple[float, float], end: Tuple[float, float],
              duration: float = 1.0) -> bool:
        """
        滑动屏幕

        Args:
            start: 起点坐标 (x, y)
            end: 终点坐标 (x, y)
            duration: 滑动持续时间

        Returns:
            是否成功
        """
        if not self.is_connected():
            print("❌ 设备未连接，无法执行滑动")
            return False
        try:
            # 输出滑动坐标
            print(f"  👆➡️ 滑动: ({start[0]:.1f}, {start[1]:.1f}) -> ({end[0]:.1f}, {end[1]:.1f})")
            swipe(start, end, duration=duration)
            return True
        except Exception as e:
            print(f"❌ 滑动失败: {e}")
            return False

    def input_text(self, text_str: str, enter: bool = True) -> bool:
        """
        输入文本

        Args:
            text_str: 要输入的文本
            enter: 是否自动回车

        Returns:
            是否成功
        """
        if not self.is_connected():
            print("❌ 设备未连接，无法输入文本")
            return False
        try:
            # 使用 __import__ 动态导入避免命名冲突
            airtest = __import__('airtest.core.api', fromlist=['text'])
            airtest.text(text_str, enter=enter)
            print(f"  ⌨️ 输入文本: {text_str}")
            return True
        except Exception as e:
            print(f"❌ 输入文本失败: {e}")
            return False

    def adb_shell(self, command: list) -> str:
        """
        执行ADB命令

        Args:
            command: ADB命令列表

        Returns:
            命令输出结果
        """
        if not self.is_connected():
            print("❌ 设备未连接，无法执行ADB命令")
            return ""
        try:
            return self.device.adb.shell(command)
        except Exception as e:
            print(f"❌ ADB命令执行失败: {e}")
            return ""

    def adb_pull(self, remote_path: str, local_path: str) -> bool:
        """
        从设备拉取文件

        Args:
            remote_path: 设备上的文件路径
            local_path: 本地保存路径

        Returns:
            是否成功
        """
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
        """
        推送文件到设备

        Args:
            local_path: 本地文件路径
            remote_path: 设备上的目标路径

        Returns:
            是否成功
        """
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
        """
        截取屏幕

        Args:
            filename: 保存的文件名，None则返回图像数据

        Returns:
            文件路径或图像数据
        """
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