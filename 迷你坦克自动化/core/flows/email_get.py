# ============================================
# 邮箱信息保存流程 + 后台 GM 邮件发送
#
# 识别当前邮件详情页，提取「数量 / 物品名称 / 物品描述」，
# 以「数量」为 id 去重后追加写入 CSV（id,name,desc）。
#
# 同时提供 send_one_email：
#   每次调用只发送 1 次。
#   发送前重新读取 发送后台物品详细.csv（只读，不写）。
#   发送后只更新该行 sent_times +1。
#   不在这里刷新 flag；等所有发送结束后再统一调 refresh_flags()：
#     sent_times <  times -> flag = 0（还需要继续发）
#     sent_times >= times -> flag = 1（已完成）
#   是否可发只认 sent_times < times，flag 不参与“是否可发”判断。
#   其他字段一律原样保留，不主动清空。
#
# 发送后台物品详细.csv 表头：
#   id,name,desc,remark,num,times,flag,sent_times
#   id          道具代号 -> item = props_p{id}
#   num         发送数量（为空不发送）
#   times       发送次数，为空默认 1
#   flag        1 表示已完成；未完成时重置为 0
#   sent_times  已发送次数，为空按 0 处理
#
# 注意：extract_mail_info 依赖「数量：」的全角冒号，
#       因此这里用原始 OCR 文本构造 texts_with_boxes，
#       不做 NFKC 归一化（与 building.py 的归一化策略不同）。
# ============================================

import csv
import os
import random
import re
from typing import Any, Dict, Optional

import requests
import urllib3

from .base import FlowMethods

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================
# 后台接口：常量
# ============================================================
FAILED_LOG_FILE = "failed_items.csv"
SENT_RECORD_FILE = "sent_record.csv"
# BACKEND_ITEMS_PATH = "/Users/mac/Documents/learn/pythonProject/mini_tk/迷你坦克自动化/其他/output.csv"
BACKEND_ITEMS_PATH = "/Users/mac/Documents/learn/pythonProject/mini_tk/迷你坦克自动化/其他/发送后台物品详细.csv"
SAVE_EMAIL_INFO_PATH = "data/不处理.csv"

MAX_BATCH_SIZE = 1
SEND_INTERVAL = 1
PRIORITY_KEYWORD = ""

DEBUG_PRINT_CURL = False
DEBUG_CURL_LOG_FILE = "debug_curl.log"

# 源 CSV 需要的表头（缺列时会自动补齐，已有列不动）
BACKEND_FIELDS = ["id", "name", "desc", "remark", "num", "times", "flag", "sent_times"]


# ============================================================
# 后台接口：工具函数
# ============================================================
def build_curl_command(url, headers, cookies, payload):
    parts = ["curl -X POST", f"'{url}'"]
    parts.append("-k")
    for k, v in headers.items():
        v_escaped = str(v).replace("'", "'\\''")
        parts.append(f"-H '{k}: {v_escaped}'")
    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        parts.append(f"-b '{cookie_str}'")
    for k, v in payload.items():
        v_escaped = str(v).replace("'", "'\\''")
        parts.append(f"--data-urlencode '{k}={v_escaped}'")
    return " ".join(parts)


def log_curl(seq, curl_cmd, path=DEBUG_CURL_LOG_FILE):
    if not path:
        return
    try:
        with open(path, mode="a", encoding="utf-8") as f:
            f.write(f"# 序号 {seq}\n{curl_cmd}\n\n")
    except Exception as e:
        print(f"⚠️ 写入 curl 调试日志失败: {e}")


def load_existing_ids(csv_path=SAVE_EMAIL_INFO_PATH):
    """从 不处理.csv 中加载已存在的道具 ID 集合"""
    existing_ids = set()
    if not os.path.exists(csv_path):
        print(f"⚠️ 未找到 {csv_path}，将不会进行去重过滤。")
        return existing_ids

    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_id = (row.get("id") or "").strip()
            if item_id:
                existing_ids.add(item_id)

    print(f"✅ 已从 {csv_path} 加载 {len(existing_ids)} 个已存在道具 ID。")
    return existing_ids


def load_sent_records(csv_path=SENT_RECORD_FILE):
    """返回 {序号: 已发次数}（仅作流水统计/参考）"""
    sent = {}
    if not os.path.exists(csv_path):
        return sent
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            seq = row[0].strip()
            if not seq or seq == "序号":
                continue
            sent[seq] = sent.get(seq, 0) + 1
    return sent


def count_sent(sent_records, seq):
    """统计某个 seq 在 sent_record.csv 中的流水次数（参考用）"""
    return sent_records.get(str(seq), 0)


def append_sent_record(seq, csv_path=SENT_RECORD_FILE):
    file_exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["序号"])
        writer.writerow([seq])


# ------------------------------------------------------------
# 源 CSV 读写：只增不改，不主动清字段
# ------------------------------------------------------------
def _read_backend_rows(backend_path=BACKEND_ITEMS_PATH):
    """读取源 CSV，返回 (fieldnames, rows)，缺列自动补齐，已有列不动"""
    with open(backend_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    changed_fields = False
    for col in BACKEND_FIELDS:
        if col not in fieldnames:
            fieldnames.append(col)
            changed_fields = True

    if changed_fields:
        for row in rows:
            for col in BACKEND_FIELDS:
                row.setdefault(col, "")

    return fieldnames, rows


def _write_backend_rows(fieldnames, rows, backend_path=BACKEND_ITEMS_PATH):
    with open(backend_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_int(value, default=0):
    try:
        s = str(value).strip()
        return int(s) if s else default
    except (ValueError, TypeError):
        return default


def increase_sent_times(seq, backend_path=BACKEND_ITEMS_PATH):
    """
    只更新源 CSV 中 id == seq 的那一行：
      sent_times += 1
    不主动改 flag（flag 由 refresh_flags 统一刷新）。
    其他字段一律原样保留。
    返回 (new_sent_times, times)
    """
    if not os.path.exists(backend_path):
        return 0, 1

    fieldnames, rows = _read_backend_rows(backend_path)
    new_sent = 0
    times_int = 1

    for row in rows:
        if (row.get("id") or "").strip() == str(seq):
            sent_int = _parse_int(row.get("sent_times"), 0)

            times_str = (row.get("times") or "").strip()
            times_int = _parse_int(times_str, 1) if times_str else 1
            if times_int <= 0:
                times_int = 1

            sent_int += 1
            row["sent_times"] = str(sent_int)
            new_sent = sent_int
            break

    _write_backend_rows(fieldnames, rows, backend_path)
    print(f"  🧮 id={seq} 已发送次数更新为 {new_sent}/{times_int}")
    return new_sent, times_int


def refresh_flags(backend_path=BACKEND_ITEMS_PATH):
    """
    重新扫描源 CSV，按 times / sent_times 刷新 flag：
      num 为空            -> 不动
      sent_times <  times -> flag = 0（还需要继续发）
      sent_times >= times -> flag = 1（已完成）
    只改 flag 列，其他字段原样保留。
    """
    if not os.path.exists(backend_path):
        return

    fieldnames, rows = _read_backend_rows(backend_path)
    changed = 0

    for row in rows:
        num_str = (row.get("num") or "").strip()
        if not num_str:
            continue

        times_str = (row.get("times") or "").strip()
        times_int = _parse_int(times_str, 1) if times_str else 1
        if times_int <= 0:
            times_int = 1

        sent_int = _parse_int(row.get("sent_times"), 0)
        old_flag = (row.get("flag") or "").strip()

        if sent_int < times_int:
            new_flag = "0"
        else:
            new_flag = "1"

        if old_flag != new_flag:
            row["flag"] = new_flag
            changed += 1

    if changed:
        _write_backend_rows(fieldnames, rows, backend_path)
        print(f"  🔄 已刷新 flag：{changed} 行更新")
    else:
        print("  🔄 已刷新 flag：无变化")


def init_failed_log():
    if os.path.exists(FAILED_LOG_FILE):
        return
    with open(FAILED_LOG_FILE, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["序号", "名称", "道具代号", "数量", "备注", "响应信息"])


def log_failure(seq, name, item, num, remark, response_msg):
    with open(FAILED_LOG_FILE, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([seq, name, item, num, remark, response_msg])


def build_headers():
    return {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "http://124.220.207.172",
        "Referer": "http://124.220.207.172/gm/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0"
            " Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }


def build_cookies():
    return {"PHPSESSID": "aiq1md4mhnmpqb4ci1bt01dtf3"}


def build_payload(type_name, uid, item_code, send_num, qu, pwd, title, content):
    """
    item_code: 道具代号，形如 props_p{id}
    send_num : 发送数量
    """
    return {
        "type": type_name,
        "uid": uid,
        "num": str(send_num),
        "item": item_code,
        "qu": str(qu),
        "pwd": str(pwd),
        "title": title,
        "content": content,
    }


def send_gm_query_sync(
    seq,
    name,
    item,
    num,
    type_name="daoju",
    uid="爱莉希雅、",
    qu=1,
    pwd=963,
    title="GM邮件",
    content="亲爱的玩家，请查收您的邮件!",
    url="http://124.220.207.172/gm/user/query.php",
):
    headers = build_headers()
    cookies = build_cookies()

    def do_post(item_code, send_num, tag=""):
        payload = build_payload(type_name, uid, item_code, send_num, qu, pwd, title, content)

        curl_cmd = None
        if DEBUG_PRINT_CURL:
            curl_cmd = build_curl_command(url, headers, cookies, payload)
            print(f"\n🐞 [DEBUG][序号 {seq}]{tag} curl 命令：")
            print(curl_cmd)
            print("-" * 80)
            log_curl(seq, curl_cmd)

        try:
            response = requests.post(
                url,
                headers=headers,
                data=payload,
                cookies=cookies,
                verify=False,
                timeout=30,
            )
            return response.text, curl_cmd, None
        except Exception as e:
            return None, curl_cmd, e

    res_text, curl_cmd, err = do_post(item, num, tag="[第一次]")
    if err is not None:
        print(f"⚠️ [网络/请求异常] 序号: {seq} | 道具: {item} | 错误: {err}")
        log_failure(seq, name, item, num, remark="网络异常", response_msg=str(err))
        append_sent_record(seq)
        return False

    first_failed = ("不存在" in res_text) or ("失败" in res_text) or ("错误" in res_text)

    if not first_failed:
        print(f"✅ [已发送] 序号: {seq} | 名称: {name} ({item}) | 数量: {num} | 响应: {res_text[:50].strip()}")
        append_sent_record(seq)
        return True

    print(f"❌ [第一次失败] 序号: {seq} | 名称: {name} ({item}) | 数量: {num} | 响应: {res_text.strip()}")

    match = re.search(r"(\d+)$", name)
    if match:
        real_num = match.group(1)
        retry_item = f"props_p{real_num}"
        print(f"🔁 [重试] 序号: {seq} | 从名称提取数字: {real_num}，改用道具代号 {retry_item} 重试")

        res_text2, curl_cmd2, err2 = do_post(retry_item, num, tag="[重试]")
        if err2 is not None:
            print(f"⚠️ [重试网络异常] 序号: {seq} | 道具: {retry_item} | 错误: {err2}")
            log_failure(seq, name, retry_item, num,
                        remark="重试网络异常", response_msg=str(err2))
            append_sent_record(seq)
            return False

        second_failed = ("不存在" in res_text2) or ("失败" in res_text2) or ("错误" in res_text2)
        if not second_failed:
            print(f"✅ [重试成功] 序号: {seq} | 名称: {name} | 道具: {retry_item} | 数量: {num} | 响应: {res_text2[:50].strip()}")
            append_sent_record(seq)
            return True
        else:
            print(f"❌ [重试仍失败] 序号: {seq} | 名称: {name} | {retry_item} | 响应: {res_text2.strip()}")
            log_failure(seq, name, retry_item, num,
                        remark="重试仍失败", response_msg=res_text2.strip())
            append_sent_record(seq)
            return False
    else:
        print(f"❌ [无法提取数字] 序号: {seq} | 名称: {name} | 第一次响应: {res_text.strip()}")
        log_failure(seq, name, item, num,
                    remark="发送失败且名称无数字", response_msg=res_text.strip())
        append_sent_record(seq)
        return False


def load_all_candidates(backend_path=BACKEND_ITEMS_PATH):
    """
    读取 发送后台物品详细.csv，表头：
    id,name,desc,remark,num,times,flag,sent_times

    id          -> 道具代号（props_p{id}）
    num         -> 发送数量（为空不发送）
    times       -> 发送次数，为空默认 1
    flag        -> 仅作展示，不参与“是否可发”判断
    sent_times  -> 已发送次数，空按 0
    """
    candidates = []
    if not os.path.exists(backend_path):
        raise FileNotFoundError(f"❌ 输入文件不存在: {backend_path}")

    fieldnames, rows = _read_backend_rows(backend_path)

    for row in rows:
        item_id = (row.get("id") or "").strip()
        name = (row.get("name") or "").strip()
        num = (row.get("num") or "").strip()
        times = (row.get("times") or "").strip()
        flag = (row.get("flag") or "").strip()
        sent_times = (row.get("sent_times") or "").strip()

        if not item_id:
            continue

        # num 为空 -> 不发送
        if not num:
            continue

        # times 为空 -> 默认 1 次
        times_int = _parse_int(times, 1) if times else 1
        if times_int <= 0:
            times_int = 1

        sent_int = _parse_int(sent_times, 0)

        candidates.append({
            "seq": item_id,
            "name": name,
            "num": num,            # 发送数量（接口用）
            "times": times_int,    # 目标次数
            "flag": flag,
            "sent_times": sent_int,
            "item_code": f"props_p{item_id}",
        })
    return candidates


def is_sendable(item, existing_ids):
    seq = item["seq"]

    if seq in existing_ids:
        return False

    # 只认 sent_times < times；flag 不参与“是否可发”判断
    if item["sent_times"] >= item["times"]:
        return False

    return True


def collect_pending_items(
    backend_path=BACKEND_ITEMS_PATH,
    existing_ids=None,
):
    """
    读取 发送后台物品详细.csv -> 过滤出可发送的 -> 分成优先池和普通池
    优先池：name 中包含 PRIORITY_KEYWORD（不区分大小写）
    """
    if existing_ids is None:
        existing_ids = set()

    all_candidates = load_all_candidates(backend_path)
    sendable = [it for it in all_candidates if is_sendable(it, existing_ids)]

    total = len(all_candidates)
    skipped = total - len(sendable)

    # 待发总次数 = 每条剩余次数之和
    remaining_total = sum(
        max(0, it["times"] - it["sent_times"]) for it in sendable
    )

    priority_pool = [
        it for it in sendable
        if PRIORITY_KEYWORD.lower() in it["name"].lower()
    ]
    normal_pool = [
        it for it in sendable
        if PRIORITY_KEYWORD.lower() not in it["name"].lower()
    ]

    print(
        f"📊 过滤统计：候选总数 {total} 条，已存在/已发送完成跳过 {skipped} 条，"
        f"可发送 {len(sendable)} 条，待发总次数 {remaining_total} 次"
        f"（优先池 {len(priority_pool)} 条，普通池 {len(normal_pool)} 条）。"
    )

    if not sendable:
        return []

    take = min(MAX_BATCH_SIZE, len(sendable))

    priority_take = min(take, len(priority_pool))
    pending = random.sample(priority_pool, priority_take) if priority_take > 0 else []

    remaining = take - len(pending)
    if remaining > 0 and normal_pool:
        normal_take = min(remaining, len(normal_pool))
        pending.extend(random.sample(normal_pool, normal_take))

    print(
        f"🎲 本批随机抽取 {len(pending)} 条发送："
        f"优先池 {priority_take} 条，普通池 {len(pending) - priority_take} 条。"
    )
    return pending


# ============================================================
# 邮件信息解析（业务解析全部在本文件内完成）
# ============================================================
def extract_mail_info(data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "数量": None,
        "物品名称": None,
        "物品描述": None,
    }

    items = data.get("texts_with_boxes", [])

    # 1. 找数量
    count_item = None
    for item in items:
        if item and len(item) >= 2 and item[0].startswith("数量："):
            count_item = item
            break

    if not count_item:
        return result

    count_text = count_item[0]
    count_center = count_item[1]
    count_box = count_item[2:]
    count_y = count_center[1]

    result["数量"] = {
        "text": count_text,
        "value": count_text.replace("数量：", "").strip(),
        "center": count_center,
        "box": count_box,
    }

    # 2. 找「点击屏幕继续」
    continue_y = None
    for item in items:
        if item and len(item) >= 2 and "点击屏幕继续" in item[0]:
            continue_y = item[1][1]
            break

    if continue_y is None:
        return result

    # 3. 物品名称：数量 y 上方最近的一条文本
    above = []
    for item in items:
        if not item or len(item) < 2:
            continue
        text = item[0]
        center = item[1]
        box = item[2:]
        cy = center[1]

        if cy < count_y:
            above.append({
                "text": text,
                "center": center,
                "box": box,
                "cy": cy,
            })

    if above:
        above.sort(key=lambda x: x["cy"], reverse=True)
        name_item = above[0]
        result["物品名称"] = {
            "text": name_item["text"],
            "center": name_item["center"],
            "box": name_item["box"],
        }

    # 4. 物品描述：数量 y 到 点击屏幕继续 y 之间
    desc_items = []
    for item in items:
        if not item or len(item) < 2:
            continue
        text = item[0]
        center = item[1]
        box = item[2:]
        cy = center[1]

        if count_y < cy < continue_y and not text.startswith("数量："):
            desc_items.append({
                "text": text,
                "center": center,
                "box": box,
                "cy": cy,
            })

    if desc_items:
        desc_items.sort(key=lambda x: x["cy"])
        desc_text = "".join(d["text"] for d in desc_items)
        result["物品描述"] = {
            "text": desc_text,
            "center": desc_items[0]["center"],
            "box": desc_items[0]["box"],
        }

    return result


# ============================================================
# Flow 方法
# ============================================================
class EmailGetFlow(FlowMethods):
    """邮箱信息：保存邮件物品信息到 CSV（按 id 去重）+ 发送后台 GM 邮件"""

    # ---------- 保存邮件信息 ----------
    def save_email_info(
        self,
        file: str = "data/save_email_info.csv",
        debug: bool = False,
    ) -> Optional[dict]:
        # ---------- 1. 原始 OCR ----------
        page_data = self.finder.get_page_ocr_data(self.dm)
        if not page_data:
            print("  ❌ save_email_info: OCR 失败")
            return None

        # ---------- 2. 原始 OCR → texts_with_boxes ----------
        texts_with_boxes = []
        for box, text, _score in page_data:
            text_str = str(text).strip()
            if not text_str:
                continue

            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)

            texts_with_boxes.append([
                text_str,
                [cx, cy],
                [box[0][0], box[0][1]],
                [box[1][0], box[1][1]],
                [box[2][0], box[2][1]],
                [box[3][0], box[3][1]],
            ])

        if debug:
            print(f"  📋 OCR 共 {len(texts_with_boxes)} 条：")
            for t in texts_with_boxes:
                print(f"     ({t[1][0]:.0f},{t[1][1]:.0f}) 「{t[0]}」")

        # ---------- 3. 业务解析 ----------
        mail = extract_mail_info({"texts_with_boxes": texts_with_boxes})

        count = mail.get("数量")
        name = mail.get("物品名称")
        desc = mail.get("物品描述")

        if not count:
            print("  ⚠️ 未识别到「数量：」，无法作为 id，跳过")
            return None

        mail_id = str(count["value"]).strip()
        mail_name = name["text"].strip() if name else ""
        mail_desc = desc["text"].strip() if desc else ""

        if debug:
            print(f"  📧 解析结果: id={mail_id!r} "
                  f"name={mail_name!r} desc={mail_desc!r}")

        # ---------- 4. 读取旧数据（CSV，按 id 去重） ----------
        os.makedirs(os.path.dirname(file) or ".", exist_ok=True)

        existing_ids = set()
        file_exists = os.path.exists(file)

        if file_exists:
            try:
                with open(file, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rid = (row.get("id") or "").strip()
                        if rid:
                            existing_ids.add(rid)
            except Exception as e:
                print(f"  ⚠️ 读取旧数据失败，按空历史处理: {e}")
                existing_ids = set()
                file_exists = False

        # ---------- 5. 按「id」去重 ----------
        if mail_id in existing_ids:
            print(f"  ⏭ 已存在 id={mail_id}，跳过写入"
                  f"（累计 {len(existing_ids)} 条）")
            return {"id": mail_id, "name": mail_name, "desc": mail_desc}

        # ---------- 6. 追加 & 写回 ----------
        try:
            with open(file, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "name", "desc"])
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "id": mail_id,
                    "name": mail_name,
                    "desc": mail_desc,
                })
        except Exception as e:
            print(f"  ❌ 写入 CSV 失败: {e}")
            return None

        print(f"  💾 已保存 → {file}（累计 {len(existing_ids) + 1} 条）")
        print(f"     id={mail_id} | name={mail_name} | desc={mail_desc}")
        return {"id": mail_id, "name": mail_name, "desc": mail_desc}

    # ---------- 发送一封后台 GM 邮件 ----------
    def send_one_email(self, debug: bool = False) -> bool:
        """
        每次调用只发送 1 次。
        发送前只读源 CSV；发送后只更新该行 sent_times +1。
        不在这里刷新 flag；等所有发送结束后再统一调 refresh_flags()。
        无可发送项返回 False。
        """
        init_failed_log()
        existing_ids = load_existing_ids()

        pending = collect_pending_items(
            existing_ids=existing_ids,
        )
        if not pending:
            print("  🎉 没有可发送的物品了")
            return False

        it = pending[0]
        print(f"  📮 本次发送: 序号={it['seq']} 名称={it['name']} "
              f"代号={it['item_code']} 数量={it['num']} "
              f"(已发 {it['sent_times']}/{it['times']})")

        if debug:
            print(f"     [debug] 可发送 {len(pending)} 条，本次取第 1 条")

        ok = send_gm_query_sync(
            seq=it["seq"],
            name=it["name"],
            item=it["item_code"],
            num=it["num"],
        )

        # 只更新该行 sent_times；flag 等全部发完后统一刷新
        increase_sent_times(it["seq"])

        return ok