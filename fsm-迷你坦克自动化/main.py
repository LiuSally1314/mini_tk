import logging
import sys
import yaml
import pkgutil
import importlib

import flows
from flows.base_flow import FlowFactory
from device import DeviceManager


# 设置airtest的日志级别为INFO，这样就不会显示DEBUG信息
logging.getLogger("airtest").setLevel(logging.INFO)
logging.getLogger("airtest.core.android.adb").setLevel(logging.WARNING)

def load_all_flows():
    """动态扫描加载 flows 目录下的所有模块，完成自动注册"""
    for _, module_name, _ in pkgutil.iter_modules(flows.__path__):
        importlib.import_module(f"flows.{module_name}")


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "main_config.yaml"

    # 1. 加载主配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    active_flow_name = cfg.get("active_flow", "general_skill_upgrade")
    print(f"📋 当前要执行的流程: [{active_flow_name}]")

    # 2. 初始化公共设备
    device_cfg = cfg.get('device', {})
    device = DeviceManager()
    if not device.connect(device_cfg.get('uri', 'Android:///')):
        raise RuntimeError("❌ 设备连接失败，程序终止")

    # 3. 动态加载注册所有流程
    load_all_flows()

    # 4. 根据工厂模式生成并执行目标流程
    flow_instance = None
    try:
        flow_instance = FlowFactory.create(active_flow_name, cfg, device)
        flow_instance.run()
    except Exception as e:
        print(f"❌ 流程执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 5. 流程资源回收与设备断开
        if flow_instance:
            flow_instance.teardown()
        device.disconnect()
        print("👋 程序执行完毕，设备已断开。")


if __name__ == '__main__':
    main()