# ============================================
# 配置加载模块
# 1) 读主配置 config.yaml
# 2) 自动扫描 flows_dir 下所有 yaml，按文件名作为 flow 名
# ============================================

import os
import yaml

DEFAULT_CONFIG = {
    "device": {"uri": "Android:///"},
    "output": {
        "json_filename": "ocr_result.json",
        "query_json_filename": "query_result.json",
        "base_dir": "截屏",
    },
    "defaults": {
        "retry": 3,
        "retry_interval": 1.0,
        "interval": 0.5,
        "exact": True,
        "sleep": 0.1,
        "enabled": True,
    },
    "active_flow": "",
    "flows_dir": "config/flows",
    "flows": {},
}


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _load_flows(flows_dir: str) -> dict:
    flows = {}
    if not os.path.isdir(flows_dir):
        print(f"⚠️ 流程目录不存在: {flows_dir}")
        return flows

    for filename in sorted(os.listdir(flows_dir)):
        if not filename.endswith((".yaml", ".yml")):
            continue
        name = os.path.splitext(filename)[0]
        path = os.path.join(flows_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            flows[name] = data
            print(f"  📄 已加载流程: {name}")
        except Exception as e:
            print(f"  ❌ 加载流程失败 {filename}: {e}")
    return flows


def load_config(config_path: str = "config/config.yaml") -> dict:
    config = {k: (v.copy() if isinstance(v, dict) else v)
              for k, v in DEFAULT_CONFIG.items()}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            _deep_merge(config, user_config)
            print(f"✅ 已加载主配置: {config_path}")
        except Exception as e:
            print(f"❌ 主配置读取失败: {e}")
    else:
        print(f"⚠️ 主配置不存在，使用默认: {config_path}")

    # 加载所有流程
    config["flows"] = _load_flows(config["flows_dir"])
    return config