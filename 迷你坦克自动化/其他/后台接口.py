import asyncio
import csv
import aiohttp

# 忽略 SSL 证书校验
ssl_context = False

# 失败日志文件名
FAILED_LOG_FILE = "failed_items.csv"


# 初始化失败日志文件（写入表头）
def init_failed_log():
    with open(
        FAILED_LOG_FILE, mode="w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.writer(f)
        writer.writerow(
            ["序号", "名称", "道具代号", "数量", "备注", "响应信息"]
        )


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
    """异步单次发送函数，捕获失败响应并写入文件"""
    headers = {
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
    cookies = {"PHPSESSID": "aiq1md4mhnmpqb4ci1bt01dtf3"}

    payload = {
        "type": type_name,
        "uid": uid,
        "item": item,
        "num": str(num),
        "qu": str(qu),
        "pwd": str(pwd),
        "title": title,
        "content": content,
    }

    try:
        async with session.post(
            url, headers=headers, data=payload, ssl=ssl_context
        ) as response:
            res_text = await response.text()

            # 判断响应中是否包含“不存在”或“错误/失败”的关键词
            # 注意：请根据服务器实际返回的提示词调整关键字（例如："不存在"、"错误"、"fail"、"invalid"等）
            if (
                "不存在" in res_text
                or "失败" in res_text
                or "错误" in res_text
            ):
                print(
                    f"❌ [发送失败] 序号: {seq} | 名称: {name} ({item}) | 响应: {res_text.strip()}"
                )
                log_failure(
                    seq,
                    name,
                    item,
                    num,
                    remark="发送失败",
                    response_msg=res_text.strip(),
                )
            else:
                print(
                    f"✅ [已发送] 序号: {seq} | 名称: {name} ({item}) | 响应: {res_text[:50].strip()}"
                )

    except Exception as e:
        print(f"⚠️ [网络/请求异常] 序号: {seq} | 道具: {item} | 错误: {e}")
        log_failure(
            seq,
            name,
            item,
            num,
            remark="网络异常",
            response_msg=str(e),
        )


def log_failure(seq, name, item, num, remark, response_msg):
    """将失败记录追加写入到 CSV 文件中"""
    with open(
        FAILED_LOG_FILE, mode="a", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.writer(f)
        writer.writerow([seq, name, item, num, remark, response_msg])


async def batch_process_csv(csv_path="后台物品.csv", interval=1.0):
    """读取 CSV 文件并逐行遍历发送，每条请求间隔 1 秒"""
    init_failed_log()  # 初始化失败日志文件表头

    async with aiohttp.ClientSession() as session:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            tasks = []
            for row in reader:
                seq = row.get("序号", "")
                name = row.get("名称", "")
                num = row.get("数量", "")

                item_code = f"props_p{seq}"

                print(
                    f"正在处理序号 [{seq}]: 名称={name}, 代号={item_code}, 数量={num}"
                )

                # 触发异步任务并保存引用
                task = asyncio.create_task(
                    send_gm_query_async(
                        session,
                        seq=seq,
                        name=name,
                        item=item_code,
                        num=num,
                    )
                )
                tasks.append(task)

                # 间隔 1 秒
                await asyncio.sleep(interval)

            # 等待所有后台任务执行完毕
            if tasks:
                await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(batch_process_csv())