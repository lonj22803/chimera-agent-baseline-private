"""Carga y valida el catalogo de intervenciones de la Tarea 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from .paths import CONFIGS

CATALOG_PATH = CONFIGS / "intervenciones_t1.yaml"
ALLOWED_TIERS = frozenset({"S", "L", "J"})
EXPECTED_IDS = frozenset(
    {"N01", *(f"N{i:02d}" for i in range(3, 16))}
    | {f"M{i}" for i in range(1, 14)}
    | {f"G{i}" for i in range(1, 8)}
)
EXPECTED_STRUCTURAL_IDS = frozenset(
    {
        "N01",
        "M7",
        "G4",
        "G5",
        "G7",
        "D-OPERATIVA",
        "D-RASGOS",
        "D-PROMPTS",
        "D-CONTRATO",
        "GRAPH_START",
        "GRAPH_END",
    }
)
_SYMBOL = re.compile(r"^[^:]+:\d")
_HYPOTHESIS = re.compile(r"^H(?:[1-9]|1[0-6])$")


class CatalogError(ValueError):
    """El YAML no satisface el contrato pre-registrado del catalogo."""


@dataclass(frozen=True)
class Intervention:
    id: str
    nombre: str
    nodos_grafo: tuple[str, ...]
    simbolo: str
    canal: str
    variantes: tuple[str, ...]
    tier: tuple[str, ...]
    hipotesis: tuple[str, ...]


@dataclass(frozen=True)
class StructuralElement:
    id: str
    nombre: str
    nodos_grafo: tuple[str, ...]
    por_que: str


@dataclass(frozen=True)
class Catalog:
    version: int
    intervenciones: tuple[Intervention, ...]
    estructural: tuple[StructuralElement, ...]

    @property
    def node_owners(self) -> dict[str, str]:
        owners: dict[str, str] = {}
        for item in (*self.intervenciones, *self.estructural):
            for node in item.nodos_grafo:
                previous = owners.setdefault(node, item.id)
                if previous != item.id:
                    raise CatalogError(
                        f"El nodo {node!r} pertenece a {previous!r} y {item.id!r}."
                    )
        return owners


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogError(f"{where} debe ser un mapa YAML.")
    return value


def _text(row: dict[str, Any], field: str, where: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{where}.{field} debe ser texto no vacio.")
    return value.strip()


def _texts(row: dict[str, Any], field: str, where: str, *, nonempty: bool = False) -> tuple[str, ...]:
    value = row.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise CatalogError(f"{where}.{field} debe ser una lista de textos.")
    if nonempty and not value:
        raise CatalogError(f"{where}.{field} no puede estar vacio.")
    return tuple(item.strip() for item in value)


def load_catalog(path: Path = CATALOG_PATH) -> Catalog:
    """Carga el YAML y falla pronto ante IDs, campos o nodos ambiguos."""
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), str(path))
    if raw.get("version") != 1:
        raise CatalogError("La version del catalogo debe ser 1.")

    raw_interventions = raw.get("intervenciones")
    if not isinstance(raw_interventions, list):
        raise CatalogError("intervenciones debe ser una lista.")

    interventions: list[Intervention] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(raw_interventions):
        where = f"intervenciones[{index}]"
        row = _mapping(value, where)
        item_id = _text(row, "id", where)
        if item_id in seen_ids:
            raise CatalogError(f"ID duplicado: {item_id}.")
        seen_ids.add(item_id)

        symbol = _text(row, "simbolo", where)
        if not _SYMBOL.match(symbol):
            raise CatalogError(f"{where}.simbolo no tiene formato fichero:linea.")
        tiers = _texts(row, "tier", where)
        unknown_tiers = set(tiers) - ALLOWED_TIERS
        if unknown_tiers:
            raise CatalogError(f"Tier desconocido en {item_id}: {sorted(unknown_tiers)}.")
        hypotheses = _texts(row, "hipotesis", where)
        if any(not _HYPOTHESIS.match(item) for item in hypotheses):
            raise CatalogError(f"Hipotesis invalida en {item_id}: {hypotheses}.")

        interventions.append(
            Intervention(
                id=item_id,
                nombre=_text(row, "nombre", where),
                nodos_grafo=_texts(row, "nodos_grafo", where),
                simbolo=symbol,
                canal=_text(row, "canal", where),
                variantes=_texts(row, "variantes", where, nonempty=True),
                tier=tiers,
                hipotesis=hypotheses,
            )
        )

    missing = EXPECTED_IDS - seen_ids
    extra = seen_ids - EXPECTED_IDS
    if missing or extra:
        raise CatalogError(f"IDs de catalogo incorrectos; faltan={sorted(missing)}, sobran={sorted(extra)}.")

    raw_structural = raw.get("estructural")
    if not isinstance(raw_structural, list):
        raise CatalogError("estructural debe ser una lista.")
    structural: list[StructuralElement] = []
    structural_ids: set[str] = set()
    for index, value in enumerate(raw_structural):
        where = f"estructural[{index}]"
        row = _mapping(value, where)
        item_id = _text(row, "id", where)
        if item_id in structural_ids:
            raise CatalogError(f"ID estructural duplicado: {item_id}.")
        structural_ids.add(item_id)
        structural.append(
            StructuralElement(
                id=item_id,
                nombre=_text(row, "nombre", where),
                nodos_grafo=_texts(row, "nodos_grafo", where),
                por_que=_text(row, "por_que", where),
            )
        )

    missing_structural = EXPECTED_STRUCTURAL_IDS - structural_ids
    extra_structural = structural_ids - EXPECTED_STRUCTURAL_IDS
    if missing_structural or extra_structural:
        raise CatalogError(
            "IDs estructurales incorrectos; "
            f"faltan={sorted(missing_structural)}, sobran={sorted(extra_structural)}."
        )

    catalog = Catalog(1, tuple(interventions), tuple(structural))
    catalog.node_owners
    return catalog
