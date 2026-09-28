import time
import yaml
from abc import ABC, abstractmethod
from transitions import Machine
from device import DeviceManager


class BaseFlow(ABC):
    """所有流程的抽象基类"""

    def __init__(self, cfg: dict, device: DeviceManager):
        self.cfg = cfg
        self.device = device
        self.debug = cfg.get('debug', False)
        self.timings = cfg.get('timings', {})

    @abstractmethod
    def run(self):
        """主执行循环，子类必须实现"""
        pass

    def teardown(self):
        """流程结束后的清理工作"""
        pass


class YAMLStateMachineFlow(BaseFlow):
    """支持从 YAML 动态读取并加载 FSM 的通用流程类"""

    def __init__(self, cfg: dict, device: DeviceManager, default_fsm_path: str = ""):
        super().__init__(cfg, device)

        # 取当前流程名（main_config.yaml 里的 active_flow）
        flow_name = cfg.get("active_flow", "")

        # 优先级：
        #   1) cfg["flows"][<flow_name>]["fsm_yaml"]   ← 方案 B 新增
        #   2) cfg["fsm_yaml"]                          ← 兼容旧写法
        #   3) default_fsm_path                         ← 子类传入的默认值
        flows_cfg = cfg.get("flows", {}) or {}
        per_flow_cfg = flows_cfg.get(flow_name, {}) or {}

        self.fsm_yaml_path = (
            per_flow_cfg.get("fsm_yaml")
            or cfg.get("fsm_yaml")
            or default_fsm_path
        )

        if not self.fsm_yaml_path:
            raise ValueError(
                f"❌ 未找到流程 '{flow_name}' 的 FSM 配置，"
                f"请在 main_config.yaml 的 flows.{flow_name}.fsm_yaml 中指定"
            )

        print(f"🧩 [FSM] 流程 '{flow_name}' 使用状态机文件: {self.fsm_yaml_path}")
        self._init_fsm_from_yaml()

    def _init_fsm_from_yaml(self):
        """使用 pytransitions 初始化状态机"""
        if not self.fsm_yaml_path:
            raise ValueError("❌ 未指定 FSM YAML 配置文件路径！")

        with open(self.fsm_yaml_path, 'r', encoding='utf-8') as f:
            fsm_config = yaml.safe_load(f)

        states = fsm_config.get('states', [])
        initial = fsm_config.get('initial')
        transitions = fsm_config.get('transitions', [])

        self.machine = Machine(
            model=self,
            states=states,
            transitions=transitions,
            initial=initial
        )
        print(f"⚙️ [FSM] 成功加载状态机图谱: {self.fsm_yaml_path}")


class FlowFactory:
    """流程注册器与工厂模式"""
    _registry = {}

    @classmethod
    def register(cls, name: str):
        """装饰器：注册流程"""
        def decorator(subclass):
            cls._registry[name] = subclass
            return subclass
        return decorator

    @classmethod
    def create(cls, name: str, cfg: dict, device: DeviceManager) -> BaseFlow:
        """从工厂创建指定的流程实例"""
        if name not in cls._registry:
            raise ValueError(f"❌ 未找到流程: '{name}'，已注册流程: {list(cls._registry.keys())}")
        return cls._registry[name](cfg, device)