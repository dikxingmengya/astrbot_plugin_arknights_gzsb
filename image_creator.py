import asyncio
import os
import uuid
from io import BytesIO
import math
import logging

import aiohttp
from PIL import Image as PILImage, ImageFont, ImageDraw

SCALE = 2
MAX_COLS = 6

BASE_CHAR_WIDTH = 90
BASE_CHAR_HEIGHT = 120
BASE_PADDING = 12
BASE_ROW_GAP = 20
BASE_TAG_PADDING = 8
BASE_TAG_GAP = 6
BASE_LABEL_AREA_WIDTH = 160

CHAR_WIDTH = int(BASE_CHAR_WIDTH * SCALE)
CHAR_HEIGHT = int(BASE_CHAR_HEIGHT * SCALE)
PADDING = int(BASE_PADDING * SCALE)
ROW_GAP = int(BASE_ROW_GAP * SCALE)
TAG_PADDING = int(BASE_TAG_PADDING * SCALE)
TAG_GAP = int(BASE_TAG_GAP * SCALE)
LABEL_AREA_WIDTH = int(BASE_LABEL_AREA_WIDTH * SCALE)

BG = "#F5F7FA"
CARD_BG = "#FFFFFF"
TEXT_COLOR = "#1E293B"
TAG_BG = "#1e293b"
TAG_TEXT_COLOR = "#ffffff"
LIMITED_GREEN = "#22C55E"
SEP_COLOR = "#d0d5dd"

RARITY_COLORS = {
    1: "#9e9e9e",
    2: "#a5d6a7",
    3: "#90caf9",
    4: "#b39ddb",
    5: "#ffe082",
    6: "#ffb74d",
}

async def generate_result_image(entries, font_path, font_small_path) -> str:
    # 下载图片资源（省略，同前）
    url_set = set()
    for entry in entries:
        for char in entry["characters"]:
            if char["avatar"]: url_set.add(char["avatar"])
            if char["rarity"]: url_set.add(char["rarity"])
            if char["profession"]: url_set.add(char["profession"])

    img_cache = {}
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in url_set:
            async def fetch(u):
                try:
                    async with session.get(u, timeout=5) as resp:
                        data = await resp.read()
                        return u, PILImage.open(BytesIO(data)).convert("RGBA")
                except Exception:
                    return u, None
            tasks.append(fetch(url))
        results = await asyncio.gather(*tasks)
        for url, img in results:
            if img:
                img_cache[url] = img

    loop = asyncio.get_running_loop()
    temp_path = await loop.run_in_executor(
        None, _draw_image, entries, img_cache, font_path, font_small_path
    )
    return temp_path

# ---------- 文本换行辅助函数 ----------
def _wrap_text(text, font, max_width):
    lines = []
    remaining = text
    while remaining:
        low, high = 0, len(remaining)
        best = 0
        while low <= high:
            mid = (low + high) // 2
            if font.getbbox(remaining[:mid])[2] <= max_width:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        if best == 0:
            best = 1
        lines.append(remaining[:best].rstrip())
        remaining = remaining[best:].lstrip()
    return lines


def _draw_image(entries, img_cache, font_path, font_small_path):
    logger = logging.getLogger("astrbot")

    # ---------- 字体 ----------
    try:
        font_label = ImageFont.truetype(font_path, int(18 * SCALE))
        font_name  = ImageFont.truetype(font_small_path, int(17 * SCALE))  # 加大名字字体
    except Exception:
        logger.warning("字体加载失败，使用默认字体（可能无中文）")
        font_label = ImageFont.load_default()
        font_name  = ImageFont.load_default()

    # ---------- 预计算各组尺寸 ----------
    group_heights = []
    group_label_heights = []
    group_card_rows = []
    group_chars = []

    for entry in entries:
        tags = entry["tag_set"]
        chars = entry["characters"]

        # ★ 按稀有度降序排序
        chars = sorted(chars, key=lambda c: c.get("star", 0), reverse=True)
        group_chars.append(chars)

        # 标签区域高度（不变）
        tag_total_h = 0
        for tag in tags:
            lines = _wrap_text(tag, font_label, LABEL_AREA_WIDTH - TAG_PADDING * 2)
            line_height = font_label.size + 2
            tag_h = line_height * len(lines) + TAG_PADDING * 2
            tag_total_h += tag_h + TAG_GAP
        if tag_total_h > 0:
            tag_total_h -= TAG_GAP
        group_label_heights.append(tag_total_h)

        # 卡片区域高度（使用排序后的 chars）
        char_count = len(chars)
        rows = math.ceil(char_count / MAX_COLS) if char_count > 0 else 1
        group_card_rows.append(rows)
        card_area_h = rows * (CHAR_HEIGHT + PADDING)
        group_heights.append(max(tag_total_h, card_area_h))

    # ---------- 计算画布尺寸 ----------
    total_height = PADDING
    for i, h in enumerate(group_heights):
        total_height += h
        if i < len(group_heights) - 1:
            total_height += ROW_GAP  # 组间间隙
    total_height += PADDING

    grid_width = MAX_COLS * (CHAR_WIDTH + PADDING) + PADDING
    img_width = PADDING + LABEL_AREA_WIDTH + PADDING + grid_width + PADDING

    img = PILImage.new("RGB", (img_width, total_height), BG)
    draw = ImageDraw.Draw(img)

    # ---------- 逐组绘制 ----------
    y_cursor = PADDING
    for idx_entry, entry in enumerate(entries):
        tags = entry["tag_set"]
        chars = group_chars[idx_entry]
        rows = group_card_rows[idx_entry]
        group_h = group_heights[idx_entry]
        label_h = group_label_heights[idx_entry]
        card_area_h = rows * (CHAR_HEIGHT + PADDING)

        # 组间分割线（居中于 ROW_GAP 中）
        if idx_entry > 0:
            half_gap = (ROW_GAP - 2) // 2
            sep_y = y_cursor + half_gap
            draw.line(
                [(PADDING, sep_y), (img_width - PADDING, sep_y)],
                fill=SEP_COLOR, width=2
            )
            y_cursor += ROW_GAP

        # --- 左侧标签区域（垂直居中） ---
        label_x = PADDING
        label_y = y_cursor + (group_h - label_h) // 2
        temp_y = label_y
        for tag in tags:
            lines = _wrap_text(tag, font_label, LABEL_AREA_WIDTH - TAG_PADDING * 2)
            line_height = font_label.size + 2
            tag_h = line_height * len(lines) + TAG_PADDING * 2

            draw.rounded_rectangle(
                [label_x, temp_y, label_x + LABEL_AREA_WIDTH, temp_y + tag_h],
                radius=int(6 * SCALE),
                fill=TAG_BG
            )

            text_x = label_x + LABEL_AREA_WIDTH // 2
            text_y = temp_y + TAG_PADDING
            for line in lines:
                draw.text(
                    (text_x, text_y + line_height // 2),
                    line,
                    fill=TAG_TEXT_COLOR,
                    font=font_label,
                    anchor="mm"
                )
                text_y += line_height
            temp_y += tag_h + TAG_GAP

        # --- 干员网格区域（垂直居中） ---
        grid_left = PADDING + LABEL_AREA_WIDTH + PADDING
        grid_top = y_cursor + (group_h - card_area_h) // 2

        for idx_char, char in enumerate(chars):
            col = idx_char % MAX_COLS
            row = idx_char // MAX_COLS
            x = grid_left + col * (CHAR_WIDTH + PADDING)
            y = grid_top + row * (CHAR_HEIGHT + PADDING)

            # 稀有度背景色
            star = char.get("star", 3)
            card_bg_color = RARITY_COLORS.get(star, CARD_BG)
            card_rect = [x, y, x + CHAR_WIDTH, y + CHAR_HEIGHT]
            draw.rounded_rectangle(card_rect, radius=int(12 * SCALE), fill=card_bg_color)

            # ----- 头像及左上/右下图标（重叠绘制）-----
            avatar_url = char.get("avatar")
            avatar_img = img_cache.get(avatar_url) if avatar_url else None
            if avatar_img:
                avatar_size = int(64 * SCALE)
                avatar_img = avatar_img.resize((avatar_size, avatar_size), PILImage.Resampling.LANCZOS)
                avatar_x = x + (CHAR_WIDTH - avatar_size) // 2
                avatar_y = y + int(6 * SCALE)
                # 粘贴头像
                try:
                    img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
                except Exception:
                    pass

                # 职业图标（左上角）
                prof_url = char.get("profession")
                if prof_url and (prof_img := img_cache.get(prof_url)):
                    prof_size = int(20 * SCALE)
                    prof_img = prof_img.resize((prof_size, prof_size), PILImage.Resampling.LANCZOS)
                    prof_offset = int(2 * SCALE)
                    try:
                        img.paste(prof_img,
                                  (avatar_x + prof_offset, avatar_y + prof_offset),
                                  prof_img)
                    except Exception:
                        pass

                # 星级图标（右下角）
                rarity_url = char.get("rarity")
                if rarity_url and (rar_img := img_cache.get(rarity_url)):
                    orig_w, orig_h = rar_img.size
                    target_h = int(12 * SCALE)
                    target_w = int(orig_w * (target_h / orig_h))
                    rar_img = rar_img.resize((target_w, target_h), PILImage.Resampling.LANCZOS)
                    rar_offset = int(2 * SCALE)
                    try:
                        img.paste(rar_img,
                                  (avatar_x + avatar_size - target_w - rar_offset,
                                   avatar_y + avatar_size - target_h - rar_offset),
                                  rar_img)
                    except Exception:
                        pass

            # ----- 名字（加大字体）-----
            name = str(char.get("name", ""))
            name_y = y + int(82 * SCALE)  # 微调下移了一点，适应更大字体
            max_text_w = CHAR_WIDTH - int(8 * SCALE)
            # 截断过长名字
            while font_name.getbbox(name)[2] > max_text_w and len(name) > 1:
                name = name[:-1]
            if len(name) < len(str(char.get("name", ""))):
                name = name[:-1] + "…"
            draw.text(
                (x + CHAR_WIDTH // 2, name_y),
                name,
                fill=TEXT_COLOR,
                font=font_name,
                anchor="ma"
            )

            # 限定标记 TODO
            # if star == 1:
            #     badge_w = int(18 * SCALE)
            #     badge_h = int(16 * SCALE)
            #     badge_x = x + CHAR_WIDTH - badge_w - int(4 * SCALE)
            #     badge_y = y + int(4 * SCALE)
            #     draw.rounded_rectangle(
            #         [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            #         radius=int(6 * SCALE),
            #         fill=LIMITED_GREEN,
            #     )
            #     draw.text(
            #         (badge_x + badge_w // 2, badge_y + badge_h // 2),
            #         "限",
            #         fill="white",
            #         font=font_name,
            #         anchor="mm",
            #     )

        y_cursor += group_h

    # ---------- 保存图片 ----------
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"recruitment_result_{uuid.UUID}.png")
    img.save(temp_path, "PNG", optimize=True)
    return temp_path