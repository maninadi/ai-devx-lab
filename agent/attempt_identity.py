
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


HEX_ID = re.compile(r"[0-9a-f]{32}")


class IdentityConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class AttemptIdentity:
    operation_id: str
    run_id: str
    generation_id: str

    def validate(self) -> None:
        for value in (
            self.operation_id,
            self.run_id,
            self.generation_id,
        ):
            if not isinstance(value, str) or not HEX_ID.fullmatch(value):
                raise IdentityConflict("Invalid identity field")


class AttemptIdentityStore:
    def __init__(self, root: Path, operation_id: str):
        if not isinstance(operation_id, str) or not HEX_ID.fullmatch(operation_id):
            raise ValueError("Invalid operation ID")

        self.root = Path(root)
        self.operation_id = operation_id
        self.path = self.root / f"{operation_id}.identity.json"

    def save_new(self, identity: AttemptIdentity) -> None:
        identity.validate()

        if identity.operation_id != self.operation_id:
            raise IdentityConflict("Operation identity mismatch")

        # Provision this directory before starting operations.
        if not self.root.is_dir() or self.root.is_symlink():
            raise IdentityConflict("Trusted identity root required")

        data = {
            "version": 1,
            "operation_id": identity.operation_id,
            "run_id": identity.run_id,
            "generation_id": identity.generation_id,
        }

        # Exclusive creation: never replace an existing binding.
        with self.path.open("x", encoding="utf-8") as file:
            os.chmod(self.path, 0o600)
            json.dump(data, file, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        fd = os.open(self.root, flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def load(self) -> AttemptIdentity:
        if self.path.is_symlink():
            raise IdentityConflict("Identity path is a symlink")

        try:
            if self.path.stat().st_size > 2048:
                raise IdentityConflict("Identity record too large")

            data = json.loads(self.path.read_text("utf-8"))

            if not isinstance(data, dict) or set(data) != {
                "version",
                "operation_id",
                "run_id",
                "generation_id",
            }:
                raise IdentityConflict("Invalid identity schema")

            if type(data["version"]) is not int or data["version"] != 1:
                raise IdentityConflict("Unsupported identity version")

            identity = AttemptIdentity(
                operation_id=data["operation_id"],
                run_id=data["run_id"],
                generation_id=data["generation_id"],
            )
            identity.validate()

            if identity.operation_id != self.operation_id:
                raise IdentityConflict("Operation identity mismatch")

            return identity

        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise IdentityConflict(
                "Identity record unavailable or invalid"
            ) from exc
