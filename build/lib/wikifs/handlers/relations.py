"""Relations handler — list relations, list relation targets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient
from wikifs.formatter import format_directory_listing, format_error
from wikifs.models import HandlerConfig, HandlerResponse

if TYPE_CHECKING:
    from wikifs.tracing import TraceContext


def _entity_resolve(
    wikidata: WikidataClient,
    name: str,
    lang: str,
    ctx: TraceContext,
) -> tuple[str | None, str | None, list[str]]:
    """Resolve entity by name. Returns (entity_id, wikipedia_title, suggestions)."""
    result = wikidata.resolve_entity(name, lang=lang, ctx=ctx)
    if result.entity:
        return (
            result.entity.entity_id,
            result.entity.wikipedia_title,
            result.suggestions or [],
        )
    return (None, None, result.suggestions or [])


# Common relation aliases (English) for demo/CLI compatibility across languages
# part_of = administrative hierarchy (Frankfurt→Hessen→Deutschland); P361 = component (motor→car)
RELATION_ALIASES: dict[str, str] = {
    "part_of": "P131",
    "component_of": "P361",
    "country": "P17",
    "located_in": "P131",
}


def _prop_label_to_filename(label: str, property_id: str, seen: set[str]) -> str:
    """Convert property label to directory name."""
    base = label.replace(" ", "_").lower()
    if not base:
        base = property_id.lower()
    if base in seen:
        base = f"{base}_{property_id}"
    seen.add(base)
    return base


class RelationsHandler:
    """Handler for entity relations (only wikibase-entityid properties)."""

    def __init__(
        self,
        wikidata: WikidataClient,
        wikipedia: WikipediaClient,
        config: HandlerConfig,
    ) -> None:
        self._wikidata = wikidata
        self._wikipedia = wikipedia
        self._config = config

    def handle(
        self,
        command: str,
        params: dict[str, str],
        flags: list[str],
        pattern: str | None,
        route: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle relations requests."""
        name = params.get("name", "")
        if not name:
            return HandlerResponse(
                output=format_error("Missing entity name", "invalid_path"),
                exit_code=1,
                error_type="invalid_path",
            )
        lang = self._config.default_language

        entity_id, _, suggestions = _entity_resolve(
            self._wikidata, name, lang, ctx
        )
        if entity_id is None:
            return HandlerResponse(
                output=format_error(
                    f"Entity not found: {name}",
                    "entity_not_found",
                    suggestions=suggestions[:5] if suggestions else None,
                ),
                exit_code=2,
                error_type="entity_not_found",
                suggestions=suggestions[:5] if suggestions else None,
            )

        if route == "relations.list_relations":
            return self._handle_list(entity_id, ctx, lang)
        if route == "relations.list_relation_targets":
            relation = params.get("relation", "")
            return self._handle_list_targets(entity_id, relation, ctx, lang)
        return HandlerResponse(
            output=format_error(f"Unknown route: {route}", "invalid_command"),
            exit_code=1,
            error_type="invalid_command",
        )

    def _handle_list(
        self,
        entity_id: str,
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        """Handle ls /wiki/entities/{name}/relations/."""
        entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return HandlerResponse(
                output=format_error("Entity data not found", "entity_not_found"),
                exit_code=2,
                error_type="entity_not_found",
            )
        relation_props = [
            c for c in entity.claims
            if c.value_type == "wikibase-entityid"
        ]
        prop_ids = list({c.property_id for c in relation_props})
        labels = self._wikidata.get_property_labels(prop_ids, lang=lang, ctx=ctx)
        seen: set[str] = set()
        entries: list[tuple[str, str | None]] = []
        for pid in prop_ids:
            label = labels.get(pid, pid)
            dirname = _prop_label_to_filename(label, pid, seen)
            entries.append((f"{dirname}/", None))
        output = format_directory_listing(entries, detailed=False)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_list_targets(
        self,
        entity_id: str,
        relation_name: str,
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        """Handle ls /wiki/entities/{name}/relations/{relation}/."""
        entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return HandlerResponse(
                output=format_error("Entity data not found", "entity_not_found"),
                exit_code=2,
                error_type="entity_not_found",
            )
        relation_props = [
            c for c in entity.claims
            if c.value_type == "wikibase-entityid"
        ]
        prop_ids = list({c.property_id for c in relation_props})
        labels = self._wikidata.get_property_labels(prop_ids, lang=lang, ctx=ctx)
        relation_name_base = relation_name.rstrip("/").lower()
        matched_prop_id: str | None = None
        resolved_pid = RELATION_ALIASES.get(relation_name_base)
        for pid in prop_ids:
            label = labels.get(pid, pid)
            dirname = label.replace(" ", "_").lower()
            pid_match = resolved_pid and pid.upper() == resolved_pid.upper()
            if (
                dirname == relation_name_base
                or f"{dirname}_{pid}" == relation_name_base
                or pid_match
            ):
                matched_prop_id = pid
                break
        if matched_prop_id is None:
            return HandlerResponse(
                output=format_error(f"Relation not found: {relation_name}", "not_found"),
                exit_code=2,
                error_type="not_found",
            )
        targets = self._wikidata.get_relation_targets(
            entity_id, matched_prop_id, lang=lang, ctx=ctx
        )
        entries: list[tuple[str, str | None]] = []
        for t in targets:
            target_name = t.wikipedia_title or t.label.replace(" ", "_")
            entries.append((f"{target_name}/", f"→ /wiki/entities/{target_name}/"))
        output = format_directory_listing(entries, detailed=True)
        return HandlerResponse(output=output, exit_code=0)
