from pathlib import Path

from agent.verification import (
    run_check,
    evaluate_completion
)


def main():
    repo_root = Path(__file__).resolve().parents[1]

    pricing = run_check("pricing", repo_root)
    suite = run_check("suite", repo_root)

    verdict = evaluate_completion(pricing, suite)

    print(f"Pricing: {pricing.status.value}")
    print(f"Suite:   {suite.status.value}")
    print(f"Verdict: {verdict.value}")

    if pricing.status.value != "pass":
        print("\nPricing verification output:")
        print(pricing.output)

    if suite.status.value != "pass":
        print("\nFull-suite verification output:")
        print(suite.output)


if __name__ == "__main__":
    main()