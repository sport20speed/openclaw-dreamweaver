"""Mutator — injects cross-domain paradigms to force creative leaps."""

from __future__ import annotations

import random

from .base import BaseRole, DreamContext, RoleOutput

# Extended paradigm library (67 cross-domain concepts from the dev diary)
MUTATION_PARADIGMS = [
    # Physics
    "量子隧穿效应", "熵增逆转", "超流体", "拓扑绝缘体", "量子纠错码", "路径积分", "规范场论",
    # Biology
    "水平基因转移", "蚂蚁信息素机制", "免疫系统记忆", "光合作用能量转换", "细胞自噬", "表观遗传",
    "菌根网络（Wood Wide Web）", "胚胎发育的形态发生场",
    # Economics & Game Theory
    "拍卖机制设计", "纳什均衡", "公共物品博弈", "维克里拍卖", "匹配市场理论", "信号博弈",
    # Art & Design
    "负空间（留白美学）", "对位法（音乐）", "散点透视（中国山水画）", "即兴爵士的call-and-response",
    "偶发艺术（Happening）", "极少主义雕塑",
    # Computer Science
    "分形压缩", "拜占庭容错", "零知识证明", "同态加密", "CRDT（无冲突复制数据类型）",
    # Philosophy
    "休谟的归纳问题", "禅宗的公案", "维特根斯坦的语言游戏", "德勒兹的块茎理论",
    # Engineering
    "张力整体结构（Tensegrity）", "被动式太阳能设计",
    # Social Sciences
    "邓巴数字", "破窗效应", "旁观者效应", "六度分隔",
    # Sports & Games
    "巴西柔术的杠杆原理", "围棋的厚势与实地", "扑克中的范围平衡",
    # More Physics
    "超导体的迈斯纳效应", "激光冷却", "量子纠缠",
    # More Bio
    "趋同进化", "拟态", "共生",
    # Abstract / Math
    "哥德尔不完备定理", "混沌理论中的蝴蝶效应", "分形几何的自相似性", "希尔伯特旅馆悖论",
    "莫比乌斯带", "四色定理的证明方法",
    # Chinese Traditional (V1.1 §2.4)
    "周易变卦", "孙子兵法奇正", "中医经络系统", "禅宗不二法门", "道家无为而治",
    "围棋的势与地", "太极的刚柔相济", "水墨画的留白意境",
    # Modern Cross-Discipline
    "复杂适应系统", "博弈论演化均衡", "网络科学的弱连接理论", "涌现现象",
]

# Domain mapping for context-aware paradigm selection (V1.1 §2.4)
DOMAIN_GROUPS = {
    "physics": ["量子隧穿效应", "熵增逆转", "超流体", "量子纠缠", "超导体的迈斯纳效应"],
    "biology": ["水平基因转移", "蚂蚁信息素机制", "共生", "趋同进化", "拟态"],
    "economics": ["纳什均衡", "拍卖机制设计", "公共物品博弈", "破窗效应"],
    "art": ["负空间（留白美学）", "散点透视（中国山水画）", "极少主义雕塑"],
    "chinese": ["周易变卦", "孙子兵法奇正", "中医经络系统", "禅宗不二法门", "道家无为而治"],
    "cross": ["复杂适应系统", "博弈论演化均衡", "网络科学的弱连接理论", "涌现现象"],
}

MUTATOR_PROMPT_V2 = """你需要引入一个完全意想不到的跨领域范式来重构当前方案。

例如：现在假设我们只能使用"蚂蚁信息素机制"来解决这个软件工程问题。或者：用"维特根斯坦的语言游戏"来重新理解这个管理难题。

**要求：**
- 必须从指定的跨领域范式中提取核心机制（不是表面的类比，而是深层结构）。
- 给出一个异化但逻辑通顺的新方案原型，保留原始问题要解决的核心矛盾。
- 方案不需要完全可执行——重要的是打开全新的思考方向。

当前方案：{solution}
变异方向：{random_paradigm}"""


class MutatorRole(BaseRole):
    role_name = "mutator"
    temperature = 1.0

    @staticmethod
    def _pick_paradigm(context: DreamContext) -> str:
        """Context-aware paradigm selection (V1.1 §2.4).
        Classify solution domain, then pick from a DIFFERENT domain group.
        """
        # Quick domain classification based on keywords in the current solution
        sol = context.current_solution.lower()
        if any(w in sol for w in ["代码", "程序", "算法", "架构", "api"]):
            avoid = ["physics", "biology", "chinese", "cross"]
            candidates = sum([DOMAIN_GROUPS[d] for d in avoid if d in DOMAIN_GROUPS], [])
        elif any(w in sol for w in ["市场", "投资", "交易", "套利", "收益"]):
            avoid = ["biology", "art", "chinese"]
            candidates = sum([DOMAIN_GROUPS[d] for d in avoid if d in DOMAIN_GROUPS], [])
        elif any(w in sol for w in ["设计", "美学", "艺术", "创意", "音乐"]):
            avoid = ["physics", "economics", "cross"]
            candidates = sum([DOMAIN_GROUPS[d] for d in avoid if d in DOMAIN_GROUPS], [])
        else:
            candidates = MUTATION_PARADIGMS
        return context.mutation_paradigm or random.choice(candidates) if candidates else random.choice(MUTATION_PARADIGMS)

    async def execute(self, context: DreamContext) -> RoleOutput:
        paradigm = self._pick_paradigm(context)
        prompt = MUTATOR_PROMPT_V2.format(
            motif=context.motif,
            solution=context.current_solution,
            random_paradigm=paradigm,
        )
        text, tokens = await self._call(prompt)
        return RoleOutput(
            role="mutator",
            content=text,
            prompt=prompt,
            tokens_used=tokens,
            temperature=self.temperature,
            model="deepseek-v4-flash",
            metadata={"paradigm": paradigm},
        )
