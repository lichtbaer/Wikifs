"""Entity handler — directory listing, meta.json, grep within entity."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient
from wikifs.formatter import format_directory_listing, format_error
from wikifs.head_tail import apply_head_tail
from wikifs.models import HandlerConfig, HandlerResponse

if TYPE_CHECKING:
    from wikifs.tracing import TraceContext


ENTITY_DIR_ENTRIES = [
    ("article.md", None),
    ("summary.md", None),
    ("properties/", None),
    ("relations/", None),
    ("sections/", None),
    ("categories/", None),
    ("links/", None),
    ("meta.json", None),
]


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


def _format_size(size: int) -> str:
    """Format byte size for ls -l."""
    if size >= 1024:
        return f"~{size // 1024}KB"
    return f"{size}B"


class EntityHandler:
    """Handler for entity directory and meta."""

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
        """Handle entity requests: ls, ls -l, cat meta.json, grep."""
        name = params.get("name", "")
        if not name:
            return HandlerResponse(
                output=format_error("Missing entity name", "invalid_path"),
                exit_code=1,
                error_type="invalid_path",
            )
        lang = ctx.effective_language(self._config.default_language)

        if command == "grep" and route == "entity.list_entity":
            return self._handle_grep(name, flags, pattern, ctx, lang)
        if command in ("cat", "head", "tail") and route == "entity.get_meta":
            return self._handle_meta(name, ctx, lang, command, flags)
        if command == "ls" and route == "entity.list_entity":
            return self._handle_ls(name, flags, ctx, lang)
        return HandlerResponse(
            output=format_error(f"Unknown command for entity: {command}", "invalid_command"),
            exit_code=1,
            error_type="invalid_command",
        )

    def _handle_ls(
        self,
        name: str,
        flags: list[str],
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        """Handle ls /wiki/entities/{name}/."""
        entity_id, wiki_title, suggestions = _entity_resolve(
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
        detailed = "-l" in flags
        entries: list[tuple[str, str | None]]
        if detailed:
            entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
            if entity is None:
                return HandlerResponse(
                    output=format_error("Entity data not found", "entity_not_found"),
                    exit_code=2,
                    error_type="entity_not_found",
                )
            claims = entity.claims
            props_count = len(set(c.property_id for c in claims))
            relation_props = sum(
                1 for c in claims if c.value_type == "wikibase-entityid"
            )
            summary = self._wikipedia.get_summary(
                wiki_title or entity.label.replace(" ", "_"),
                lang=lang,
                ctx=ctx,
            )
            sections = self._wikipedia.get_sections(
                wiki_title or entity.label.replace(" ", "_"),
                lang=lang,
                ctx=ctx,
            )
            entries = [
                ("article.md", "[lazy] ~42KB"),
                (
                    "summary.md",
                    f"[cached] {_format_size(len(summary.extract_markdown.encode()))}",
                ),
                ("properties/", f"{props_count} items"),
                ("relations/", f"{relation_props} items"),
                ("sections/", f"{len(sections)} items"),
                ("categories/", "[lazy]"),
                ("links/", "[lazy]"),
                ("meta.json", "[cached] 0.3KB"),
            ]
        else:
            entries = cast(list[tuple[str, str | None]], ENTITY_DIR_ENTRIES)
        output = format_directory_listing(entries, detailed=detailed)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_meta(
        self,
        name: str,
        ctx: TraceContext,
        lang: str,
        command: str,
        flags: list[str],
    ) -> HandlerResponse:
        """Handle cat/head/tail /wiki/entities/{name}/meta.json."""
        entity_id, wiki_title, suggestions = _entity_resolve(
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
        entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return HandlerResponse(
                output=format_error("Entity data not found", "entity_not_found"),
                exit_code=2,
                error_type="entity_not_found",
            )
        import json

        meta = {
            "entity_id": entity.entity_id,
            "label": entity.label,
            "description": entity.description,
            "aliases": entity.aliases,
            "last_modified": entity.last_modified,
        }
        raw = json.dumps(meta, indent=2)
        text, err = apply_head_tail(raw, command, flags)
        if err:
            return HandlerResponse(
                output=format_error(err, "invalid_flag"),
                exit_code=1,
                error_type="invalid_flag",
            )
        return HandlerResponse(output=text, exit_code=0)

    def _handle_grep(
        self,
        name: str,
        flags: list[str],
        pattern: str | None,
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        """Handle grep within entity."""
        if not pattern:
            return HandlerResponse(
                output=format_error("grep requires a pattern", "invalid_command"),
                exit_code=1,
                error_type="invalid_command",
            )
        entity_id, wiki_title, suggestions = _entity_resolve(
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
        entity = self._wikidata.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return HandlerResponse(
                output=format_error("Entity data not found", "entity_not_found"),
                exit_code=2,
                error_type="entity_not_found",
            )
        case_insensitive = "-i" in flags
        count_only = "-c" in flags
        regex_flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(re.escape(pattern), regex_flags)
        except re.error:
            regex = re.compile(re.escape(pattern), regex_flags)

        matches: list[tuple[str, int, str]] = []
        searchables: list[tuple[str, str]] = []

        summary = self._wikipedia.get_summary(
            wiki_title or entity.label.replace(" ", "_"),
            lang=lang,
            ctx=ctx,
        )
        searchables.append(("summary.md", summary.extract_markdown))

        article = self._wikipedia.get_article(
            wiki_title or entity.label.replace(" ", "_"),
            lang=lang,
            ctx=ctx,
        )
        searchables.append(("article.md", article.markdown))

        prop_labels = self._wikidata.get_property_labels(
            list({c.property_id for c in entity.claims}),
            lang=lang,
            ctx=ctx,
        )
        for c in entity.claims:
            label = prop_labels.get(c.property_id, c.property_id)
            fname = label.replace(" ", "_").lower()
            searchables.append((f"properties/{fname}.txt", c.value))
        for c in entity.claims:
            if c.value_type == "wikibase-entityid":
                target = self._wikidata.get_entity(c.value, lang=lang, ctx=ctx)
                if target:
                    label = prop_labels.get(c.property_id, c.property_id)
                    rel_name = label.replace(" ", "_").lower()
                    searchables.append(
                        (f"relations/{rel_name}/", target.label)
                    )

        for fname, content in searchables:
            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    matches.append((fname, i, line.strip()))

        if count_only:
            return HandlerResponse(output=str(len(matches)), exit_code=0)
        lines = [f"{fname}:{i}: {text}" for fname, i, text in matches]
        return HandlerResponse(output="\n".join(lines), exit_code=0)
