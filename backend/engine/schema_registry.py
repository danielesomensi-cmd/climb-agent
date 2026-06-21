from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

@dataclass(frozen=True)
class SchemaRegistry:
    schemas_dir: Path
    base_uri: str
    schemas_by_key: Dict[str, Dict[str, Any]]
    store: Dict[str, Dict[str, Any]]

    @staticmethod
    def from_dir(schemas_dir: str | Path) -> "SchemaRegistry":
        d = Path(schemas_dir).resolve()
        if not d.exists():
            raise FileNotFoundError(f"schemas_dir not found: {d}")

        base_uri = d.as_uri().rstrip("/") + "/"
        schemas_by_key: Dict[str, Dict[str, Any]] = {}
        store: Dict[str, Dict[str, Any]] = {}

        for p in sorted(d.glob("*.json")):
            schema = json.loads(p.read_text(encoding="utf-8"))
            fname = p.name
            stem = p.stem  # e.g. session_log_entry.v1
            furi = p.resolve().as_uri()

            # keys for lookup
            schemas_by_key[fname] = schema
            schemas_by_key[stem] = schema

            # store entries for $ref resolution
            store[furi] = schema
            store[fname] = schema  # convenience (some resolvers use raw ref)

        return SchemaRegistry(schemas_dir=d, base_uri=base_uri, schemas_by_key=schemas_by_key, store=store)

    def get(self, key: str) -> Dict[str, Any]:
        # Accept "session_log_entry.v1" or "session_log_entry.v1.json"
        k = key.strip()
        if k.endswith(".json") and k in self.schemas_by_key:
            return self.schemas_by_key[k]
        if k in self.schemas_by_key:
            return self.schemas_by_key[k]
        if not k.endswith(".json") and (k + ".json") in self.schemas_by_key:
            return self.schemas_by_key[k + ".json"]
        raise KeyError(f"Schema not found for key='{key}'. Available: {sorted(self.schemas_by_key.keys())[:10]}...")

    def draft7_validator(self, schema: Dict[str, Any]):
        import jsonschema  # type: ignore
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT7

        # Build a fully-local registry from the preloaded store so cross-file
        # $refs (e.g. "exercise_outcome.v1.json") resolve without any network
        # access. Replaces the deprecated jsonschema.RefResolver (slated for
        # removal in a future jsonschema release). The store is keyed by both
        # file URI and bare filename, so either $ref spelling resolves.
        resources = [
            (uri, Resource.from_contents(s, default_specification=DRAFT7))
            for uri, s in self.store.items()
        ]
        registry = Registry().with_resources(resources)
        return jsonschema.Draft7Validator(schema, registry=registry)

def validate_instance(instance: Dict[str, Any], registry: SchemaRegistry, schema_key: str) -> List[str]:
    schema = registry.get(schema_key)
    v = registry.draft7_validator(schema)

    errors: List[str] = []
    for err in sorted(v.iter_errors(instance), key=lambda e: list(e.path)):
        loc = ".".join([str(x) for x in err.path]) if err.path else "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors
