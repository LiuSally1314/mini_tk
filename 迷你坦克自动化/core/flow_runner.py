# ============================================
# 流程执行模块 - 通用执行器，解释配置里的步骤
# ============================================

from core.device import DeviceManager
from core.ocr_finder import OcrFinder
from core.actions import ActionRunner


class FlowRunner:
    """按配置执行任意流程"""

    def __init__(self, device_manager: DeviceManager, config: dict):
        self.dm = device_manager
        self.config = config
        self.defaults = config.get("defaults", {})
        self.finder = OcrFinder(base_dir=config["output"]["base_dir"])
        self.runner = ActionRunner(self.dm, self.finder, self.defaults)

        self.runner._flows = config.get("flows", {})

    def run(self):
        flow_name = self.config["active_flow"]
        flow = self.config["flows"].get(flow_name)
        if not flow:
            print(f"❌ 未找到流程配置: {flow_name}")
            print(f"   可用流程: {list(self.config['flows'].keys())}")
            return

        loop = flow.get("loop_count", 1)
        steps = flow.get("steps", [])

        print(f"🚀 开始执行流程「{flow_name}」，共 {loop} 次循环")
        for n in range(1, loop + 1):
            print(f"\n===== 「{flow_name}」第 {n}/{loop} 次循环 =====")
            for idx, step in enumerate(steps, 1):
                print(f"  ▶ 步骤 {idx}: {step['action']}")
                ok = self.runner.run_step(step)
                if not ok:
                    print(f"  ⏭ 步骤 {idx} 未成功，跳过本循环剩余步骤")
                    break

        print(f"\n🎉 流程「{flow_name}」执行完毕")