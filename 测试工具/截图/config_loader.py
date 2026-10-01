# ============================================
# 配置加载模块 - 读取 YAML 配置文件
# ============================================

import os
import yaml
from typing import Dict, Any


DEFAULT_CONFIG = {
    "device": {
        "uri": "Android:///"
    },
    "output": {
        "json_filename": "ocr_result.json",
        "query_json_filename": "query_result.json",
        "base_dir": "截屏"
    }
}


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """加载 YAML 配置文件"""
    if not os.path.exists(config_path):
        print(f"⚠️ 配置文件不存在: {config_path}，使用默认配置")
        return DEFAULT_CONFIG

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        merged = {
            "device": {**DEFAULT_CONFIG["device"], **config.get("device", {})},
            "output": {**DEFAULT_CONFIG["output"], **config.get("output", {})},
        }
        print(f"✅ 已加载配置文件: {config_path}")
        return merged

    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}，使用默认配置")
        return DEFAULT_CONFIG