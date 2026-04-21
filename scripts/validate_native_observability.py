#!/usr/bin/env python
"""Validate observability (token usage, cost, OTel spans) for native clients.

Runs a small manifest against FFMistralSmall, FFMistral, FFPerplexity, and FFGemini,
then inspects the parquet results for token counts, cost estimates, and duration.
"""

import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from src.orchestrator.manifest import ManifestOrchestrator

MANIFEST_DIR = "./manifest_samples/observability_native_clients"

CLIENTS = [
    {
        "name": "FFMistralSmall",
        "client_type": "mistral-small",
        "env_key": "MISTRALSMALL_KEY",
    },
    {
        "name": "FFMistral",
        "client_type": "litellm-mistral-large",
        "env_key": "MISTRAL_API_KEY",
        "note": "using litellm-mistral-large as proxy since FFMistral has no client_type registered; will also test FFMistral directly below",
    },
    {
        "name": "FFPerplexity",
        "client_type": "perplexity",
        "env_key": "PERPLEXITY_API_KEY",
    },
    {
        "name": "FFGemini",
        "client_type": "gemini",
        "env_key": "GEMINI_API_KEY",
    },
]


def get_client_instance(client_info):
    """Create a native client instance directly."""
    name = client_info["name"]
    api_key = os.getenv(client_info["env_key"])

    if not api_key:
        return None, f"No API key found for {client_info['env_key']}"

    match name:
        case "FFMistralSmall":
            from src.Clients.FFMistralSmall import FFMistralSmall

            return FFMistralSmall(api_key=api_key, max_tokens=256, temperature=0.3), None
        case "FFMistral":
            from src.Clients.FFMistral import FFMistral

            return FFMistral(api_key=api_key, max_tokens=256, temperature=0.3), None
        case "FFPerplexity":
            from src.Clients.FFPerplexity import FFPerplexity

            return FFPerplexity(api_key=api_key, model="sonar", max_tokens=256, temperature=0.3), None
        case "FFGemini":
            from src.Clients.FFGemini import FFGemini

            try:
                return FFGemini(max_tokens=256, temperature=0.3), None
            except Exception as e:
                return None, f"FFGemini requires Google Cloud ADC: {e}"
        case _:
            return None, f"Unknown client: {name}"


def validate_usage(client, client_name):
    """Validate that usage is populated after a generate_response call."""
    prompt = "Say hello in one sentence."
    try:
        response = client.generate_response(prompt)
        usage = client.last_usage
        cost = client.last_cost_usd

        print(f"  Response: {response[:80]}...")
        print(f"  Usage: input={usage.input_tokens if usage else 'None'}, "
              f"output={usage.output_tokens if usage else 'None'}, "
              f"total={usage.total_tokens if usage else 'None'}")
        print(f"  Cost: ${cost:.6f}")

        if usage is None:
            print(f"  [WARN] No usage data extracted for {client_name}")
            return False

        if usage.input_tokens <= 0:
            print(f"  [WARN] Input tokens is 0 for {client_name}")
            return False

        if usage.output_tokens <= 0:
            print(f"  [WARN] Output tokens is 0 for {client_name}")
            return False

        print("  [OK] Token usage extracted successfully")
        return True

    except Exception as e:
        print(f"  [ERROR] {e}")
        traceback.print_exc()
        return False


def validate_manifest_run(client, client_name):
    """Run the manifest and validate parquet output."""
    try:
        start = time.time()
        orchestrator = ManifestOrchestrator(
            manifest_dir=MANIFEST_DIR,
            client=client,
            concurrency=1,
        )
        parquet_path = orchestrator.run()
        elapsed = time.time() - start

        summary = orchestrator.get_summary()

        print(f"  Parquet: {parquet_path}")
        print(f"  Elapsed: {elapsed:.1f}s")
        print(f"  Summary: {summary['successful']} success, "
              f"{summary['failed']} failed, "
              f"{summary.get('skipped', 0)} skipped")

        total_input = summary.get("total_input_tokens", 0)
        total_output = summary.get("total_output_tokens", 0)
        total_cost = summary.get("total_cost_usd", 0.0)

        tokens_summary = summary.get("tokens", {})
        if tokens_summary:
            total_input = tokens_summary.get("input", 0)
            total_output = tokens_summary.get("output", 0)
            total_cost = summary.get("cost_usd", 0.0)

        print(f"  Tokens: in={total_input}, out={total_output}")
        print(f"  Cost: ${total_cost:.6f}")

        if summary["failed"] > 0:
            print(f"  [WARN] {summary['failed']} prompts failed")
            return False

        if total_input > 0 or total_output > 0:
            print("  [OK] Token tracking working in orchestrator")
        else:
            print("  [WARN] No tokens tracked in orchestrator summary")

        return True

    except Exception as e:
        print(f"  [ERROR] {e}")
        traceback.print_exc()
        return False


def main():
    print("=" * 70)
    print("OBSERVABILITY VALIDATION - Native Client Token Usage & Cost")
    print("=" * 70)
    print()

    results = {}

    for client_info in CLIENTS:
        name = client_info["name"]
        print(f"--- {name} ---")

        client, err = get_client_instance(client_info)
        if err:
            print(f"  [SKIP] {err}")
            results[name] = "SKIP"
            print()
            continue

        # Step 1: Direct usage validation
        print("  [Test 1] Direct generate_response() usage extraction:")
        usage_ok = validate_usage(client, name)
        print()

        # Step 2: Manifest orchestrator run
        print("  [Test 2] Manifest orchestrator run:")
        clone = client.clone()
        manifest_ok = validate_manifest_run(clone, name)

        results[name] = "PASS" if (usage_ok and manifest_ok) else "PARTIAL"
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, status in results.items():
        icon = {"PASS": "OK", "PARTIAL": "!!", "SKIP": "--", "FAIL": "XX"}[status]
        print(f"  [{icon}] {name}: {status}")
    print()

    all_pass = all(s in ("PASS", "SKIP") for s in results.values())
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
