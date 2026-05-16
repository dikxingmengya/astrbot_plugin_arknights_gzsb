import json
import itertools
import logging
from typing import List, Dict, Set, Tuple
import os

# ================= 配置 =================
JSON_FILE_PATH = "operators.json"  # 请根据实际情况修改路径


# ================= 预处理模块 =================
class OperatorFinder:
    def __init__(self, json_path: str):
        self.json_path = json_path
        # 核心数据结构：反向索引
        # Key: Tag (如 "近卫")
        # Value: Set of Operators (如 {"银灰", "赫拉格"})
        self.tag_to_operators: Dict[str, Set[str]] = {}
        self._load_and_build_index()

    def _load_and_build_index(self):
        """
        私有方法：加载JSON并构建反向索引。
        时间复杂度: O(M), M为所有干员词条的总数量。
        """
        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"未找到文件: {self.json_path}")

        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 遍历每一个词条条目
        for entry in data.get("operators", []):
            tags = entry.get("tags", [])
            characters = entry.get("characters", [])

            # 将干员名转为集合，方便后续交集运算
            char_set = set(characters)
            tags_str = ""
            tags.sort()
            for tag in tags:
                tags_str += f"{tag} "

            self.tag_to_operators[tags_str] = char_set

        logging.getLogger("astrbot").info(f"[预处理完成] 已索引 {len(self.tag_to_operators)} 个词条组。")



    def find(self, tags: List[str]) -> Dict[Tuple[str, ...], List[str]]:
        """
        查找给定词条组合对应的角色。

        Args:
            tags: 字符串列表，例如 ["近卫", "输出", "生存"]

        Returns:
            Dict[Tuple[str], List[str]]: 键为词条组合元组，值为对应干员列表。
        """

        if not tags:
            return {}

        # 生成所有词条组合
        all_combos = []
        for r in range(1, len(tags) + 1):
            all_combos.extend(itertools.combinations(tags, r))

        # 伪 hash 查询词条
        result_map = {}
        for combo in all_combos:
            tags: list[str] = list(combo)
            tags_str = ""
            tags.sort()
            for tag in tags:
                tags_str += f"{tag} "

            result_map[combo] = self.tag_to_operators.get(tags_str) or set()

        return result_map