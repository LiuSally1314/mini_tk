import csv
import os
import random
import re
import time

import requests

# ============ 异步开关 ============
USE_ASYNC = False

if USE_ASYNC:
    import asyncio
    import aiohttp

# 忽略 SSL 证书校验
ssl_context = False

# 失败日志文件名
FAILED_LOG_FILE = "failed_items.csv"

# 已发送记录文件
SENT_RECORD_FILE = "sent_record.csv"

# save_email_info.csv 路径（用于去重：里面记录的 id 就是已存在的道具 id）
SAVE_EMAIL_INFO_PATH = "/Users/mac/Documents/learn/pythonProject/mini_tk/迷你坦克自动化/data/save_email_info.csv"

# ============ 输入文件：output.csv ============
BACKEND_ITEMS_PATH = "output.csv"

# 单批最大发送数量
MAX_BATCH_SIZE = 1000

# 每条发送之间的间隔（秒）
SEND_INTERVAL = 2

# ============ 优先关键字 ============
PRIORITY_KEYWORD = "sample"

# ============ 调试开关 ============
DEBUG_PRINT_CURL = False
DEBUG_CURL_LOG_FILE = "debug_curl.log"


def build_curl_command(url, headers, cookies, payload):
    parts = ["curl -X POST", f"'{url}'"]
    if ssl_context is False:
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
    """从 save_email_info.csv 中加载已存在的道具 ID 集合"""
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
    sent = set()
    if not os.path.exists(csv_path):
        return sent
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                sent.add(row[0].strip())
    return sent


def append_sent_record(seq, csv_path=SENT_RECORD_FILE):
    file_exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["序号"])
        writer.writerow([seq])


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


# =====================================================================
# 公共请求参数构造
# =====================================================================
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


def build_payload(type_name, uid, num, qu, pwd, title, content):
    return {
        "type": type_name,
        "uid": uid,
        "num": str(num),
        "item": f"props_p{num}",
        "qu": str(qu),
        "pwd": str(pwd),
        "title": title,
        "content": content,
    }


# =====================================================================
# 同步实现
# =====================================================================
def send_gm_query_sync(
    seq,
    name,
    item,
    num,
    type_name="daoju",
    uid="爱莉希雅、",
    qu=1,
    pwd=69,
    title="GM邮件",
    content="亲爱的玩家，请查收您的邮件!",
    url="http://124.220.207.172/gm/user/query.php",
):
    headers = build_headers()
    cookies = build_cookies()

    def do_post(item_num, tag=""):
        payload = build_payload(type_name, uid, item_num, qu, pwd, title, content)

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

    res_text, curl_cmd, err = do_post(num, tag="[第一次]")
    if err is not None:
        print(f"⚠️ [网络/请求异常] 序号: {seq} | 道具: props_p{num} | 错误: {err}")
        if curl_cmd:
            print(f"🐞 [异常请求 curl] {curl_cmd}")
        log_failure(seq, name, f"props_p{num}", num, remark="网络异常", response_msg=str(err))
        append_sent_record(seq)
        return False

    first_failed = ("不存在" in res_text) or ("失败" in res_text) or ("错误" in res_text)

    if not first_failed:
        print(f"✅ [已发送] 序号: {seq} | 名称: {name} (props_p{num}) | 响应: {res_text[:50].strip()}")
        append_sent_record(seq)
        return True

    print(f"❌ [第一次失败] 序号: {seq} | 名称: {name} (props_p{num}) | 响应: {res_text.strip()}")

    match = re.search(r"(\d+)$", name)
    if match:
        real_num = match.group(1)
        print(f"🔁 [重试] 序号: {seq} | 从名称提取数字: {real_num}，改用 num={real_num} 重试")

        res_text2, curl_cmd2, err2 = do_post(real_num, tag="[重试]")
        if err2 is not None:
            print(f"⚠️ [重试网络异常] 序号: {seq} | 道具: props_p{real_num} | 错误: {err2}")
            if curl_cmd2:
                print(f"🐞 [重试异常 curl] {curl_cmd2}")
            log_failure(seq, name, f"props_p{real_num}", real_num,
                        remark="重试网络异常", response_msg=str(err2))
            append_sent_record(seq)
            return False

        second_failed = ("不存在" in res_text2) or ("失败" in res_text2) or ("错误" in res_text2)
        if not second_failed:
            print(f"✅ [重试成功] 序号: {seq} | 名称: {name} | num={real_num} | 响应: {res_text2[:50].strip()}")
            append_sent_record(seq)
            return True
        else:
            print(f"❌ [重试仍失败] 序号: {seq} | 名称: {name} | props_p{real_num} | 响应: {res_text2.strip()}")
            log_failure(seq, name, f"props_p{real_num}", real_num,
                        remark="重试仍失败", response_msg=res_text2.strip())
            append_sent_record(seq)
            return False
    else:
        print(f"❌ [无法提取数字] 序号: {seq} | 名称: {name} | 第一次响应: {res_text.strip()}")
        log_failure(seq, name, f"props_p{num}", num,
                    remark="发送失败且名称无数字", response_msg=res_text.strip())
        append_sent_record(seq)
        return False


# =====================================================================
# 异步实现
# =====================================================================
async def send_gm_query_async(
    session,
    seq,
    name,
    item,
    num,
    type_name="daoju",
    uid="爱莉希雅、",
    qu=1,
    pwd=69,
    title="GM邮件",
    content="亲爱的玩家，请查收您的邮件!",
    url="http://124.220.207.172/gm/user/query.php",
):
    headers = build_headers()
    cookies = build_cookies()

    async def do_post(item_num, tag=""):
        payload = build_payload(type_name, uid, item_num, qu, pwd, title, content)

        curl_cmd = None
        if DEBUG_PRINT_CURL:
            curl_cmd = build_curl_command(url, headers, cookies, payload)
            print(f"\n🐞 [DEBUG][序号 {seq}]{tag} curl 命令：")
            print(curl_cmd)
            print("-" * 80)
            log_curl(seq, curl_cmd)

        try:
            async with session.post(
                url, headers=headers, data=payload, cookies=cookies, ssl=ssl_context
            ) as response:
                res_text = await response.text()
                return res_text, curl_cmd, None
        except Exception as e:
            return None, curl_cmd, e

    res_text, curl_cmd, err = await do_post(num, tag="[第一次]")
    if err is not None:
        print(f"⚠️ [网络/请求异常] 序号: {seq} | 道具: props_p{num} | 错误: {err}")
        if curl_cmd:
            print(f"🐞 [异常请求 curl] {curl_cmd}")
        log_failure(seq, name, f"props_p{num}", num, remark="网络异常", response_msg=str(err))
        append_sent_record(seq)
        return False

    first_failed = ("不存在" in res_text) or ("失败" in res_text) or ("错误" in res_text)

    if not first_failed:
        print(f"✅ [已发送] 序号: {seq} | 名称: {name} (props_p{num}) | 响应: {res_text[:50].strip()}")
        append_sent_record(seq)
        return True

    print(f"❌ [第一次失败] 序号: {seq} | 名称: {name} (props_p{num}) | 响应: {res_text.strip()}")

    match = re.search(r"(\d+)$", name)
    if match:
        real_num = match.group(1)
        print(f"🔁 [重试] 序号: {seq} | 从名称提取数字: {real_num}，改用 num={real_num} 重试")

        res_text2, curl_cmd2, err2 = await do_post(real_num, tag="[重试]")
        if err2 is not None:
            print(f"⚠️ [重试网络异常] 序号: {seq} | 道具: props_p{real_num} | 错误: {err2}")
            if curl_cmd2:
                print(f"🐞 [重试异常 curl] {curl_cmd2}")
            log_failure(seq, name, f"props_p{real_num}", real_num,
                        remark="重试网络异常", response_msg=str(err2))
            append_sent_record(seq)
            return False

        second_failed = ("不存在" in res_text2) or ("失败" in res_text2) or ("错误" in res_text2)
        if not second_failed:
            print(f"✅ [重试成功] 序号: {seq} | 名称: {name} | num={real_num} | 响应: {res_text2[:50].strip()}")
            append_sent_record(seq)
            return True
        else:
            print(f"❌ [重试仍失败] 序号: {seq} | 名称: {name} | props_p{real_num} | 响应: {res_text2.strip()}")
            log_failure(seq, name, f"props_p{real_num}", real_num,
                        remark="重试仍失败", response_msg=res_text2.strip())
            append_sent_record(seq)
            return False
    else:
        print(f"❌ [无法提取数字] 序号: {seq} | 名称: {name} | 第一次响应: {res_text.strip()}")
        log_failure(seq, name, f"props_p{num}", num,
                    remark="发送失败且名称无数字", response_msg=res_text.strip())
        append_sent_record(seq)
        return False


# =====================================================================
# 通用工具函数
# =====================================================================
def load_all_candidates(backend_path=BACKEND_ITEMS_PATH):
    """
    读取 output.csv，格式为：id,name
    id 同时作为 序号(seq) 和 num(道具代号数字)
    """
    candidates = []
    if not os.path.exists(backend_path):
        raise FileNotFoundError(f"❌ 输入文件不存在: {backend_path}")

    with open(backend_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_id = (row.get("id") or "").strip()
            name = (row.get("name") or "").strip()

            if not item_id:
                continue

            candidates.append(
                {
                    "seq": item_id,          # 序号 = id
                    "name": name,            # 名称
                    "num": item_id,          # 数量/道具代号数字 = id
                    "item_code": f"props_p{item_id}",
                }
            )
    return candidates


def is_sendable(item, existing_ids, sent_records):
    seq = item["seq"]
    if seq in existing_ids:
        return False
    if seq in sent_records:
        return False
    return True


def collect_pending_items(
    backend_path=BACKEND_ITEMS_PATH,
    existing_ids=None,
    sent_records=None,
):
    """
    读取 output.csv -> 过滤出可发送的 -> 分成优先池和普通池
    优先池：name 中包含 PRIORITY_KEYWORD（不区分大小写）
    先从优先池随机抽，不够再从普通池随机补齐
    """
    if existing_ids is None:
        existing_ids = set()
    if sent_records is None:
        sent_records = set()

    all_candidates = load_all_candidates(backend_path)

    # 过滤出可发送的
    sendable = [it for it in all_candidates if is_sendable(it, existing_ids, sent_records)]

    total = len(all_candidates)
    skipped = total - len(sendable)

    # 分成优先池和普通池
    priority_pool = [
        it for it in sendable
        if PRIORITY_KEYWORD.lower() in it["name"].lower()
    ]
    normal_pool = [
        it for it in sendable
        if PRIORITY_KEYWORD.lower() not in it["name"].lower()
    ]

    print(
        f"📊 过滤统计：候选总数 {total} 条，已存在/已发送跳过 {skipped} 条，"
        f"可发送 {len(sendable)} 条（优先池 {len(priority_pool)} 条，普通池 {len(normal_pool)} 条）。"
    )

    if not sendable:
        return []

    take = min(MAX_BATCH_SIZE, len(sendable))

    # 先从优先池随机抽
    priority_take = min(take, len(priority_pool))
    pending = random.sample(priority_pool, priority_take) if priority_take > 0 else []

    # 不够再从普通池随机补
    remaining = take - len(pending)
    if remaining > 0 and normal_pool:
        normal_take = min(remaining, len(normal_pool))
        pending.extend(random.sample(normal_pool, normal_take))

    print(
        f"🎲 本批随机抽取 {len(pending)} 条发送："
        f"优先池 {priority_take} 条，普通池 {len(pending) - priority_take} 条。"
    )

    return pending


# =====================================================================
# 同步批量发送
# =====================================================================
def send_batch_sync(items, interval=SEND_INTERVAL):
    sent_records = load_sent_records()

    for it in items:
        if it["seq"] in sent_records:
            print(f"⏭️ 序号 [{it['seq']}] 已发送过，跳过。")
            continue

        print(f"正在处理序号 [{it['seq']}]: 名称={it['name']}, 代号=props_p{it['num']}, 数量={it['num']}")
        ok = send_gm_query_sync(
            seq=it["seq"],
            name=it["name"],
            item=it["item_code"],
            num=it["num"],
        )
        if ok:
            sent_records.add(it["seq"])
        time.sleep(interval)


# =====================================================================
# 异步批量发送
# =====================================================================
async def send_batch_async(items, interval=SEND_INTERVAL):
    sent_records = load_sent_records()

    async with aiohttp.ClientSession() as session:
        for it in items:
            if it["seq"] in sent_records:
                print(f"⏭️ 序号 [{it['seq']}] 已发送过，跳过。")
                continue

            print(f"正在处理序号 [{it['seq']}]: 名称={it['name']}, 代号=props_p{it['num']}, 数量={it['num']}")
            ok = await send_gm_query_async(
                session,
                seq=it["seq"],
                name=it["name"],
                item=it["item_code"],
                num=it["num"],
            )
            if ok:
                sent_records.add(it["seq"])
            await asyncio.sleep(interval)


# =====================================================================
# 主流程（同步/异步统一入口）
# =====================================================================
def batch_process_csv_sync(interval=SEND_INTERVAL):
    init_failed_log()
    existing_ids = load_existing_ids()
    sent_records = load_sent_records()

    round_no = 1
    while True:
        print(f"\n{'=' * 60}")
        print(f"🚀 [同步模式] 第 {round_no} 批开始处理")
        print(f"{'=' * 60}")

        pending = collect_pending_items(existing_ids=existing_ids, sent_records=sent_records)
        if not pending:
            print("🎉 没有需要发送的物品了，全部完成！")
            break

        print(f"本批将发送 {len(pending)} 条物品。")
        send_batch_sync(pending, interval=interval)

        sent_records = load_sent_records()
        round_no += 1

        user_input = input("\n⏸️ 本批发送完成。是否继续下一批？(y/n): ").strip().lower()
        if user_input not in ("y", "yes", "是", "继续"):
            print("👋 用户选择停止，程序退出。")
            break


async def batch_process_csv_async(interval=SEND_INTERVAL):
    init_failed_log()
    existing_ids = load_existing_ids()
    sent_records = load_sent_records()

    round_no = 1
    while True:
        print(f"\n{'=' * 60}")
        print(f"🚀 [异步模式] 第 {round_no} 批开始处理")
        print(f"{'=' * 60}")

        pending = collect_pending_items(existing_ids=existing_ids, sent_records=sent_records)
        if not pending:
            print("🎉 没有需要发送的物品了，全部完成！")
            break

        print(f"本批将发送 {len(pending)} 条物品。")
        await send_batch_async(pending, interval=interval)

        sent_records = load_sent_records()
        round_no += 1

        user_input = input("\n⏸️ 本批发送完成。是否继续下一批？(y/n): ").strip().lower()
        if user_input not in ("y", "yes", "是", "继续"):
            print("👋 用户选择停止，程序退出。")
            break


def batch_process_csv(interval=SEND_INTERVAL):
    if USE_ASYNC:
        asyncio.run(batch_process_csv_async(interval=interval))
    else:
        batch_process_csv_sync(interval=interval)


if __name__ == "__main__":
    batch_process_csv(interval=11)