import json
import logging
import os
from io import BytesIO
from typing import Dict

import aiohttp
from PIL import Image as PILImage
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import Image, Plain
import astrbot.api.message_components as Comp

from .image_creator import generate_result_image
from .image_ocr import OcrEngine, is_game_landscape, cut
from .recruitment_calculator import OperatorFinder


@register("gzsb", "Drest", "基于 Ocr 的《明日方舟》公开招募自动识别插件。", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        self.config = config
        self.logger = logging.getLogger("astrbot")

        self.output_format = config.get("output_format", "normal")
        self.enable_vlm = config.get("enable_vlm", True)
        self.character_path = config.get("character_path", "characters.json")
        self.operators_path = config.get("operators_path", "operators.json")
        self.auto_detection = config.get("auto_detection", False)
        self.min_ratio = config.get("min_ratio", 1.4)
        self.max_ratio = config.get("max_ratio", 2.4)
        self.cut_left = config.get("cut_left", 0.3)
        self.cut_right = config.get("cut_right", 0.7)
        self.cut_upper = config.get("cut_upper", 0.5)
        self.cut_lower = config.get("cut_lower", 0.67)

        self.marcher: OperatorFinder | None = None
        self.ocr_engine: OcrEngine | None = None
        self.tags: list[str] = []
        self.characters: Dict[str, dict]  = {}

        self.ai_message: str = """识别图中公开招募的词条
1. 使用["词条1", "词条2", ...] 格式输出
2. 如果出现错误，输出 []
3. 请不要输出除了 [] 以外的内容"""

        # 确定插件所在目录（用于默认字体路径）
        plugin_dir = os.path.dirname(os.path.abspath(__file__))

        # 字体路径：优先使用配置文件指定的路径，否则使用插件目录下的 "font.ttf"
        self.font_path = self.config.get("font_path", os.path.join(plugin_dir, "fonts/font.ttf"))
        self.font_small_path = self.config.get("font_small_path", os.path.join(plugin_dir, "fonts/small.ttf"))

    async def initialize(self):
        # 解析 operators.json 路径
        if not os.path.isabs(self.operators_path):
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            self.operators_path = os.path.join(plugin_dir, self.operators_path)
        if not self.operators_path:
            self.logger.error("未配置 tag 文件路径")
            return
        try:
            self.logger.info(f"tag 文件路径: {self.operators_path}")
            if not os.path.exists(self.operators_path):
                self.logger.error(f"tag 文件不存在: {self.operators_path}")
                return
        except FileNotFoundError:
            self.logger.error(f"tag 文件不存在: {self.operators_path}")
            return

        # 解析 characters.json 路径（可选）
        if not os.path.isabs(self.character_path):
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            self.character_path = os.path.join(plugin_dir, self.character_path)
        try:
            if self.character_path and not os.path.exists(self.character_path):
                self.logger.warning(f"角色文件不存在: {self.character_path}，部分功能可能受限")
        except FileNotFoundError:
            pass

        if os.path.exists(self.character_path):
            with open(self.character_path, 'r', encoding='utf-8') as f:
                char_data = json.load(f)
                self.characters = char_data.get("characters", {})

        # 读取所有标签
        with open(self.operators_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            for operator in data["operators"]:
                if len(operator["tags"]) == 1:
                    self.tags.append(operator["tags"][0])

        # 初始化匹配器与 OCR 引擎
        self.marcher = OperatorFinder(self.operators_path)
        self.ocr_engine = OcrEngine(self.tags)

    async def download_image(self, img: str):
        # noinspection PyBroadException
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(img, timeout=10) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
                    return PILImage.open(BytesIO(data)).convert("RGB")
        except Exception:
            self.logger.exception("下载图片异常")
            return None

    async def get_provider_id(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        return await self.context.get_current_chat_provider_id(umo=umo)

    # noinspection PyBroadException
    async def handle_vlm(self, event: AstrMessageEvent, image_url: str) -> list:
        try:
            result = await self.context.llm_generate(
                chat_provider_id=await self.get_provider_id(event),
                prompt=self.ai_message,
                image_urls=[image_url],
            )
            if not result:
                return []
            try:
                return json.loads(result)
            except json.decoder.JSONDecodeError:
                return []
        except Exception:
            self.logger.exception("VLM 识别异常")
            return []

    async def handle_tags(self, event: AstrMessageEvent, tags: list[str]):
        """处理词条"""
        self.logger.info(f"处理词条: {str(list(tags))}")
        match self.output_format:
            case "normal":
                output_format = "normal"
            case "all":
                output_format = "all"
            case _:
                output_format = "normal"

        result = self.marcher.find(tags)

        entries = []
        for tag_set, char_names in result.items():
            chars = []
            for name in char_names:
                info = self.characters.get(name, {})

                if output_format == "normal" and 2 <= info.get("star", 0) <= 4:
                    continue

                chars.append({
                    "name": name,
                    "star": info.get("star", 0),
                    "avatar": info.get("avatar", ""),
                    "profession": info.get("profession", ""),
                    "rarity": info.get("rarity", "")
                })
            if not len(chars):
                continue
            entries.append({
                "tag_set": tag_set,
                "characters": chars
            })


        if not len(entries):
            yield event.plain_result(f"没有符合输出条件({output_format})的词条组合")
            return

        # 生成合成图片
        image_path = await generate_result_image(entries, self.font_path, self.font_small_path)

        # 构建消息链
        chain = [
            Comp.Plain(f'{str(list(tags))}'),
            Comp.Image.fromFileSystem(image_path),
        ]
        yield event.chain_result(chain)

    @filter.command("公招识别", alias={"gzsb"})
    async def on_command(self, event: AstrMessageEvent):
        """公招识别指令"""

        messages = event.get_messages()
        images: list[str] = []
        tags: list[str] = []
        cnt: int = 0

        for message in messages:
            if isinstance(message, Image):
                images.append(message.url)
            elif isinstance(message, Plain):
                # 按空格分割，逐个检查是否在标签集中
                for word in message.text.split():
                    if word in self.tags:
                        tags.append(word)

        # 直接识别的文本优先响应
        if tags:
            async for msg in self.handle_tags(event, tags):
                yield msg

        for img in images:
            cnt += 1
            if self.enable_vlm:
                self.logger.info("调用 vlm 大模型进行图像识别")
                recognized = await self.handle_vlm(event, img)
            else:
                self.logger.info("使用 ocr 进行图像识别")
                pil_image = await self.download_image(img)
                if pil_image:
                    recognized = self.ocr_engine.ocr(pil_image)
                else:
                    recognized = None
            if recognized:
                async for msg in self.handle_tags(event, recognized):
                    yield msg
            elif recognized is None:
                yield event.plain_result(f"图片 [{cnt} / {len(images)}] 识别失败，请重试！")
                self.logger.error(f"图片 [{cnt} / {len(images)}] 识别失败")
            else:
                yield event.plain_result(f"图片 [{cnt} / {len(images)}] 未识别到任何词条。")
                self.logger.error(f"图片 [{cnt} / {len(images)}] 未识别到任何词条")


    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听消息"""

        # 检测自动识别
        if not self.auto_detection:
            return

        messages = event.get_messages()
        if len(messages) != 1:
            return

        image = messages[0]
        if isinstance(image, Image):
            img = image.url
        else:
            return

        # 下载图片
        pil_image = await self.download_image(img)
        if not pil_image:
            return

        # 检测图片是否为横屏游戏截图
        if not is_game_landscape(pil_image, self.min_ratio, self.max_ratio):
            return

        # 裁剪出标签区域
        cut_image = cut(pil_image, self.cut_left, self.cut_right, self.cut_upper, self.cut_lower)

        # OCR 识别
        tags = self.ocr_engine.ocr(cut_image)  # 直接传入 PIL Image，不再用文件路径
        if tags:
            self.logger.info("检测到公开招募图片")
            async for msg in self.handle_tags(event, tags):
                yield msg


    async def terminate(self):
        pass