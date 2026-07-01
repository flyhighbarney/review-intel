"""LLM client with caching, rate-limiting, and cost tracking."""

from __future__ import annotations
import asyncio
import hashlib
import json
import time
from pathlib import Path

import anthropic
import diskcache

from config import settings, CACHE_DIR

_cache = diskcache.Cache(str(CACHE_DIR / "llm_cache"))
_cost_log: list[dict] = []
_semaphore: asyncio.Semaphore | None = None

PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
}


def _cache_key(model: str, messages: list, system: str) -> str:
    blob = json.dumps({"model": model, "messages": messages, "system": system}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def get_total_cost() -> float:
    return sum(e["cost_usd"] for e in _cost_log)


def get_cost_breakdown() -> dict:
    by_model: dict[str, float] = {}
    for e in _cost_log:
        by_model[e["model"]] = by_model.get(e["model"], 0) + e["cost_usd"]
    return {"total_usd": get_total_cost(), "by_model": by_model, "calls": len(_cost_log)}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


async def classify_review(
    review_text: str,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.0,
) -> dict:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_llm)

    model = model or settings.classification_model
    messages = [{"role": "user", "content": user_prompt}]
    key = _cache_key(model, messages, system_prompt)

    cached = _cache.get(key)
    if cached is not None:
        return cached

    budget_remaining = settings.llm_budget_usd - get_total_cost()
    if budget_remaining <= 0:
        raise RuntimeError(f"LLM budget exhausted: ${get_total_cost():.2f} spent of ${settings.llm_budget_usd}")

    async with _semaphore:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )

    text = resp.content[0].text
    cost = _estimate_cost(model, resp.usage.input_tokens, resp.usage.output_tokens)
    _cost_log.append({
        "model": model,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cost_usd": cost,
        "timestamp": time.time(),
    })

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
        else:
            result = {"raw_response": text, "parse_error": True}

    _cache.set(key, result)
    return result


async def generate_text(
    prompt: str,
    system: str = "",
    model: str | None = None,
    max_tokens: int = 2000,
) -> str:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_llm)

    model = model or settings.recommendation_model
    messages = [{"role": "user", "content": prompt}]
    key = _cache_key(model, messages, system)

    cached = _cache.get(key)
    if cached is not None:
        return cached

    async with _semaphore:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.3,
            system=system or "You are a senior product analyst at SharkNinja.",
            messages=messages,
        )

    text = resp.content[0].text
    cost = _estimate_cost(model, resp.usage.input_tokens, resp.usage.output_tokens)
    _cost_log.append({
        "model": model,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cost_usd": cost,
        "timestamp": time.time(),
    })

    _cache.set(key, text)
    return text
