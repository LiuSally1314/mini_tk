import logging

from airtest.core.api import *
from airtest.core.cv import Template
import time

logging.getLogger("airtest").setLevel(logging.INFO)
logging.getLogger("airtest.core.android.adb").setLevel(logging.WARNING)
# 连接设备
connect_device("Android:///192.168.31.33:45665")

image = r"/Users/mac/Documents/learn/pythonProject/mini_tk/迷你坦克自动化/pic/红色箭头.png"

for i in range(10):
    pos = loop_find(Template(image, target_pos=5))
    print(f"[{i + 1}/10] 返回坐标: {pos}")

    if i < 9:  # 最后一次不用等
        time.sleep(3)
    # loop_find
# 断开
device().disconnect()