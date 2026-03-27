#!/usr/bin/env python
"""LinkedIn AI Post Creator -- standalone script.

Replicates the manifest_samples/linkedin_ai_post_v2 workflow using direct
API calls via LiteLLM.  No orchestrator, no YAML, no framework.

Usage:
    python scripts/linkedin_ai_post.py
    python scripts/linkedin_ai_post.py --output-dir ./my_posts
    python scripts/linkedin_ai_post.py --no-save

Requires: PERPLEXITY_API_KEY, OPENAI_API_KEY, MISTRAL_API_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from litellm import acompletion

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REVISION_THRESHOLD = 8.0


# ── Prompts ──────────────────────────────────────────────────────────────────

RESEARCH_PROMPT = """\
Find the most compelling AI story from the past 7 days (today is {today}).

Search for: "AI news {month} {year}" OR "artificial intelligence announcement" \
OR "LLM model release {month} {year}" OR "AI agent announcement {year}"

Rules:
- AI must be the central subject, not tangential
- Prefer stories from the past 48 hours
- Prefer stories with real user/business impact
- Reject incremental updates, prefer genuine surprises

For the top story, provide:
1. Headline (specific, include AI tech/company name)
2. Publication date
3. Key facts (2-3 sentences with specific details)
4. Primary source URL
5. 2-3 related AI stories or trends that connect to this one
6. One surprising or counterintuitive fact
7. Specific numbers, people, or technical details"""

DEEP_RESEARCH_PROMPT = """\
Research deeper details on the most significant AI development from the past 7 days.

Search for: "new AI model launched {month} {year}" OR "machine learning breakthrough {month} {year}" \
OR "AI company news {month} {year}"

Find for the top story:
1. Specific numbers (users, dollars, percentages, benchmarks)
2. Named individuals involved (CEOs, researchers, engineers)
3. Technical AI details (model architecture, capabilities, benchmarks)
4. Historical context (what came before, how we got here)
5. Competitor responses or parallel moves"""

SELECT_BRIEF_PROMPT = """\
You have two research passes. Synthesize them into one clear brief for a LinkedIn writer.

RESEARCH PASS 1:
{research}

RESEARCH PASS 2:
{deep_research}

Select the single best AI story and produce a writer brief:

Output as JSON:
{{
  "headline": "specific headline with AI tech/company",
  "source_url": "https://...",
  "publication_date": "YYYY-MM-DD",
  "key_facts": ["fact1 with specifics", "fact2", "fact3"],
  "surprising_detail": "one counterintuitive thing",
  "related_trends": ["trend1", "trend2"],
  "technical_details": "specific AI tech details",
  "people_involved": ["person and role"],
  "why_it_matters": "one sentence",
  "angle_suggestion": "suggested angle for the post"
}}

If the two passes found different stories, pick whichever is more recent and impactful."""

DRAFT_PROMPT = """\
Write a LinkedIn post about this AI story.

WRITER BRIEF:
{brief}

Requirements:
- 300-400 words
- Must mention the AI technology and company by name
- Must reference specific details from the story
- Must be anchored to the actual news event -- not generic AI commentary
- Have a clear point of view
- Open with the most interesting detail, not a setup
- End with something that makes people want to respond
- Vary sentence length
- Sound like you're telling a smart friend about something that caught your attention"""

EVALUATE_PROMPT = """\
Evaluate this LinkedIn post draft.

WRITER BRIEF (for reference):
{brief}

DRAFT:
{draft}

Score each 1-10:
1. AI TOPIC FOCUS -- AI tech named? Company named? Story-anchored?
2. AUTHENTICITY -- sounds human? any AI-generated cliches?
3. SPECIFICITY -- concrete details vs vague claims?
4. ENGAGEMENT -- would someone comment?
5. CLARITY -- clear point of view?

Check for these red flags (each found = -2):
"In today's world", "In an era where", "It's not X, it's Y", "Here's the thing:",
"Let's dive in", "Let's unpack this", "At the end of the day", "Game-changer",
"This changes everything", rhetorical question opener, 3+ sentences starting the same way

Output as JSON:
{{
  "ai_focus_score": 0,
  "authenticity_score": 0,
  "specificity_score": 0,
  "engagement_score": 0,
  "clarity_score": 0,
  "overall_score": 0,
  "red_flags_found": ["flag1"],
  "topic_drift": false,
  "revision_priorities": ["issue1", "issue2"],
  "ready": true
}}"""

REVISE_PROMPT = """\
Revise this LinkedIn post based on the evaluation.

WRITER BRIEF:
{brief}

CURRENT DRAFT:
{draft}

EVALUATION:
{evaluation}

Fix the revision priorities identified. Remove any red flags. Stay anchored to the AI story.
Keep what's working. Stay under 400 words.

Output the revised draft only."""

FINALIZE_PROMPT = """\
Output the final, ready-to-post LinkedIn post.

LATEST DRAFT:
{revised}

{original}

If a revised version exists, use it. Otherwise use the original draft.
Apply any final polish. Output only the post text."""

HASHTAGS_PROMPT = """\
Generate 3-5 hashtags for this LinkedIn post about AI.

POST:
{post}

Mix broad (#AI) with specific tags. Avoid oversaturated generic tags. Max 5.

Output as JSON:
{{
  "hashtags": ["#AI", "#LLMs"],
  "rationale": "brief explanation"
}}"""

IMAGE_PROMPT = """\
Create an image prompt for a LinkedIn post visual that accompanies this AI story post.

POST:
{post}

WRITER BRIEF (for AI story context):
{brief}

Requirements:
- Create one professional image prompt that works with any image generator (DALL-E, midjourney, Flux)
- Style: modern, professional, tech-forward but not cliched
- Avoid: robots with glowing eyes, brains with circuit boards, Matrix code, stock photo cliches
- Include: color palette, composition, mood/lighting, camera angle notes

Output as JSON:
{{
  "prompt": "Full detailed prompt text",
  "style": "one-line style description",
  "color_palette": ["color1", "color2", "color3"],
  "composition": "composition notes",
  "aspect_ratio": "16:9",
  "negative_prompt": "things to avoid"
}}"""

# ── System prompts ────────────────────────────────────────────────────────────

RESEARCHER_SYSTEM = "You are a research assistant. Find current, specific information. Return facts with sources when possible. Be concise and accurate."

ANALYST_SYSTEM = "You are a content analyst. Evaluate writing quality, authenticity, and engagement potential. Be specific in your feedback. Score on 1-10 scales with justification."

WRITER_SYSTEM = """\
You are a LinkedIn content writer who sounds like a real human.

ANTI-CLICHE RULES - Never use:
- "In today's world" / "In an era where" / "In our increasingly X world"
- "It's not X, it's Y" pattern
- "The real question is..." / "Here's the thing:" / "Let's be clear:"
- Starting with "Look,"
- "What this means for you:" / "The bottom line:"
- "Picture this" / "Imagine a world where"
- "Let's dive in" / "Let's unpack this" / "Unpacking"
- "At the end of the day" / "Game-changer" / "This changes everything"
- Rhetorical question as opener
- More than 2 em-dashes
- "Moreover" / "Furthermore" / "In addition"
- "In conclusion" / "To summarize" / "The takeaway"
- 3+ sentences starting the same way
- Vague phrases without specifics
- "The implications are profound" or similar drama

WRITING STYLE:
- Start mid-thought, not with setup
- Use specific numbers, names, details
- Vary sentence length - some short, some long
- Sound like you're talking to a smart friend
- Have a clear point of view
- End with something that sticks, not a summary"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_json(text: str) -> dict:
    from json_repair import repair_json

    return json.loads(repair_json(text))


async def call(
    model: str,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 3000,
) -> str:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = await acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# ── Pipeline ──────────────────────────────────────────────────────────────────


async def run(output_dir: str | None, save: bool) -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%B")
    year = now.strftime("%Y")

    log.info("Phase 1: Research (parallel)")

    research, deep_research = await asyncio.gather(
        call(
            "perplexity/sonar",
            RESEARCH_PROMPT.format(today=today, month=month, year=year),
            system=RESEARCHER_SYSTEM,
            temperature=0.3,
            max_tokens=2000,
        ),
        call(
            "perplexity/sonar",
            DEEP_RESEARCH_PROMPT.format(month=month, year=year),
            system=RESEARCHER_SYSTEM,
            temperature=0.3,
            max_tokens=2000,
        ),
    )
    log.info("  research: %s chars", len(research))
    log.info("  deep_research: %s chars", len(deep_research))

    log.info("Phase 2: Select + Draft")

    brief_raw = await call(
        "openai/gpt-4o",
        SELECT_BRIEF_PROMPT.format(research=research, deep_research=deep_research),
        system=ANALYST_SYSTEM,
        temperature=0.4,
        max_tokens=3000,
    )
    brief = _parse_json(brief_raw)
    log.info("  selected: %s", brief.get("headline", "(unknown)"))

    draft = await call(
        "mistral/mistral-small-latest",
        DRAFT_PROMPT.format(brief=json.dumps(brief, indent=2)),
        system=WRITER_SYSTEM,
        temperature=0.8,
        max_tokens=2000,
    )
    log.info("  draft: %s chars", len(draft))

    log.info("Phase 3: Evaluate")

    eval_raw = await call(
        "openai/gpt-4o",
        EVALUATE_PROMPT.format(brief=json.dumps(brief, indent=2), draft=draft),
        system=ANALYST_SYSTEM,
        temperature=0.4,
        max_tokens=3000,
    )
    evaluation = _parse_json(eval_raw)
    score = evaluation.get("overall_score", 0)
    log.info("  overall_score: %s", score)

    revised = None
    if score < REVISION_THRESHOLD:
        log.info("  score < %.1f -- revising", REVISION_THRESHOLD)
        revised = await call(
            "mistral/mistral-small-latest",
            REVISE_PROMPT.format(
                brief=json.dumps(brief, indent=2),
                draft=draft,
                evaluation=json.dumps(evaluation, indent=2),
            ),
            system=WRITER_SYSTEM,
            temperature=0.8,
            max_tokens=2000,
        )
        log.info("  revised: %s chars", len(revised))
    else:
        log.info("  score >= %.1f -- skipping revision", REVISION_THRESHOLD)

    log.info("Phase 4: Final outputs")

    final_post = await call(
        "mistral/mistral-small-latest",
        FINALIZE_PROMPT.format(revised=revised or "(no revision)", original=draft),
        system=WRITER_SYSTEM,
        temperature=0.8,
        max_tokens=2000,
    )
    log.info("  final_post: %s chars", len(final_post))

    hashtags_raw, image_raw = await asyncio.gather(
        call(
            "mistral/mistral-small-latest",
            HASHTAGS_PROMPT.format(post=final_post),
            system=WRITER_SYSTEM,
            temperature=0.8,
            max_tokens=500,
        ),
        call(
            "openai/gpt-4o",
            IMAGE_PROMPT.format(post=final_post, brief=json.dumps(brief, indent=2)),
            system=ANALYST_SYSTEM,
            temperature=0.4,
            max_tokens=1000,
        ),
    )

    hashtags = _parse_json(hashtags_raw)
    image_config = _parse_json(image_raw)

    log.info("  hashtags: %s", hashtags.get("hashtags", []))

    result = {
        "timestamp": now.isoformat(),
        "headline": brief.get("headline"),
        "source_url": brief.get("source_url"),
        "overall_score": score,
        "evaluation": evaluation,
        "post": final_post,
        "hashtags": hashtags.get("hashtags", []),
        "image_prompt": image_config,
    }

    print("\n" + "=" * 60)
    print("LINKEDIN POST")
    print("=" * 60)
    print(f"Score: {score}/10")
    print(f"Source: {brief.get('source_url', 'N/A')}")
    print()
    print(final_post)
    print()
    print(" ".join(hashtags.get("hashtags", [])))
    print("=" * 60 + "\n")

    if save and output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        ts = now.strftime("%Y%m%d_%H%M%S")
        json_path = out_path / f"linkedin_post_{ts}.json"
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Saved to %s", json_path)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a LinkedIn post from AI news")
    parser.add_argument(
        "--output-dir", default="./outputs/linkedin_posts", help="Directory for saved results"
    )
    parser.add_argument("--no-save", action="store_true", help="Don't save results to file")
    args = parser.parse_args()

    for key in ("PERPLEXITY_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY"):
        if not os.getenv(key):
            log.error("Missing required env var: %s", key)
            return 1

    asyncio.run(run(output_dir=args.output_dir, save=not args.no_save))
    return 0


if __name__ == "__main__":
    sys.exit(main())
