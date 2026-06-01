"""Integration test: real DeepSeek API → full dream pipeline."""

import asyncio
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI

from openclaw_plugins.dreamweaver.config import DreamWeaverConfig
from openclaw_plugins.dreamweaver.self_play import SelfPlayEngine, SelfPlayConfig


class DeepSeekProvider:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    async def generate(self, system_prompt, user_prompt="", *, temperature=0.7, max_tokens=4096):
        resp = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt or "请开始"},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content
        tokens = resp.usage.total_tokens
        return text, tokens


async def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY") or "sk-00ba8f2f08f24f1993c07b1b4e744a80"
    llm = DeepSeekProvider(api_key)

    print("=" * 60)
    print("Test 1: 单轮 Genius 调用")
    print("=" * 60)
    text, tokens = await llm.generate(
        system_prompt="你是创新突破专家。针对以下问题，提出一个激进的解决方案。\n问题：如何用最少的代码重构一个大型 Python 项目？",
        temperature=0.8,
        max_tokens=1024,
    )
    print(f"✓ 响应 ({tokens} tokens):")
    print(text[:300])
    print()

    print("=" * 60)
    print("Test 2: Judge 角色评分 (JSON 解析)")
    print("=" * 60)
    from openclaw_plugins.dreamweaver.self_play import SelfPlayEngine

    judge_prompt = """你是一位公正的专家评委。根据正确性、创新性、实用性、鲁棒性和效率进行 0-10 分综合评分。
问题：用最少的代码重构项目
当前方案：方案A：使用微内核架构拆分模块
历史最佳方案：方案B：在现有代码上增量重构
输出 JSON: {"score_A": .., "score_B": .., "winner": "A"/"B", "reason": "..."}"""

    text, tokens = await llm.generate(
        system_prompt=judge_prompt,
        temperature=0.1,
        max_tokens=512,
    )
    print(f"✓ 响应 ({tokens} tokens):")
    print(text)
    verdict = SelfPlayEngine._parse_judge_response(text)
    print(f"解析结果: A={verdict.score_a}, B={verdict.score_b}, winner={verdict.winner}")
    print()

    print("=" * 60)
    print("Test 3: 完整 3 轮自我对弈 (SelfPlayEngine)")
    print("=" * 60)
    config = SelfPlayConfig(max_iterations=3, convergence_rounds=20, mutation_interval=999)
    engine = SelfPlayEngine(llm, config)
    result = await engine.run("如何用最少的代码重构一个大型 Python 项目？")
    print(f"✓ 完成 {result.total_iterations} 轮")
    print(f"  最佳评分: {result.best_score:.1f}")
    print(f"  结束原因: {result.convergence_reason}")
    print(f"  总日志条数: {len(result.logs)}")
    print(f"  最终方案摘要: {result.final_solution[:200]}...")
    print()

    print("All integration tests passed! 🎉")


if __name__ == "__main__":
    asyncio.run(main())
