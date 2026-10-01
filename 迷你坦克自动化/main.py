# ============================================
# 主入口
# ============================================
import json
import logging
import os

from config.loader import load_config
from core.device import DeviceManager
from core.flow_runner import FlowRunner
from core.actions import UserExit


logging.getLogger("airtest").setLevel(logging.INFO)
logging.getLogger("airtest.core.android.adb").setLevel(logging.WARNING)


# 坐标缓存文件路径（与 core/actions.py 中 COORD_CACHE_FILE 保持一致）
COORD_CACHE_FILE = "data/coord_cache.json"


def clear_coord_cache(path: str = COORD_CACHE_FILE):
    """启动时清空坐标缓存：存在则写空 dict，不存在则创建空 dict"""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        print(f"🧹 已清空坐标缓存: {path}")
    except Exception as e:
        print(f"⚠️ 清空坐标缓存失败 {path}: {e}")


def main():
    config = load_config("config/config.yaml")

    # 启动时清空坐标缓存
    clear_coord_cache()

    dm = DeviceManager()
    if not dm.connect(config["device"]["uri"]):
        print("❌ 设备连接失败，程序退出")
        return

    try:
        FlowRunner(dm, config).run()
    except UserExit as e:
        print(f"\n🛑 用户选择退出: {e}")
    finally:
        dm.disconnect()


if __name__ == "__main__":
    main()