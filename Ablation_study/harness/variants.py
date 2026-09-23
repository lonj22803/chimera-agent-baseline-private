"""Registro declarativo y construccion de variantes Tier S."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
import re
from typing import Any

import yaml

from .paths import CONFIGS
from .sim import A0, VariantSpec

VARIANTS_PATH = CONFIGS / "variantes_sim.yaml"
ALLOWED_TYPES = frozenset({"baseline", "ablacion", "reemplazo", "floor", "add_back", "sensitivity"})
_HYPOTHESIS = re.compile(r"^H(?:[1-9]|1[0-6])$")
_SPEC_FIELDS = {field.name for field in fields(VariantSpec)} - {"id"}


class VariantsError(ValueError):
    """El registro de variantes no satisface su contrato."""


@dataclass(frozen=True)
class Variant:
    id: str
    descripcion: str
    bloque: str
    tipo: str
    hipotesis: tuple[str, ...]
    spec: VariantSpec


def _text(row: dict[str, Any], field: str, where: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise VariantsError(f"{where}.{field} debe ser texto no vacio.")
    return value.strip()


def _normalise_changes(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VariantsError(f"{where}.cambios debe ser un mapa.")
    unknown = set(value) - _SPEC_FIELDS
    if unknown:
        raise VariantsError(f"Campos de VariantSpec desconocidos en {where}: {sorted(unknown)}.")
    changes = dict(value)
    if "closed_documents" in changes:
        documents = changes["closed_documents"]
        if not isinstance(documents, list):
            raise VariantsError(f"{where}.cambios.closed_documents debe ser una lista.")
        changes["closed_documents"] = tuple(documents)
    if "tiers" in changes:
        tiers = changes["tiers"]
        if not isinstance(tiers, dict):
            raise VariantsError(f"{where}.cambios.tiers debe ser un mapa.")
        changes["tiers"] = tuple((name, float(tiers[name])) for name in ("firm", "supports", "discuss"))
    return changes


def load_variants(path: Path = VARIANTS_PATH) -> dict[str, Variant]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise VariantsError("La version del registro de variantes debe ser 1.")
    rows = raw.get("variantes")
    if not isinstance(rows, list):
        raise VariantsError("variantes debe ser una lista.")

    variants: dict[str, Variant] = {}
    for index, value in enumerate(rows):
        where = f"variantes[{index}]"
        if not isinstance(value, dict):
            raise VariantsError(f"{where} debe ser un mapa.")
        variant_id = _text(value, "id", where)
        if variant_id in variants:
            raise VariantsError(f"ID de variante duplicado: {variant_id}.")
        variant_type = _text(value, "tipo", where)
        if variant_type not in ALLOWED_TYPES:
            raise VariantsError(f"Tipo desconocido en {variant_id}: {variant_type}.")
        hypotheses = value.get("hipotesis")
        if not isinstance(hypotheses, list) or any(
            not isinstance(item, str) or not _HYPOTHESIS.match(item) for item in hypotheses
        ):
            raise VariantsError(f"Hipotesis invalidas en {variant_id}.")
        changes = _normalise_changes(value.get("cambios"), where)
        spec = replace(A0, id=variant_id, **changes)
        variants[variant_id] = Variant(
            id=variant_id,
            descripcion=_text(value, "descripcion", where),
            bloque=_text(value, "bloque", where),
            tipo=variant_type,
            hipotesis=tuple(hypotheses),
            spec=spec,
        )
    if "A0" not in variants or variants["A0"].spec != A0:
        raise VariantsError("A0 debe estar presente y no puede cambiar la referencia.")
    return variants


def get_spec(variant_id: str, path: Path = VARIANTS_PATH) -> VariantSpec:
    try:
        return load_variants(path)[variant_id].spec
    except KeyError as exc:
        raise VariantsError(f"Variante desconocida: {variant_id}.") from exc
