import argparse
from pathlib import Path

from agent.loop import run_agent


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("task")

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    answer = run_agent(
        task=args.task,
        repo_root=repo_root,
    )

    print("\n=== AGENT ANSWER ===\n")
    print(answer)


if __name__ == "__main__":
    main()