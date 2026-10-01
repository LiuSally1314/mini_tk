# ============================================
# OCR识别模块 - 截图后直接OCR
# ============================================

import os
import time
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from rapidocr import RapidOCR

from device import DeviceManager
from config_loader import load_config


class OCRManager:
    """OCR识别管理器"""

    def __init__(self, device: DeviceManager, config: Dict[str, Any] = None):
        self.device = device
        self.config = config or {}
        self.engine = RapidOCR()

    def ocr_image(self, image_path: str) -> Dict[str, Any]:
        """对图片进行OCR识别"""
        if not os.path.exists(image_path):
            print(f"❌ 图片不存在: {image_path}")
            return {"texts": [], "texts_with_boxes": [], "raw": None}

        try:
            result = self.engine(image_path)

            if result and result.txts:
                # 使用备份路径进行可视化，避免覆盖原图
                base, ext = os.path.splitext(image_path)
                img_url = f"{base}_vis{ext}"

                result.vis(img_url)
                print(f"🖼️ 可视化标注图已保存: {img_url}")

                text_list = list(result.txts)
                text_with_boxes = []
                for txt, box in zip(result.txts, result.boxes):
                    coords = [[int(round(p[0])), int(round(p[1]))] for p in box.tolist()]
                    cx = int(round(sum(c[0] for c in coords) / 4))
                    cy = int(round(sum(c[1] for c in coords) / 4))
                    text_with_boxes.append([txt, [cx, cy]] + coords)

                return {
                    "texts": text_list,
                    "texts_with_boxes": text_with_boxes,
                    "raw": result,
                    "vis_image": img_url
                }
            else:
                print("⚠️ OCR未识别到任何文字")
                return {"texts": [], "texts_with_boxes": [], "raw": result}

        except Exception as e:
            print(f"❌ OCR识别失败: {e}")
            return {"texts": [], "texts_with_boxes": [], "raw": None}

    def screenshot_and_ocr(self,
                           save_dir: str = "截屏",
                           filename: str = None,
                           json_output: str = "ocr_result.json") -> Optional[Dict[str, Any]]:
        """截图并OCR识别，结果写入JSON"""
        print("\n" + "=" * 50)
        print("📸 步骤1: 截取屏幕")
        print("=" * 50)

        screenshot_path = self._take_screenshot(save_dir, filename)

        if not screenshot_path:
            print("❌ 截图失败，无法进行OCR识别")
            return None

        print("\n" + "=" * 50)
        print("🔍 步骤2: OCR识别")
        print("=" * 50)

        ocr_result = self.ocr_image(screenshot_path)

        abs_image_path = os.path.abspath(screenshot_path)

        # 截图文件名（含扩展名），作为查询结果的 key
        image_filename = os.path.basename(screenshot_path)

        if not ocr_result["texts"]:
            print("⚠️ OCR未识别到任何文字")
            result = {
                "screenshot_path": screenshot_path,
                "image_path": abs_image_path,
                "image_filename": image_filename,
                "texts": [],
                "texts_with_boxes": []
            }
            self._save_json(json_output, result)
            return result

        self._print_ocr_result(ocr_result)

        result = {
            "screenshot_path": screenshot_path,
            "image_path": abs_image_path,
            "image_filename": image_filename,
            "texts": ocr_result["texts"],
            "texts_with_boxes": ocr_result["texts_with_boxes"]
        }

        self._save_json(json_output, result)
        return result

    def _save_json(self, json_path: str, result: Dict[str, Any]):
        """保存OCR结果到JSON（按 image_filename 追加累积，不覆盖历史记录）"""
        try:
            json_dir = os.path.dirname(json_path)
            if json_dir:
                os.makedirs(json_dir, exist_ok=True)

            image_filename = result.get("image_filename", "")

            # 读取已有数据
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        data = {}
                except Exception:
                    data = {}
            else:
                data = {}

            # 以截图文件名为 key 追加/更新
            data[image_filename] = {
                "image_path": result.get("image_path", ""),
                "screenshot_path": result.get("screenshot_path", ""),
                "texts": result.get("texts", []),
                "texts_with_boxes": result.get("texts_with_boxes", [])
            }

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"\n💾 JSON结果已追加保存: {json_path}")
            print(f"   🖼️ 截图 key: 「{image_filename}」")
            print(f"   📄 当前累计记录数: {len(data)}")
            print(f"   📦 文件大小: {os.path.getsize(json_path)} 字节")

        except Exception as e:
            print(f"❌ 保存JSON失败: {e}")

    def _take_screenshot(self, save_dir: str, filename: str = None) -> Optional[str]:
        """执行截图并保存"""
        if not self.device.is_connected():
            print("❌ 设备未连接，无法截屏")
            return None

        try:
            os.makedirs(save_dir, exist_ok=True)

            if filename:
                safe_filename = "".join(c for c in filename if c.isalnum() or c in " _-")
                if not safe_filename:
                    safe_filename = "screenshot"
                final_name = f"{safe_filename}.png"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_name = f"screenshot_{timestamp}.png"

            local_path = os.path.join(save_dir, final_name)

            if os.path.exists(local_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_without_ext = final_name.rsplit('.', 1)[0]
                final_name = f"{name_without_ext}_{timestamp}.png"
                local_path = os.path.join(save_dir, final_name)

            print(f"📸 开始截屏: {final_name}")

            try:
                phone_path = "/sdcard/temp_screenshot.png"
                print(f"  📱 执行手机截屏...")
                self.device.adb_shell(["screencap", "-p", phone_path])
                time.sleep(0.5)

                print(f"  💾 拉取截图到电脑: {local_path}")
                self.device.adb_pull(phone_path, local_path)

                print(f"  🗑️ 删除手机临时截图...")
                self.device.adb_shell(["rm", phone_path])

                print(f"✅ 截屏成功: {local_path}")
                return local_path

            except Exception as e:
                print(f"❌ ADB截屏失败: {e}")
                try:
                    print("  🔄 尝试使用Airtest snapshot方法...")
                    temp_filename = f"temp_snapshot_{int(time.time())}.png"
                    self.device.snapshot(temp_filename)
                    time.sleep(0.5)

                    if os.path.exists(temp_filename):
                        import shutil
                        shutil.move(temp_filename, local_path)
                        print(f"✅ 截屏成功(备用方法): {local_path}")
                        return local_path
                except Exception as e2:
                    print(f"❌ 备用截屏也失败: {e2}")
                    return None

        except Exception as e:
            print(f"❌ 截屏功能出错: {e}")
            return None

    def _print_ocr_result(self, ocr_result: Dict[str, Any]):
        """打印OCR识别结果"""
        texts = ocr_result["texts"]
        texts_with_boxes = ocr_result["texts_with_boxes"]

        print(f"\n📝 共识别到 {len(texts)} 条文字:\n")
        print("=" * 50)
        print("【文字 + 中心坐标 + 四个角坐标 JSON】")
        print("=" * 50)
        print(json.dumps(texts_with_boxes, ensure_ascii=False, indent=2))


# ============================================
# 坐标查询模块
# ============================================

def query_coordinates(texts_with_boxes: List[List[Any]],
                      image_filename: str,
                      query_json_path: str) -> None:
    """
    交互式查询文字坐标（模糊查询），结果累积保存到 query_result.json

    Args:
        texts_with_boxes: OCR识别结果
        image_filename: 截图文件名（含扩展名），作为第一层 key
        query_json_path: 查询结果 JSON 文件路径
    """
    while True:
        try:
            keyword = input("\n🔍 请输入要查询的文字 (直接回车跳过): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n⚠️ 查询中断")
            return

        if not keyword:
            print("⏭️ 跳过查询")
            return

        # 模糊查询
        matches = [
            item for item in texts_with_boxes
            if keyword in item[0]
        ]

        if not matches:
            print(f"❌ 未找到包含「{keyword}」的文字")
        else:
            print(f"\n✅ 找到 {len(matches)} 条匹配「{keyword}」的记录:")
            for item in matches:
                text = item[0]
                center = item[1]
                print(f"  📌 「{text}」 中心坐标: ({center[0]}, {center[1]})")

            # 保存到 query_result.json
            _save_query_result(image_filename, keyword, matches, query_json_path)

        # 询问是否继续查询
        try:
            again = input("\n❓ 是否继续查询？(y/n, 回车跳过): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n⚠️ 查询中断")
            return

        if again not in ('y', 'yes'):
            print("⏭️ 结束查询")
            return


def _save_query_result(image_filename: str,
                       keyword: str,
                       matches: List[List[Any]],
                       json_path: str) -> None:
    """
    保存查询结果到 query_result.json（追加累积）

    results 每条结构:
      [文字, [中心cx, cy], [[左上x,y], [右上x,y], [右下x,y], [左下x,y]]]
    """
    try:
        json_dir = os.path.dirname(json_path)
        if json_dir:
            os.makedirs(json_dir, exist_ok=True)

        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}
        else:
            data = {}

        if image_filename not in data:
            data[image_filename] = {}

        # matches 中每条 item = [文字, [cx,cy], [x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        # 转成: [文字, [cx,cy], [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]]
        data[image_filename][keyword] = {
            "keyword": keyword,
            "results": [
                [item[0], item[1], [item[2], item[3], item[4], item[5]]]
                for item in matches
            ]
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 查询结果已追加保存: {json_path}")
        print(f"   🖼️ 截图: 「{image_filename}」")
        print(f"   🔑 关键字: 「{keyword}」  ({len(matches)} 条)")

    except Exception as e:
        print(f"❌ 保存查询结果失败: {e}")


# ============================================
# 主程序入口
# ============================================

def main():
    """主函数 - 交互式循环"""
    import logging
    import traceback
    logging.getLogger("airtest").setLevel(logging.CRITICAL)

    config = load_config("config.yaml")

    device_uri = config["device"]["uri"]
    json_output_name = config["output"]["json_filename"]
    query_json_name = config["output"]["query_json_filename"]
    base_dir = config["output"]["base_dir"]

    device = DeviceManager()

    try:
        print("🔗 正在连接设备...")
        print(f"   设备ID: {device_uri}")
        if not device.connect(device_uri):
            print("❌ 设备连接失败，请检查ADB连接")
            return

        ocr_mgr = OCRManager(device, config)

        # 询问子目录
        print("\n" + "=" * 50)
        print("📁 截图保存设置")
        print("=" * 50)
        print(f"基础目录: {base_dir}")
        sub_dir = input(f"请输入子目录 (直接回车使用基础目录): ").strip()

        if sub_dir:
            save_dir = os.path.join(base_dir, sub_dir)
        else:
            save_dir = base_dir

        print(f"✅ 截图将保存到: {save_dir}")

        task_count = 0
        while True:
            task_count += 1
            print("\n" + "=" * 60)
            print(f"🔄 第 {task_count} 次任务")
            print("=" * 60)
            print("命令说明:")
            print("  - 直接回车: 自动生成文件名截图")
            print("  - 输入文件名: 使用该文件名截图")
            print("  - 输入 q / quit / exit: 退出程序")
            print("  - 输入 dir: 修改保存目录")
            print("=" * 60)

            try:
                user_input = input("📝 请输入截图文件名 (回车自动生成, q退出): ").strip()
            except EOFError:
                print("\n⚠️ 检测到 EOF（非交互环境），退出")
                break
            except KeyboardInterrupt:
                print("\n⚠️ 用户 Ctrl+C 中断")
                break

            if user_input.lower() in ('q', 'quit', 'exit'):
                print("\n👋 退出程序")
                break

            if user_input.lower() == 'dir':
                print(f"当前基础目录: {base_dir}")
                new_sub = input(f"请输入新的子目录 (当前: {sub_dir or '(基础目录)'}): ").strip()
                sub_dir = new_sub
                if sub_dir:
                    save_dir = os.path.join(base_dir, sub_dir)
                else:
                    save_dir = base_dir
                print(f"✅ 保存目录已修改为: {save_dir}")
                continue

            filename = user_input if user_input else None

            # JSON 输出路径
            json_output = os.path.join(save_dir, json_output_name)
            query_json_path = os.path.join(save_dir, query_json_name)

            result = ocr_mgr.screenshot_and_ocr(
                save_dir=save_dir,
                filename=filename,
                json_output=json_output
            )

            if result:
                print("\n" + "=" * 50)
                print("✅ 本次任务完成")
                print("=" * 50)
                print(f"📁 截图路径: {result['screenshot_path']}")
                print(f"🖼️ 图片绝对路径: {result['image_path']}")
                print(f"📝 识别文字数: {len(result['texts'])}")
                print(f"💾 JSON已保存: {json_output}")

                if result['texts_with_boxes']:
                    query_coordinates(
                        texts_with_boxes=result['texts_with_boxes'],
                        image_filename=result['image_filename'],
                        query_json_path=query_json_path
                    )

    except Exception as e:
        print("\n" + "!" * 50)
        print(f"❌ 程序异常退出: {e}")
        traceback.print_exc()
        print("!" * 50)
    finally:
        device.disconnect()
        print("📱 设备已断开连接")


if __name__ == "__main__":
    main()