"""
Async batch summarization service via LiteLLM proxy.

Summarizes note sections using a local LLM (e.g., Qwen3.5-35B-A3B MoE)
running on Mac Studio via LM Studio + LiteLLM proxy.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from ..utils.langfuse_trace import create_trace, start_generation

if TYPE_CHECKING:
    from ..types.section import SectionData

logger = logging.getLogger(__name__)

# LM Studio direct (bypass LiteLLM — needed for chat_template_kwargs passthrough)
DEFAULT_LM_STUDIO_URL = "http://mac-studio.local:1234/v1"
DEFAULT_LM_STUDIO_KEY = "lm-studio"
DEFAULT_MODEL = "qwen3.5-9b"
DEFAULT_MIN_TOKENS = 200
# Qwen3.5 uses ~800-1000 tokens for internal reasoning even with enable_thinking=false
# The actual summary is ~50-100 tokens, but we need headroom for the thinking overhead
DEFAULT_MAX_SUMMARY_TOKENS = 2000


async def summarize_section(
    section: "SectionData",
    client: AsyncOpenAI,
    model: str = DEFAULT_MODEL,
    max_summary_tokens: int = DEFAULT_MAX_SUMMARY_TOKENS,
    temperature: float = 0.5,
    enable_thinking: bool = False,
) -> str:
    """Summarize a single section via LLM.

    Args:
        temperature: Sampling temperature (0.0-1.0). Lower = more deterministic.
        enable_thinking: Whether to allow internal reasoning (uses ~900 extra tokens).

    Returns the summary text, or empty string on failure.
    """
    context = f"Section: {section.heading_path}" if section.heading_path else "Note section"

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_summary_tokens,
        temperature=temperature,
        extra_body={"chat_template_kwargs": {"enable_thinking": enable_thinking}},
        messages=[
            {
                "role": "system",
                "content": "You are a concise note summarizer. Output only the summary, no preamble.",
            },
            {
                "role": "user",
                "content": f"Summarize this note section in 1-2 sentences.\nContext: {context}\n\n{section.raw_text}",
            },
        ],
    )
    content = response.choices[0].message.content or ""
    return content.strip()


async def summarize_sections_batch(
    sections: list["SectionData"],
    *,
    model: str = DEFAULT_MODEL,
    proxy_url: str = DEFAULT_LM_STUDIO_URL,
    proxy_key: str = DEFAULT_LM_STUDIO_KEY,
    concurrency: int = 3,
    min_tokens: int = DEFAULT_MIN_TOKENS,
    delay_between_batches: float = 0.5,
    progress_callback: object | None = None,
) -> list["SectionData"]:
    """Summarize sections in parallel with bounded concurrency.

    Sections under `min_tokens` are skipped (summary stays None).

    Args:
        sections: List of SectionData to summarize (modified in place).
        model: LLM model name for summarization.
        proxy_url: LiteLLM proxy base URL.
        proxy_key: LiteLLM API key.
        concurrency: Max parallel LLM calls.
        min_tokens: Skip sections under this token count.
        delay_between_batches: Seconds between batches (rate limiting).
        progress_callback: Optional rich.progress Task for progress updates.
            Must have an `advance(1)` method.

    Returns:
        The same list with .summary populated for sections that were summarized.
    """
    client = AsyncOpenAI(base_url=proxy_url, api_key=proxy_key)
    semaphore = asyncio.Semaphore(concurrency)

    to_summarize = [s for s in sections if s.token_count >= min_tokens]
    skipped = len(sections) - len(to_summarize)
    logger.info(
        "Summarizing %d sections (skipping %d < %d tokens), concurrency=%d",
        len(to_summarize),
        skipped,
        min_tokens,
        concurrency,
    )

    # Langfuse: parent trace for the batch (no-op if not configured)
    batch_trace_ctx = create_trace(
        "summarize_batch",
        metadata={"total": len(sections), "to_summarize": len(to_summarize), "model": model},
    )
    if batch_trace_ctx:
        batch_trace_ctx.__enter__()

    async def _summarize_one(section: "SectionData") -> None:
        async with semaphore:
            try:
                section.summary = await summarize_section(section, client, model)
                logger.debug("Summarized: %s (%d tokens)", section.section_id, section.token_count)
                # Langfuse: record generation
                if batch_trace_ctx and section.summary:
                    gen = start_generation(
                        "summarize_section",
                        model=model,
                        input=section.raw_text[:500],
                        output=section.summary,
                        metadata={"section_id": section.section_id, "token_count": section.token_count},
                    )
                    if gen:
                        gen.__enter__()
                        gen.__exit__(None, None, None)
            except Exception as e:
                logger.warning("Summarization failed for %s: %s", section.section_id, e)
                section.summary = None
            if progress_callback is not None:
                progress_callback.advance(1)

    # Process in batches to allow rate limit delays
    batch_size = concurrency * 2
    for i in range(0, len(to_summarize), batch_size):
        batch = to_summarize[i : i + batch_size]
        await asyncio.gather(*[_summarize_one(s) for s in batch])
        if i + batch_size < len(to_summarize) and delay_between_batches > 0:
            await asyncio.sleep(delay_between_batches)

    summarized = sum(1 for s in sections if s.summary is not None)
    logger.info("Summarization complete: %d/%d sections summarized", summarized, len(sections))

    if batch_trace_ctx:
        try:
            batch_trace_ctx.__exit__(None, None, None)
        except Exception:
            pass

    await client.close()
    return sections
