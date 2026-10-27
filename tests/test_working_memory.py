
import json

import pytest

from agent.evidence_ledger import Evidence
from agent.working_memory import (
    WorkingMemory,
    MemoryCapsuleStore,
    InvalidMemoryCapsule,
)


def evidence(number):
    return Evidence(
        path=f"file_{number}.py",
        start_line=1,
        end_line=2,
        sha256="a" * 64,
    )


def make_capsule(memory, used=0, limit=100):
    return memory.capsule(
        run_id="run-1",
        response_id="resp-1",
        turn=2,
        context_chars_used=used,
        context_chars_limit=limit,
    )


def test_deduplicates_evidence():
    memory = WorkingMemory(max_recent=2)

    memory.observe(evidence(1))
    memory.observe(evidence(1))
    memory.observe(evidence(2))

    capsule = make_capsule(memory)

    assert capsule.unique_evidence == 2
    assert capsule.omitted_evidence == 0


def test_compaction_retains_recent_references():
    memory = WorkingMemory(max_recent=2)

    for number in range(1, 5):
        memory.observe(evidence(number))

    capsule = make_capsule(memory)

    assert capsule.unique_evidence == 4
    assert capsule.omitted_evidence == 2
    assert [
        item.path
        for item in capsule.recent_evidence
    ] == ["file_3.py", "file_4.py"]


@pytest.mark.parametrize(
    "used, expected",
    [
        (20, "normal"),
        (75, "high"),
        (100, "exhausted"),
    ],
)
def test_context_pressure(used, expected):
    memory = WorkingMemory()

    capsule = make_capsule(
        memory,
        used=used,
        limit=100,
    )

    assert capsule.pressure == expected


def test_capsule_round_trip(tmp_path):
    memory = WorkingMemory()
    memory.observe(evidence(1))

    original = make_capsule(memory)

    store = MemoryCapsuleStore(
        tmp_path / "memory.json"
    )

    store.save(original)

    assert store.load() == original


def test_invalid_capsule_is_rejected(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text(
        json.dumps({"version": 999}),
        encoding="utf-8",
    )

    with pytest.raises(InvalidMemoryCapsule):
        MemoryCapsuleStore(path).load()


def test_rejects_unverified_input():
    memory = WorkingMemory()

    with pytest.raises(TypeError):
        memory.observe({
            "path": "invented.py",
            "start_line": 1,
        })


def test_rejects_invalid_context_accounting():
    memory = WorkingMemory()

    with pytest.raises(InvalidMemoryCapsule):
        make_capsule(
            memory,
            used=101,
            limit=100,
        )
