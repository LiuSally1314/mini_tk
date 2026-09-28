# ============================================
# 关键词匹配模块 - 通用关键词规则判断
# ============================================

from typing import Union, Dict, List


# 文本清洗开关（默认关闭）
_ENABLE_TEXT_CLEAN = False


def set_text_clean_enabled(enabled: bool):
    """设置是否启用文本清洗"""
    global _ENABLE_TEXT_CLEAN
    _ENABLE_TEXT_CLEAN = enabled


def clean_text(text: str) -> str:
    """
    文本清洗：去除空白、换行等
    可按需扩展（如去除标点、全角转半角等）
    """
    if not text:
        return ""
    return "".join(text.split())


def check_keywords_match(text: str, confirm_config: Union[Dict, str, List]) -> bool:
    """
    检查文本是否匹配关键词规则

    支持格式：
    - 字符串: 直接匹配包含该字符串
    - 列表: 包含任意一个即可
    - 字典:
        {
            "mode": "mixed",
            "rules": [
                {"type": "must", "keywords": ["关键词1", "关键词2"]}
            ]
        }

    注意：文本清洗功能默认关闭，如需启用请调用 set_text_clean_enabled(True)
    """
    if not text:
        return False

    # 根据开关决定是否清洗文本
    if _ENABLE_TEXT_CLEAN:
        cleaned = clean_text(text)
        search_text = cleaned if cleaned else text
    else:
        search_text = text

    # 字符串匹配
    if isinstance(confirm_config, str):
        return confirm_config in search_text

    # 列表匹配（or模式）
    if isinstance(confirm_config, list):
        return any(keyword in search_text for keyword in confirm_config)

    # 字典配置
    if isinstance(confirm_config, dict):
        mode = confirm_config.get("mode", "or")

        if mode == "and":
            keywords = confirm_config.get("keywords", [])
            if not keywords:
                return True
            return all(keyword in search_text for keyword in keywords)

        elif mode == "or":
            keywords = confirm_config.get("keywords", [])
            if not keywords:
                return True
            return any(keyword in search_text for keyword in keywords)

        elif mode == "mixed":
            rules = confirm_config.get("rules", [])
            if not rules:
                return True

            # 只处理 must 类型，必须全部包含
            for rule in rules:
                rule_type = rule.get("type", "must")
                keywords = rule.get("keywords", [])

                # 不管 type 是什么，都按 must 处理：必须全部包含
                if not all(keyword in search_text for keyword in keywords):
                    return False

            return True

        else:
            # 未知模式，默认使用or
            keywords = confirm_config.get("keywords", [])
            return any(keyword in search_text for keyword in keywords)

    return False