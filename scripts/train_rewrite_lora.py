#!/usr/bin/env python3
"""
Query Rewrite LoRA training entry.

Goals:
- provide a real runnable training path instead of a pure scaffold
- support a lightweight CPU smoke run for local validation
- support a more formal LoRA configuration for later GPU training

Examples:

# 1) Dry-run config check
python scripts/train_rewrite_lora.py --dry-run

# 2) CPU smoke run (tiny model, very small steps)
python scripts/train_rewrite_lora.py --profile smoke-cpu

# 3) Formal LoRA run (for a stronger local/GPU environment)
python scripts/train_rewrite_lora.py --profile formal \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --output-dir artifacts/ft/rewrite-lora-qwen
"""
from __future__ import annotations

import argparse
import json
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class TrainConfig:
    profile: str
    train_file: str
    dev_file: str
    test_file: str
    model: str
    output_dir: str
    max_source_length: int
    max_target_length: int
    learning_rate: float
    epochs: int
    batch_size: int
    grad_accum_steps: int
    max_steps: int
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    seed: int
    use_bf16: bool
    use_fp16: bool
    save_steps: int
    eval_steps: int
    logging_steps: int


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def format_prompt(query: str) -> str:
    return (
        "你是一个面向检索优化的 Query Rewrite 助手。"
        "请保持原始意图不变，把用户问题改写成更适合检索的表达，不要编造事实。\n\n"
        f"原始问题：{query.strip()}\n"
        "改写结果："
    )


def build_examples(rows: List[Dict]) -> List[Dict[str, str]]:
    examples = []
    for row in rows:
        query = row.get("query", "").strip()
        rewrite = row.get("rewrite", "").strip()
        if not query or not rewrite:
            continue
        examples.append(
            {
                "id": row.get("id", "unknown"),
                "prompt": format_prompt(query),
                "target": rewrite,
            }
        )
    return examples


def resolve_config(args: argparse.Namespace) -> TrainConfig:
    if args.profile == "smoke-cpu":
        defaults = dict(
            model="sshleifer/tiny-gpt2",
            max_source_length=128,
            max_target_length=64,
            learning_rate=5e-4,
            epochs=1,
            batch_size=1,
            grad_accum_steps=1,
            max_steps=12,
            lora_r=4,
            lora_alpha=8,
            lora_dropout=0.05,
            use_bf16=False,
            use_fp16=False,
            save_steps=50,
            eval_steps=50,
            logging_steps=1,
            output_dir="artifacts/ft/rewrite-lora-smoke",
        )
    else:
        defaults = dict(
            model="Qwen/Qwen2.5-1.5B-Instruct",
            max_source_length=256,
            max_target_length=128,
            learning_rate=2e-4,
            epochs=3,
            batch_size=2,
            grad_accum_steps=4,
            max_steps=-1,
            lora_r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            use_bf16=True,
            use_fp16=False,
            save_steps=100,
            eval_steps=100,
            logging_steps=10,
            output_dir="artifacts/ft/rewrite-lora",
        )

    return TrainConfig(
        profile=args.profile,
        train_file=args.train_file,
        dev_file=args.dev_file,
        test_file=args.test_file,
        model=args.model or defaults["model"],
        output_dir=args.output_dir or defaults["output_dir"],
        max_source_length=args.max_source_length or defaults["max_source_length"],
        max_target_length=args.max_target_length or defaults["max_target_length"],
        learning_rate=args.learning_rate or defaults["learning_rate"],
        epochs=args.epochs or defaults["epochs"],
        batch_size=args.batch_size or defaults["batch_size"],
        grad_accum_steps=args.grad_accum_steps or defaults["grad_accum_steps"],
        max_steps=args.max_steps if args.max_steps is not None else defaults["max_steps"],
        lora_r=args.lora_r or defaults["lora_r"],
        lora_alpha=args.lora_alpha or defaults["lora_alpha"],
        lora_dropout=args.lora_dropout if args.lora_dropout is not None else defaults["lora_dropout"],
        seed=args.seed,
        use_bf16=args.use_bf16 if args.use_bf16 is not None else defaults["use_bf16"],
        use_fp16=args.use_fp16 if args.use_fp16 is not None else defaults["use_fp16"],
        save_steps=args.save_steps or defaults["save_steps"],
        eval_steps=args.eval_steps or defaults["eval_steps"],
        logging_steps=args.logging_steps or defaults["logging_steps"],
    )


def set_seed(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


class RewriteTorchDataset:
    def __init__(self, examples: List[Dict[str, str]], tokenizer, max_source_length: int, max_target_length: int):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_source_length = max_source_length
        self.max_target_length = max_target_length

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> Dict[str, List[int]]:
        example = self.examples[idx]
        prompt_ids = self.tokenizer(
            example["prompt"],
            truncation=True,
            max_length=self.max_source_length,
            add_special_tokens=True,
        )["input_ids"]
        target_ids = self.tokenizer(
            example["target"],
            truncation=True,
            max_length=self.max_target_length,
            add_special_tokens=False,
        )["input_ids"]

        input_ids = prompt_ids + target_ids + [self.tokenizer.eos_token_id]
        labels = [-100] * len(prompt_ids) + target_ids + [self.tokenizer.eos_token_id]
        attention_mask = [1] * len(input_ids)
        return {
            "input_ids": input_ids,
            "labels": labels,
            "attention_mask": attention_mask,
        }


class Seq2SeqLikeCollator:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __call__(self, features: List[Dict]):
        import torch

        max_len = max(len(f["input_ids"]) for f in features)
        pad_id = self.tokenizer.pad_token_id
        batch = {"input_ids": [], "labels": [], "attention_mask": []}
        for f in features:
            pad_len = max_len - len(f["input_ids"])
            batch["input_ids"].append(f["input_ids"] + [pad_id] * pad_len)
            batch["labels"].append(f["labels"] + [-100] * pad_len)
            batch["attention_mask"].append(f["attention_mask"] + [0] * pad_len)
        return {k: torch.tensor(v) for k, v in batch.items()}


def write_metadata(config: TrainConfig, train_examples: List[Dict], dev_examples: List[Dict], test_examples: List[Dict]) -> None:
    out_dir = ROOT / config.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "config": asdict(config),
        "dataset_sizes": {
            "train": len(train_examples),
            "dev": len(dev_examples),
            "test": len(test_examples),
        },
        "note": "Generated by train_rewrite_lora.py",
    }
    (out_dir / "run_config.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def print_plan(config: TrainConfig, train_examples: List[Dict], dev_examples: List[Dict], test_examples: List[Dict]) -> None:
    print("=" * 72)
    print("Query Rewrite LoRA Training")
    print("=" * 72)
    print(f"profile        : {config.profile}")
    print(f"train file     : {config.train_file}")
    print(f"dev file       : {config.dev_file}")
    print(f"test file      : {config.test_file}")
    print(f"base model     : {config.model}")
    print(f"output dir     : {config.output_dir}")
    print(f"dataset sizes  : train={len(train_examples)}, dev={len(dev_examples)}, test={len(test_examples)}")
    print(f"lora config    : r={config.lora_r}, alpha={config.lora_alpha}, dropout={config.lora_dropout}")
    print(f"train config   : epochs={config.epochs}, batch={config.batch_size}, grad_accum={config.grad_accum_steps}, max_steps={config.max_steps}")
    print(f"precision      : bf16={config.use_bf16}, fp16={config.use_fp16}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train query-rewrite LoRA model")
    parser.add_argument("--profile", choices=["smoke-cpu", "formal"], default="smoke-cpu")
    parser.add_argument("--train-file", default="data/ft/rewrite_train.jsonl")
    parser.add_argument("--dev-file", default="data/ft/rewrite_dev.jsonl")
    parser.add_argument("--test-file", default="data/ft/rewrite_test.jsonl")
    parser.add_argument("--model")
    parser.add_argument("--output-dir")
    parser.add_argument("--max-source-length", type=int)
    parser.add_argument("--max-target-length", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--grad-accum-steps", type=int)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--lora-r", type=int)
    parser.add_argument("--lora-alpha", type=int)
    parser.add_argument("--lora-dropout", type=float)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use-bf16", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--use-fp16", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--save-steps", type=int)
    parser.add_argument("--eval-steps", type=int)
    parser.add_argument("--logging-steps", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = resolve_config(args)
    set_seed(config.seed)

    train_rows = load_jsonl(ROOT / config.train_file)
    dev_rows = load_jsonl(ROOT / config.dev_file)
    test_rows = load_jsonl(ROOT / config.test_file)
    train_examples = build_examples(train_rows)
    dev_examples = build_examples(dev_rows)
    test_examples = build_examples(test_rows)

    write_metadata(config, train_examples, dev_examples, test_examples)
    print_plan(config, train_examples, dev_examples, test_examples)

    if args.dry_run:
        print("\nDry-run only. Config and dataset metadata have been written.")
        return

    try:
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
    except Exception as exc:
        print("\nMissing training dependencies.")
        print("Please install requirements-train.txt before running an actual LoRA job.")
        print(f"Import error: {type(exc).__name__}: {exc}")
        return

    tokenizer = AutoTokenizer.from_pretrained(config.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = None
    if config.use_bf16 and torch.cuda.is_available():
        dtype = torch.bfloat16
    elif config.use_fp16 and torch.cuda.is_available():
        dtype = torch.float16

    model = AutoModelForCausalLM.from_pretrained(
        config.model,
        trust_remote_code=True,
        torch_dtype=dtype,
    )

    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    try:
        model = get_peft_model(model, lora_config)
    except Exception:
        # Fallback for smaller models such as tiny-gpt2 used in smoke runs.
        fallback = LoraConfig(
            r=config.lora_r,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=["c_attn", "c_proj"],
        )
        model = get_peft_model(model, fallback)

    train_dataset = RewriteTorchDataset(train_examples, tokenizer, config.max_source_length, config.max_target_length)
    eval_dataset = RewriteTorchDataset(dev_examples, tokenizer, config.max_source_length, config.max_target_length)
    collator = Seq2SeqLikeCollator(tokenizer)

    output_dir = str(ROOT / config.output_dir)
    training_args = TrainingArguments(
        output_dir=output_dir,
        overwrite_output_dir=True,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        gradient_accumulation_steps=config.grad_accum_steps,
        num_train_epochs=config.epochs,
        learning_rate=config.learning_rate,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        eval_steps=config.eval_steps,
        evaluation_strategy="steps" if len(eval_dataset) > 0 else "no",
        save_strategy="steps",
        bf16=config.use_bf16 and torch.cuda.is_available(),
        fp16=config.use_fp16 and torch.cuda.is_available(),
        report_to=[],
        max_steps=config.max_steps,
        remove_unused_columns=False,
        seed=config.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset if len(eval_dataset) > 0 else None,
        data_collator=collator,
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    summary = {
        "status": "completed",
        "profile": config.profile,
        "model": config.model,
        "output_dir": config.output_dir,
        "train_examples": len(train_examples),
        "dev_examples": len(dev_examples),
        "test_examples": len(test_examples),
    }
    (ROOT / config.output_dir / "train_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nTraining finished.")
    print(f"Adapters and tokenizer saved to: {config.output_dir}")


if __name__ == "__main__":
    main()
