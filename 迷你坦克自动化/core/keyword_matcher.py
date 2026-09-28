# ============================================
# 关键词匹配模块 - 通用关键词规则判断
#
# 支持三种配置形式：
#   1. 字符串         "建造"                    → 子串匹配
#   2. 字符串列表     ["建造", "研究"]           → 任一命中即可
#   3. 字典（规则）   {mode: "and/or/mixed", ...}
#
# mixed 模式：
#   rules:     规则列表，每条规则 {type, keywords}
#   match_mode: "all"（全部规则满足，默认）/ "any"（任一规则满足）
#   rule.type:
#     must → 全部关键词都出现（AND）
#     any  → 任一关键词出现（OR）
#     not  → 全部关键词都不出现
# ============================================

from typing import Union, Dict, List

_ENABLE_TEXT_CLEAN = False


def set_text_clean_enabled(enabled: bool):
    global _ENABLE_TEXT_CLEAN
    _ENABLE_TEXT_CLEAN = enabled


def clean_text(text: str) -> str:
    if not text:
        return ""
    return "".join(text.split())


def check_keywords_match(text: str, confirm_config: Union[Dict, str, List]) -> bool:
    if not text:
        return False

    search_text = clean_text(text) if _ENABLE_TEXT_CLEAN else text

    if isinstance(confirm_config, str):
        return confirm_config in search_text

    if isinstance(confirm_config, list):
        return any(keyword in search_text for keyword in confirm_config)

    if isinstance(confirm_config, dict):
        mode = confirm_config.get("mode", "or")

        if mode == "and":
            keywords = confirm_config.get("keywords", [])
            return all(kw in search_text for kw in keywords) if keywords else True

        if mode == "or":
            keywords = confirm_config.get("keywords", [])
            return any(kw in search_text for kw in keywords) if keywords else True

        if mode == "mixed":
            rules = confirm_config.get("rules", [])
            if not rules:
                return True

            match_mode = confirm_config.get("match_mode", "all")

            rule_results = []
            for rule in rules:
                rule_type = rule.get("type", "must")
                keywords = rule.get("keywords", [])

                if not keywords:
                    rule_results.append(True)
                    continue

                if rule_type == "not":
                    ok = all(kw not in search_text for kw in keywords)
                elif rule_type == "any":
                    ok = any(kw in search_text for kw in keywords)
                else:
                    ok = all(kw in search_text for kw in keywords)

                rule_results.append(ok)

            if match_mode == "any":
                return any(rule_results)
            return all(rule_results)

        keywords = confirm_config.get("keywords", [])
        return any(kw in search_text for kw in keywords)

    return False


def only_not_rules_matched(text: str, confirm_config: Union[Dict, str, List]) -> bool:
    """检查是否仅仅是 not 规则触发匹配（用来计算连续确认）"""
    if not isinstance(confirm_config, dict) or confirm_config.get("mode") != "mixed":
        return False

    rules = confirm_config.get("rules", [])
    if not rules:
        return False

    search_text = text or ""
    must_any_hit = False
    not_hit = False

    for rule in rules:
        rule_type = rule.get("type", "must")
        keywords = rule.get("keywords", [])
        if not keywords:
            continue

        if rule_type == "not":
            if all(kw not in search_text for kw in keywords):
                not_hit = True
        elif rule_type == "any":
            if any(kw in search_text for kw in keywords):
                must_any_hit = True
        else:
            if all(kw in search_text for kw in keywords):
                must_any_hit = True

    return not_hit and not must_any_hit