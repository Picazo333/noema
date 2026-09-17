from __future__ import annotations

from datetime import datetime, timezone


def minimal_provenance(activity: str, actor: str, inputs=None, sources=None, integrity=None):
    return {
        "activity": activity,
        "actor": actor,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs or [],
        "source_refs": sources or [],
        "integrity": integrity,
    }
