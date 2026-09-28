# ============================================
# 设备管理模块 - 处理Android设备连接和基本操作
# ============================================

import os
import time
import tempfile
from typing import Optional, Tuple

from airtest.core.api import (
    connect_device,
    touch,
    double_click,
    swipe,
    text as airtest_text,
    snapshot as airtest_snapshot,
    G,
)


class DeviceManager:
    """Android设备管理器"""

    def __init__(self):
        self.device = None
        self._connected = False

    # ---------------- 连接 ----------------
    def connect(self, uri: str = "Android:///") -> bool:
        try:
            self.device = connect_device(uri)
            # 确保全局 G.DEVICE 指向该设备（部分版本 connect_device 不会自动设置）
            G.DEVICE = self.device
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

    # ---------------- 截图（返回 numpy，不落盘） ----------------
    def capture(self, settle: float = 0.0):
        """
        实时截图，返回 numpy 图像数组（BGR），不落盘。

        Args:
            settle: 截图前等待秒数（等界面稳定）

        Returns:
            numpy.ndarray；失败返回 None
        """
        if not self.is_connected():
            print("❌ 设备未连接，无法截屏")
            return None

        if settle > 0:
            time.sleep(settle)

        # 优先：G.DEVICE.snapshot() 返回 numpy
        try:
            img = self.device.snapshot()
            if img is not None and hasattr(img, "shape"):
                print(f"  📷 截图成功 (device.snapshot) shape={img.shape}")
                return img
            # 若返回的是路径字符串，读回
            if isinstance(img, str) and os.path.exists(img):
                import cv2
                arr = cv2.imread(img)
                print(f"  📷 截图成功 (路径读回) shape={getattr(arr, 'shape', 'N/A')}")
                return arr
        except Exception as e:
            print(f"  ⚠️ device.snapshot() 失败: {e}，尝试 tempfile 兜底")

        # 兜底：写临时文件再读回 numpy
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.close(tmp_fd)
            airtest_snapshot(filename=tmp_path)
            import cv2
            arr = cv2.imread(tmp_path)
            if arr is None:
                print("❌ 截屏兜底失败：cv2.imread 返回 None")
                return None
            print(f"  📷 截图成功 (tempfile 兜底) shape={arr.shape}")
            return arr
        except Exception as e:
            import traceback
            print(f"❌ 截屏失败: {e}")
            traceback.print_exc()
            return None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    # ---------------- 基础操作 ----------------
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
            airtest_text(text_str, enter=enter)
            print(f"  ⌨️ 输入文本: {text_str}")
            return True
        except Exception as e:
            print(f"❌ 输入文本失败: {e}")
            return False

    # ---------------- ADB ----------------
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

        touch