# ============================================
# 主入口
# ============================================
import logging

from config.loader import load_config
from core.device import DeviceManager
from core.flow_runner import FlowRunner
from core.actions import UserExit


logging.getLogger("airtest").setLevel(logging.INFO)
logging.getLogger("airtest.core.android.adb").setLevel(logging.WARNING)


def main():
    config = load_config("config/config.yaml")

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