#!/usr/bin/env python3
"""
Skeleton training entry for query-rewrite LoRA fine-tuning.

This file is intentionally lightweight: it documents the expected training
interface and keeps the project story concrete even before full infra is added.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train query-rewrite LoRA model")
    parser.add_argument("--train-file", default="data/ft/rewrite_train.jsonl")
    parser.add_argument("--dev-file", default="data/ft/rewrite_dev.jsonl")
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--output-dir", default="artifacts/ft/rewrite-lora")
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    print("=" * 70)
    print("Query Rewrite LoRA Training Skeleton")
    print("=" * 70)
    print(f"train file : {args.train_file}")
    print(f"dev file   : {args.dev_file}")
    print(f"base model : {args.model}")
    print(f"output dir : {args.output_dir}")
    print(f"lora config: r={args.lora_r}, alpha={args.lora_alpha}")
    print(f"epochs     : {args.epochs}")
    print(f"batch size : {args.batch_size}")
    print()
    print("Next implementation steps:")
    print("1. load base model + tokenizer")
    print("2. convert JSONL rows into instruction-format samples")
    print("3. attach LoRA adapters")
    print("4. train on rewrite_train.jsonl and validate on rewrite_dev.jsonl")
    print("5. save adapters to artifacts/ft/rewrite-lora")
    print()
    print("This script is a project scaffold, not a fake claim of completed FT training.")

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()
