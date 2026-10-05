"""Optional real API demo; temporary synthetic data only, no existing corpus."""
from pathlib import Path
import tempfile

from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST, DEMO_TEXT, EngineMemory
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

STAMP = "2026-10-05T07:11:52+00:00"


def seed(root):
    # Only this fixture builder writes, via the engine's coordinated service.
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from core.information.writes import FilesystemInformationWrites
    backend = FilesystemBackend(root / "memory/persistent", root / "memory/history")
    memory = Memory("synthetic-note", content=DEMO_TEXT,
                    metadata={"epistemic_status": "UNVERIFIED", "operational_state": "PLANNED",
                              "confidence": "LOW", "context": {"scope": {"goal": "demo"}}},
                    provenance={"source_type": "SYNTHETIC", "source": "core-integration-fixture/1"},
                    temporal={"observed_at": STAMP},
                    verification={"evidence": {"supporting": ["synthetic-case-1"]}})
    writer = FilesystemInformationWrites(backend)
    writer.create(memory, operation_id="fixture-create-1", event_id="fixture-event-1",
                  actor="core-test-fixture", timestamp=STAMP)
    return backend, writer, memory


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-core-memory-demo-") as directory:
        root = Path(directory)
        seed(root / "engine")
        runtime = Runtime(Store(root / "missions"), memory=EngineMemory(str(root / "engine")))
        mission = runtime.create(DEMO_REQUEST)
        result = runtime.run(mission["id"])
        print(encode(result))
        return 0 if result["status"] == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
