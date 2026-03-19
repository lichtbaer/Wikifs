"""Search handler — entity search and SPARQL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient
from wikifs.formatter import format_error, format_search_results, format_sparql_csv
from wikifs.models import HandlerConfig, HandlerResponse

if TYPE_CHECKING:
    from wikifs.tracing import TraceContext


def _get_flag_value(flags: list[str], flag_name: str) -> str | None:
    """Get value for flag like --type or --limit."""
    for i, f in enumerate(flags):
        if f == flag_name and i + 1 < len(flags):
            return flags[i + 1]
    return None


class SearchHandler:
    """Handler for search and SPARQL."""

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
        """Handle search requests."""
        if route == "search.entities":
            return self._handle_entity_search(flags, pattern, ctx)
        if route == "search.sparql_query":
            return self._handle_sparql(flags, ctx)
        return HandlerResponse(
            output=format_error(f"Unknown route: {route}", "invalid_command"),
            exit_code=1,
            error_type="invalid_command",
        )

    def _handle_entity_search(
        self,
        flags: list[str],
        pattern: str | None,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle search "Goethe" --type entity --limit 10."""
        query = pattern or ""
        if not query.strip():
            return HandlerResponse(
                output=format_error("Search requires a query (pattern)", "invalid_command"),
                exit_code=1,
                error_type="invalid_command",
            )
        limit_str = _get_flag_value(flags, "--limit")
        limit = self._config.pagination_default_limit
        if limit_str:
            try:
                limit = min(int(limit_str), self._config.pagination_max_limit)
            except ValueError:
                pass
        lang = ctx.effective_language(self._config.default_language)
        results = self._wikidata.search_entities(
            query, lang=lang, limit=limit, ctx=ctx
        )
        tuples = [
            (
                r.wikipedia_title or r.label.replace(" ", "_") or r.entity_id,
                r.entity_id,
                r.description or "",
            )
            for r in results
        ]
        output = format_search_results(tuples)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_sparql(
        self,
        flags: list[str],
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle search --sparql "SELECT ..." (cat /wiki/sparql/result.csv)."""
        sparql = _get_flag_value(flags, "--sparql")
        if not sparql or not sparql.strip():
            return HandlerResponse(
                output=format_error(
                    "SPARQL query required. Use --sparql \"SELECT ...\"",
                    "invalid_command",
                ),
                exit_code=1,
                error_type="invalid_command",
            )
        bindings = self._wikidata.sparql_query(sparql, ctx=ctx)
        output = format_sparql_csv(bindings)
        return HandlerResponse(output=output, exit_code=0)
