"""Minimal local debug scripts for trace/review output."""
import asyncio
import json
from pathlib import Path

from src.core.rag_engine import RAGEngine
from src.utils.review import build_review_view


async def main() -> None:
    engine = RAGEngine()
    result = await engine.query("系统支持哪些检索优化能力？")
    review = build_review_view(result)

    out_dir = Path("artifacts/eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "debug_review_sample.json"
    out_file.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
