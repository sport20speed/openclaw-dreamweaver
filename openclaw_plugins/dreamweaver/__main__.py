#!/usr/bin/env python3
"""DreamWeaver CLI — run, serve, and manage dreams.

Usage::

    python -m openclaw_plugins.dreamweaver run --motif "如何优化项目"
    python -m openclaw_plugins.dreamweaver run                   # 自动选题
    python -m openclaw_plugins.dreamweaver init                  # 生成配置
    python -m openclaw_plugins.dreamweaver serve                 # 启动 API
    python -m openclaw_plugins.dreamweaver history               # 查看历史
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from openai import AsyncOpenAI


def _get_api_key() -> str:
    """Fetch DeepSeek API key from env or .env."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip("\"'")
    return ""


def _read_env(key: str) -> str:
    """Read any key from .env file."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip("\"'")
    return ""


class DeepSeekProvider:
    """Real DeepSeek LLM provider (used by SelfPlayEngine)."""

    def __init__(self, api_key: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str = "",
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[str, int]:
        resp = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt or "请开始"},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return text, tokens


# ── Sub-commands ───────────────────────────────────────────────────


async def cmd_run(args: argparse.Namespace) -> None:
    """Run a dream with optional motif."""
    api_key = _get_api_key()
    if not api_key:
        print("❌ 未找到 DEEPSEEK_API_KEY，请设置环境变量或创建 .env 文件")
        print("   echo DEEPSEEK_API_KEY=sk-xxx > .env")
        sys.exit(1)

    # ── 文件锁：防止重复进程 ──
    lock_path = Path(__file__).parent.parent.parent / "dream.lock"
    if lock_path.exists():
        old_pid = int(lock_path.read_text().strip())
        try:
            os.kill(old_pid, 0)
            print(f"❌ 另一个 dream 正在运行 (PID={old_pid})，请等待完成或删除 dream.lock")
            sys.exit(1)
        except (OSError, ProcessLookupError):
            pass  # 旧进程已死
    lock_path.write_text(str(os.getpid()))

    from .config import DreamWeaverConfig
    from .self_play import SelfPlayConfig, SelfPlayEngine

    config = DreamWeaverConfig(
        max_iterations=args.iterations,
        convergence_rounds=args.convergence,
        mutation_interval=args.mutate_interval,
    )

    llm = DeepSeekProvider(api_key)
    engine = SelfPlayEngine(
        llm,
        SelfPlayConfig(
            max_iterations=config.max_iterations,
            convergence_rounds=config.convergence_rounds,
            mutation_interval=config.mutation_interval,
        ),
    )

    motif = args.motif or "如何提升个人或团队的日常工作效率与创造力？"
    print(f"\n🌙 梦境启动")
    print(f"   母题: {motif}")
    print(f"   最大迭代: {config.max_iterations} 轮")
    print(f"   变异间隔: 每 {config.mutation_interval} 轮\n")

    result = await engine.run(motif)

    print(f"\n✅ 梦境完成")
    print(f"   迭代: {result.total_iterations} 轮")
    print(f"   最佳评分: {result.best_score:.1f}/10")
    print(f"   结束原因: {result.convergence_reason}")
    print(f"\n📝 最终方案摘要:")
    print(f"   {result.final_solution[:500]}...")
    print(f"\n📊 迭代日志: {len(result.logs)} 条")

    # ── 释放锁 ──
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass

    # Save output file
    if args.output:
        out = {
            "motif": result.motif,
            "best_score": result.best_score,
            "total_iterations": result.total_iterations,
            "convergence_reason": result.convergence_reason,
            "final_solution": result.final_solution,
            "logs": [
                {
                    "round": l.round,
                    "role": l.role,
                    "score": l.score,
                    "tokens_used": l.tokens_used,
                }
                for l in result.logs
            ],
        }
        Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"\n💾 结果已保存到 {args.output}")


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI server (synchronous, uvicorn manages its own loop)."""
    try:
        import uvicorn
    except ImportError:
        print("❌ 需要安装 uvicorn: pip install uvicorn")
        sys.exit(1)

    from contextlib import asynccontextmanager
    from .config import DreamWeaverConfig
    from .database import DreamRepository
    from .dream_service import DreamService
    from .api import create_router
    from .llm_providers import get_provider
    from fastapi import FastAPI

    # Provider selection: LOCAL_MODEL env → Ollama, else DeepSeek
    use_local = bool(os.environ.get("LOCAL_MODEL") or _read_env("LOCAL_MODEL"))
    local_model = os.environ.get("LOCAL_MODEL") or _read_env("LOCAL_MODEL") or "qwen3.5:9b"
    api_key = _get_api_key()
    if not use_local and not api_key:
        print("❌ 未找到 DEEPSEEK_API_KEY，设置 LOCAL_MODEL=qwen3.5:9b 使用本地模型")
        sys.exit(1)

    cloud_model = os.environ.get("CLOUD_MODEL") or _read_env("CLOUD_MODEL") or "deepseek-chat"
    judge_model = os.environ.get("JUDGE_MODEL") or _read_env("JUDGE_MODEL") or "deepseek-chat"
    llm = get_provider(use_local=use_local, local_model=local_model, cloud_model=cloud_model, api_key=api_key)
    judge_llm = get_provider(use_local=False, cloud_model=judge_model, api_key=api_key)  # Judge always cloud
    model_label = f"Ollama {local_model}" if use_local else cloud_model
    # Load persisted config BEFORE creating LLM providers
    config = DreamWeaverConfig()
    import json as _json
    _cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "dream_config.json")
    _cfg_path = os.path.abspath(_cfg_path)
    if os.path.exists(_cfg_path):
        try:
            with open(_cfg_path, encoding="utf-8") as _f:
                saved = _json.loads(_f.read())
            for k, v in saved.items():
                if hasattr(config, k):
                    setattr(config, k, v)
            print(f"📋 载入已保存配置: {_cfg_path}")
        except Exception:
            pass

    # Override LLM selection with persisted config
    if config.cloud_enabled and config.cloud_model:
        cloud_model = config.cloud_model
        judge_model = config.judge_model
        use_local = False
    if config.local_model:
        local_model = config.local_model

    print(f"🧠 模型: {model_label} | Judge: {judge_model}")
    repo = DreamRepository(args.db or "dreamweaver.db")

    # Obsidian writer setup
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    dream_folder = os.environ.get("DREAM_FOLDER", "Dreams")
    from .obsidian_writer import ObsidianWriter, ObsidianWriterConfig

    @asynccontextmanager
    async def lifespan(app):
        await repo.init()

        # Obsidian writer (if vault configured)
        writer = None
        if vault_path and os.path.isdir(vault_path):
            from .obsidian_writer import VaultFileSystem
            class _FS:
                async def write_note(self, note):
                    p = Path(vault_path) / note.path
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(note.content, encoding="utf-8")
                    return str(p)
                async def note_exists(self, title):
                    target = Path(vault_path) / f"{title}.md"
                    return str(target) if target.exists() else None
                async def create_stub(self, title):
                    p = Path(vault_path) / f"{title}.md"
                    p.write_text(f"# {title}\n\n存根笔记 — 由 DreamWeaver 自动创建。\n", encoding="utf-8")
                    return str(p)
            writer = ObsidianWriter(fs=_FS(), config=ObsidianWriterConfig(
                vault_path=vault_path, dream_folder=dream_folder))
            print(f"📓 Obsidian sync: {vault_path}/{dream_folder}")

        from .meta_learner import MetaLearner
        _meta_learner = MetaLearner(args.db or "dreamweaver.db")
        svc = DreamService(config, llm, judge_llm=judge_llm)
        router = create_router(svc, repo, meta_learner=_meta_learner)
        app.include_router(router)

        # M1: Meta-collector for learning from past dreams
        from .meta_collector import MetaCollector
        _meta_collector = MetaCollector(repo._get_conn())

        async def _save(r):
            from datetime import datetime
            import hashlib
            did = datetime.now().strftime("%Y%m%d-") + hashlib.md5(r.motif.encode()).hexdigest()[:8]
            await repo.save_result(did, r)
            if writer:
                await writer.write(r)
            # M1: collect meta-episode
            try:
                from .self_play import SelfPlayConfig
                cfg = SelfPlayConfig()
                _meta_collector.collect(did, r, cfg, motif_source="manual")
            except Exception:
                pass
        svc.on_dream_complete = _save

        await svc.start()
        yield
        await svc.stop()
        await repo.close()

    app = FastAPI(title="DreamWeaver", version="1.0.0", lifespan=lifespan)

    print(f"\n🌙 DreamWeaver API server starting on {args.host}:{args.port}")
    print(f"   Docs: http://{args.host}:{args.port}/docs")
    print(f"   Status: http://{args.host}:{args.port}/dream/status\n")
    uvicorn.run(app, host=args.host, port=args.port)


async def cmd_init(args: argparse.Namespace) -> None:
    """Create a default .env and config file."""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        print(f"⚠️  .env 已存在: {env_path}")
        return

    env_path.write_text(
        "# DreamWeaver 配置\n"
        f"DEEPSEEK_API_KEY={args.key or 'sk-your-deepseek-api-key-here'}\n"
    )
    print(f"✅ 已创建 {env_path}")
    print("   编辑该文件填入你的 DeepSeek API key")


async def cmd_history(args: argparse.Namespace) -> None:
    """Query dream history from the database."""
    from .database import DreamRepository

    path = args.db or "dreamweaver.db"
    if not Path(path).exists():
        print("❌ 数据库不存在，尚未运行过任何梦境")
        return

    repo = DreamRepository(path)
    await repo.init()
    dreams = await repo.list_dreams(limit=args.limit, offset=args.offset, sort_by=args.sort)
    total = await repo.count_dreams()

    print(f"\n📋 梦境历史 (共 {total} 条)")
    print(f"{'ID':<20} {'评分':<6} {'迭代':<6} {'状态':<12} {'母题'}")
    print("-" * 80)
    for d in dreams:
        score = f"{d.get('best_score', 0):.1f}" if d.get("best_score") else "-"
        motif = (d.get("motif", "") or "")[:50]
        print(f"{d['id']:<20} {score:<6} {d.get('iterations', 0):<6} {d.get('status', ''):<12} {motif}")
    await repo.close()


# ── Parser ─────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dreamweaver",
        description="🌙 DreamWeaver — 梦境自主进化引擎",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="运行一次梦境")
    p_run.add_argument("--motif", "-m", default="", help="母题（留空自动生成）")
    p_run.add_argument("--iterations", "-i", type=int, default=5, help="最大迭代轮数")
    p_run.add_argument("--convergence", type=int, default=10, help="收敛判定轮数")
    p_run.add_argument("--mutate-interval", type=int, default=3, help="变异器触发间隔")
    p_run.add_argument("--output", "-o", default="", help="结果输出 JSON 路径")
    p_run.set_defaults(func=cmd_run)

    # serve
    p_serve = sub.add_parser("serve", help="启动 API 服务器")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", "-p", type=int, default=8000)
    p_serve.add_argument("--db", default="dreamweaver.db")
    p_serve.set_defaults(func=cmd_serve)

    # init
    p_init = sub.add_parser("init", help="初始化 .env 配置")
    p_init.add_argument("--key", "-k", default="", help="DeepSeek API Key")
    p_init.set_defaults(func=cmd_init)

    # history
    p_hist = sub.add_parser("history", help="查看梦境历史")
    p_hist.add_argument("--limit", type=int, default=20)
    p_hist.add_argument("--offset", type=int, default=0)
    p_hist.add_argument("--sort", default="created_at", choices=["created_at", "score", "iterations"])
    p_hist.add_argument("--db", default="dreamweaver.db")
    p_hist.set_defaults(func=cmd_history)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    func = args.func
    if func is cmd_serve:
        func(args)  # sync — uvicorn manages its own event loop
    else:
        asyncio.run(func(args))


if __name__ == "__main__":
    main()
