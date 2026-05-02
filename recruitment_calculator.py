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

    def find(self, tags: List[str]) -> Dict[Tuple[str], List[str]]:
        """
        查找给定词条组合对应的角色。

        Args:
            tags: 字符串列表，例如 ["近卫", "输出", "生存"]

        Returns:
            Dict[Tuple[str], List[str]]: 键为词条组合元组，值为对应干员列表。
        """
        if not tags:
            return {}

        result_map = {}

        # 1. 生成所有可能的组合 (从长度1到长度n)
        # 使用 range(1, len(tags)+1) 生成不同长度的组合
        for r in range(1, len(tags) + 1):
            for combo_tuple in itertools.combinations(tags, r):
                # 2. 对于当前组合，进行集合交集运算
                # 初始化为全集或者第一个词条的集合
                common_operators = None

                for tag in combo_tuple:
                    if tag in self.tag_to_operators:
                        if common_operators is None:
                            common_operators = self.tag_to_operators[tag].copy()
                        else:
                            common_operators &= self.tag_to_operators[tag]  # 集合交集
                    else:
                        # 如果某个词条不存在，该组合结果为空
                        common_operators = set()
                        break

                # 转换为列表，若无结果则为空列表
                operator_list = sorted(list(common_operators)) if common_operators else []

                # 3. 存入结果 (仅当有结果或为了完整性需要包含空结果时)
                # 这里我们只存储有结果的组合，或者你可以根据需求修改
                if operator_list:  # 只存储有干员的组合
                    result_map[combo_tuple] = operator_list
                # else:
                #     result_map[combo_tuple] = [] # 如果需要显示无结果的组合，请取消注释此块

        return result_map