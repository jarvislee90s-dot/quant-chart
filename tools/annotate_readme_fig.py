# -*- coding: utf-8 -*-
"""在 README 效果图上绘制红色圈号①–⑩，生成图例标注版。

用法: python tools/annotate_readme_fig.py
输入: docs/images/basis_zones_example.png
输出: docs/images/basis_zones_annotated.png
坐标与 README「图例说明」小节的编号一一对应，改坐标后重跑即可再生成。
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "images" / "basis_zones_example.png"
DST = ROOT / "docs" / "images" / "basis_zones_annotated.png"

# (编号, x, y, 备注) —— 圈心像素坐标，基于 1600x900 版式
MARKS = [
    (1, 640, 402, "分钟收盘价线（深蓝）"),
    (2, 505, 468, "日内均价线（橙虚线）"),
    (3, 150, 655, "贴水面积（红/绿，右轴）"),
    (4, 272, 543, "每日贴水最低倒三角"),
    (5, 590, 540, "击球区矩形"),
    (6, 1248, 553, "区内触发线（墨绿虚线）"),
    (7, 312, 350, "现价基准线（灰虚线）"),
    (8, 1170, 445, "低点连线+价差涨幅标注（紫）"),
    (9, 700, 790, "日期行"),
    (10, 1455, 400, "右侧双轴（贴水点/贴水率%）"),
]

R = 20          # 圈半径
FONT_SIZE = 22


def main():
    img = Image.open(SRC).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("msyhbd.ttc", FONT_SIZE)      # 微软雅黑 Bold
    except OSError:
        font = ImageFont.truetype("arialbd.ttf", FONT_SIZE)
    for no, x, y, _ in MARKS:
        draw.ellipse([x - R, y - R, x + R, y + R],
                     fill=(214, 48, 60, 255), outline="white", width=3)
        bbox = draw.textbbox((0, 0), str(no), font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x - w / 2 - bbox[0], y - h / 2 - bbox[1]), str(no),
                  fill="white", font=font)
    img.save(DST)
    print("saved:", DST)


if __name__ == "__main__":
    main()
