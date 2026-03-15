"""Wikidata data models for WikiFS."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResolvedEntity:
    """Resolved entity from name or ID lookup."""

    entity_id: str  # "Q1794"
    label: str  # "Frankfurt am Main"
    description: str  # "Metropole in Hessen, Deutschland"
    wikipedia_title: str  # "Frankfurt_am_Main"
    aliases: list[str]  # ["Frankfurt", "Frankfurt/Main"]


@dataclass
class Claim:
    """Single claim (property-value pair)."""

    property_id: str  # "P1082"
    property_label: str  # "population"
    value: str  # "773.068"
    qualifiers: dict[str, str]  # {"P585": "2023"} (point in time)
    rank: str  # "preferred", "normal", "deprecated"


@dataclass
class ResolveResult:
    """Result of entity resolution with optional suggestions for fuzzy matching."""

    entity: ResolvedEntity | None
    suggestions: list[str] = field(default_factory=list)  # Top-5 when no exact match


@dataclass
class WikidataEntity:
    """Full Wikidata entity with claims and sitelinks."""

    entity_id: str
    label: str
    description: str
    aliases: list[str]
    claims: list[Claim]
    sitelinks: dict[str, str]  # {"dewiki": "Frankfurt_am_Main", "enwiki": "Frankfurt"}
    last_modified: str


@dataclass
class ClaimValue:
    """Formatted claim value with qualifiers."""

    value: str
    formatted: str  # "773.068 (2023, Statistisches Bundesamt)"
    qualifiers: dict[str, str]
    value_type: str  # "quantity", "string", "wikibase-entityid", "time", "coordinate"


@dataclass
class RelationTarget:
    """Target of a relation (e.g. P131 -> Hessen)."""

    entity_id: str
    label: str
    wikipedia_title: str


@dataclass
class SearchResult:
    """Search result from wbsearchentities."""

    entity_id: str
    label: str
    description: str
    wikipedia_title: str | None


@dataclass
class ClassMembers:
    """Members of a Wikidata class from SPARQL."""

    members: list[SearchResult]
    total_count: int | None  # Wenn verfügbar
    has_more: bool
