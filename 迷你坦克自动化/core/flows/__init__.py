# ============================================
# 流程方法注册中心
#
# 约定：
#   core/flows/<name>.py 里定义类，继承 FlowMethods
#   类里所有 public 方法（不以 _ 开头）会被收集进 registry
#   ActionRunner.run_method 通过 registry 查找并调用
#
# 新增流程：
#   1. 在 core/flows/ 下新建 <name>.py
#   2. 定义 class XxxFlow(FlowMethods): ...
#   3. 无需改任何其他文件
# ============================================

import importlib
import inspect
import os
import pkgutil
from typing import Any, Callable, Dict, Optional

from .base import FlowMethods


# 全局方法表：method_name -> bound method
_REGISTRY: Dict[str, Callable] = {}
# 全局方法归属：method_name -> 类名（用于报错/日志）
_OWNERS: Dict[str, str] = {}
# 实例缓存：类名 -> 实例
_INSTANCES: Dict[str, FlowMethods] = {}

# 与 ActionRunner 内建方法冲突的名字，禁止注册
BUILTIN_METHODS = {
    "do_find", "do_click", "do_find_click", "do_wait", "do_wait_text",
    "do_abort_check", "do_dump_ocr", "do_repeat", "do_for_each_coord",
    "do_poll_click", "do_call_flow", "do_run_method",
    "scan_general_skills", "get_click_target", "update_click_count",
    "run_step",
}


def _discover_modules():
    """扫描当前包下所有 .py（排除 __init__ / base）"""
    pkg_dir = os.path.dirname(__file__)
    for _, mod_name, _ in pkgutil.iter_modules([pkg_dir]):
        if mod_name in ("__init__", "base"):
            continue
        yield mod_name


def register_all(force: bool = False):
    """
    扫描并注册所有流程方法（只注册一次）。
    force=True 时清空后重新注册。
    """
    if force:
        _REGISTRY.clear()
        _OWNERS.clear()
        _INSTANCES.clear()

    if _REGISTRY:
        return  # 已注册

    for mod_name in _discover_modules():
        try:
            module = importlib.import_module(f".{mod_name}", package=__name__)
        except Exception as e:
            print(f"  ⚠️ 加载流程模块失败 {mod_name}: {e}")
            continue

        for cls_name, cls in inspect.getmembers(module, inspect.isclass):
            if cls is FlowMethods:
                continue
            if not issubclass(cls, FlowMethods):
                continue
            if cls.__module__ != module.__name__:
                continue

            try:
                inst = cls()
            except Exception as e:
                print(f"  ⚠️ 实例化 {mod_name}.{cls_name} 失败: {e}")
                continue

            _INSTANCES[cls_name] = inst

            for method_name, method in inspect.getmembers(inst, inspect.ismethod):
                if method_name.startswith("_"):
                    continue
                if method_name in BUILTIN_METHODS:
                    print(f"  ⚠️ 方法「{method_name}」（{cls_name}）"
                          f"与内建冲突，跳过注册")
                    continue
                if method_name in _REGISTRY:
                    print(f"  ⚠️ 方法名冲突「{method_name}」："
                          f"{_OWNERS[method_name]} 已被 {cls_name} 覆盖")
                _REGISTRY[method_name] = method
                _OWNERS[method_name] = cls_name

    if _REGISTRY:
        print(f"  📦 已注册流程方法 {len(_REGISTRY)} 个: "
              f"{', '.join(sorted(_REGISTRY.keys()))}")
    else:
        print("  📦 未发现任何流程方法（core/flows/ 下为空）")


def bind_all(runner: Any):
    """把所有实例绑到 ActionRunner 上（在 register_all 之后调用）"""
    for inst in _INSTANCES.values():
        inst.bind(runner)


def get_method(name: str) -> Optional[Callable]:
    return _REGISTRY.get(name)


def get_owner(name: str) -> str:
    return _OWNERS.get(name, "?")


def get_instances() -> Dict[str, FlowMethods]:
    return dict(_INSTANCES)


def list_methods() -> Dict[str, str]:
    return dict(_OWNERS)