from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()
img_url = "/Users/mac/Documents/learn/pythonProject/auto_tk/军团贡献V2/截屏/2026-09-06/马云0F-lj00f-2026-09-06.png"

# RapidOCR 标准返回：result (列表), elapse_time (耗时)
result, _ = engine(img_url)

if result:
    # 格式一：纯文字列表
    text_list = [item[1] for item in result]

    # 格式二：文字与四点整数坐标列表
    text_with_boxes = [
        [item[1], [[int(pt[0]), int(pt[1])] for pt in item[0]]]
        for item in result
    ]

    print("格式 1 (仅文字):")
    if text_list:
        print(text_list[0])

    print("\n格式 2 (文字与坐标):")
    print(text_with_boxes)