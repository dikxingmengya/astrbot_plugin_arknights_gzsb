import numpy as np
from rapidocr_onnxruntime import RapidOCR
from PIL import Image

def is_game_landscape(image: Image.Image, min_ratio: float = 1.4, max_ratio: float = 2.4) -> bool:
    """判断是否为符合长宽比的图片"""
    width, height = image.size
    ratio = width / height
    return min_ratio <= ratio <= max_ratio

def cut(image: Image.Image, cut_left: float = 0.3, cut_right: float = 0.7,
        cut_upper: float = 0.5, cut_lower: float = 0.67) -> Image.Image:
    """对图片进行初步剪切"""
    width, height = image.size
    left = int(width * cut_left)
    right = int(width * cut_right)
    upper = int(height * cut_upper)
    lower = int(height * cut_lower)
    return image.crop((left, upper, right, lower))

class OcrEngine:
    def __init__(self, tags: list[str]):
        self.tags = tags
        self.ocr_engine = RapidOCR(
            use_cls=False,            # 关闭方向分类
            use_dilation=False,       # 关闭膨胀算法
            min_box_size=15,          # 忽略过小文本块
            # 删除了不存在的 max_box_size 参数
        )

    def ocr(self, image: Image.Image) -> list[str]:
        # 将 PIL.Image 转为 numpy 数组并转换为 BGR 格式（RapidOCR 期望 BGR）
        img_np = np.array(image.convert('RGB'))          # 先得到 RGB 数组
        img_bgr = img_np[:, :, ::-1]                     # RGB -> BGR

        result = self.ocr_engine(img_bgr)                # 现在可以正确传入了
        tags = []
        if result[0]:
            for box, text, score in result[0]:
                if text.strip() in self.tags:
                    tags.append(text.strip())
        return tags