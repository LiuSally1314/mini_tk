from rapidocr import RapidOCR

engine = RapidOCR()
img_url = "/Users/mac/Documents/learn/pythonProject/auto_tk/军团贡献V2/截屏/2026-09-06/马云0F-lj00f-2026-09-06.png"

result = engine(img_url)

if result and result.txts:
    # 格式一：纯文本列表 [文字, 文字]
    text_list = list(result.txts)

    # 格式二：带坐标的列表 [[文字, 坐标], [文字, 坐标]]
    # box 格式为 [[x1, y1], [x2, y2], [x3, y3], [x4, y4]] 四点坐标（整数）
    text_with_boxes = [
        [txt, [[int(x), int(y)] for x, y in box.tolist()]]
        for txt, box in zip(result.txts, result.boxes)
    ]

    print("格式 1 (仅文字):")
    print(text_list[0])

    print("\n格式 2 (文字与坐标):")
    print(text_with_boxes)

result.vis(img_url)