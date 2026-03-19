"""Properties handler — list properties, get property value, _all.json."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient
from wikifs.formatter import format_directory_listing, format_error, format_file_content
from wikifs.models import HandlerConfig, HandlerResponse

if TYPE_CHECKING:
    from wikifs.tracing import TraceContext


# Common property aliases (English) for demo/CLI compatibility across languages
PROPERTY_ALIASES: dict[str, str] = {
    "population": "P1082",
    "country": "P17",
}


def _prop_label_to_filename(label: str, property_id: str, seen: set[str]) -> str:
    """Convert property label to filename. Handles duplicates with {label}_{property_id}.txt."""
    base = label.replace(" ", "_").lower()
    if not base:
        base = property_id.lower()
    fname = f"{base}.txt"
    if fname in seen:
        fname = f"{base}_{property_id}.txt"
    seen.add(fname)
    return fname


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


class PropertiesHandler:
    """Handler for entity properties."""

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
        """Handle properties requests."""
        name = params.get("name", "")
        if not name:
            return HandlerResponse(
                output=format_error("Missing entity name", "invalid_path"),
                exit_code=1,
                error_type="invalid_path",
            )
        lang = ctx.effective_language(self._config.default_language)

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

        if route == "properties.list_properties":
            return self._handle_list(entity_id, ctx, lang)
        if route == "properties.get_property":
            prop = params.get("prop", "")
            return self._handle_get_property(entity_id, prop, ctx, lang)
        if route == "properties.get_all_properties":
            return self._handle_get_all(entity_id, ctx, lang)
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
        """Handle ls /wiki/entities/{name}/properties/."""
        entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return HandlerResponse(
                output=format_error("Entity data not found", "entity_not_found"),
                exit_code=2,
                error_type="entity_not_found",
            )
        prop_ids = list({c.property_id for c in entity.claims})
        labels = self._wikidata.get_property_labels(prop_ids, lang=lang, ctx=ctx)
        seen: set[str] = set()
        entries: list[tuple[str, str | None]] = []
        for pid in prop_ids:
            label = labels.get(pid, pid)
            fname = _prop_label_to_filename(label, pid, seen)
            entries.append((fname, None))
        entries.append(("_all.json", None))
        output = format_directory_listing(entries, detailed=False)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_get_property(
        self,
        entity_id: str,
        prop_name: str,
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        """Handle cat /wiki/entities/{name}/properties/{prop}.txt."""
        entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return HandlerResponse(
                output=format_error("Entity data not found", "entity_not_found"),
                exit_code=2,
                error_type="entity_not_found",
            )
        prop_ids = list({c.property_id for c in entity.claims})
        labels = self._wikidata.get_property_labels(prop_ids, lang=lang, ctx=ctx)
        prop_name_base = prop_name.replace(".txt", "").lower()
        # Resolve alias (e.g. "population" -> P1082) for cross-language CLI usage
        resolved_pid = PROPERTY_ALIASES.get(prop_name_base)
        for c in entity.claims:
            label = labels.get(c.property_id, c.property_id)
            fname_base = label.replace(" ", "_").lower()
            pid_match = resolved_pid and c.property_id.upper() == resolved_pid.upper()
            if (
                fname_base == prop_name_base
                or f"{fname_base}_{c.property_id}" == prop_name_base
                or pid_match
            ):
                qual_str = ", ".join(c.qualifiers.values()) if c.qualifiers else ""
                content = c.value
                if qual_str:
                    content = f"{c.value} ({qual_str})"
                return HandlerResponse(
                    output=format_file_content(content, f"{prop_name}.txt"),
                    exit_code=0,
                )
        return HandlerResponse(
            output=format_error(f"Property not found: {prop_name}", "not_found"),
            exit_code=2,
            error_type="not_found",
        )

    def _handle_get_all(
        self,
        entity_id: str,
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        """Handle cat /wiki/entities/{name}/properties/_all.json."""
        entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return HandlerResponse(
                output=format_error("Entity data not found", "entity_not_found"),
                exit_code=2,
                error_type="entity_not_found",
            )
        prop_ids = list({c.property_id for c in entity.claims})
        labels = self._wikidata.get_property_labels(prop_ids, lang=lang, ctx=ctx)
        result: dict[str, dict[str, str | None]] = {}
        for c in entity.claims:
            label = labels.get(c.property_id, c.property_id)
            fname_base = label.replace(" ", "_").lower()
            key = fname_base
            result[key] = {
                "value": c.value,
                "property_id": c.property_id,
                "value_type": c.value_type,
            }
        return HandlerResponse(output=json.dumps(result, indent=2), exit_code=0)
