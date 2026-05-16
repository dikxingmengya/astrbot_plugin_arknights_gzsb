import json
import itertools
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

            for tag in tags:
                if tag not in self.tag_to_operators:
                    self.tag_to_operators[tag] = set()
                # 将该干员加入该词条的集合中
                self.tag_to_operators[tag].update(char_set)

        print(f"[预处理完成] 已索引 {len(self.tag_to_operators)} 个词条。")



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

        # 1. 生成所有非空子集组合
        all_combos = []
        for r in range(1, len(tags) + 1):
            all_combos.extend(itertools.combinations(tags, r))

        # 2. 初步计算每个组合的交集干员
        combo_operators = {}
        for combo in all_combos:
            ops = None
            for tag in combo:
                if tag in self.tag_to_operators:
                    if ops is None:
                        ops = self.tag_to_operators[tag].copy()
                    else:
                        ops &= self.tag_to_operators[tag]
                else:
                    ops = set()
                    break
            combo_operators[combo] = ops or set()

        # 3. 按组合长度降序排序，分配干员（长组合优先）
        sorted_combos = sorted(combo_operators.keys(), key=lambda c: len(c), reverse=True)
        assigned_global = set()  # 已经被分配的干员
        result_map = {}

        for combo in sorted_combos:
            # 当前组合可用干员 = 交集 - 已被更长组合分配的
            available = combo_operators[combo] - assigned_global
            # 更新全局已分配集合
            assigned_global.update(available)
            # 排序后存入结果
            result_map[combo] = sorted(available)

        # 如果需要按某种顺序返回（例如保持原标签顺序的某种组合），可以进一步整理
        # 这里直接返回
        return result_map