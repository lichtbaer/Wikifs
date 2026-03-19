"""Virtual files for Wikipedia categories and outgoing article links."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient, WikipediaError
from wikifs.formatter import format_directory_listing, format_error, format_file_content
from wikifs.head_tail import apply_head_tail
from wikifs.models import HandlerConfig, HandlerResponse
from wikifs.wikipedia_nav_slug import resolve_nav_slug, title_to_nav_slug

if TYPE_CHECKING:
    from wikifs.tracing import TraceContext


def _entity_resolve(
    wikidata: WikidataClient,
    name: str,
    lang: str,
    ctx: TraceContext,
) -> tuple[str | None, str | None, list[str]]:
    result = wikidata.resolve_entity(name, lang=lang, ctx=ctx)
    if result.entity:
        return (
            result.entity.entity_id,
            result.entity.wikipedia_title,
            result.suggestions or [],
        )
    return (None, None, result.suggestions or [])


class PageNavHandler:
    """categories/ and links/ under an entity (MediaWiki API)."""

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
        name = params.get("name", "")
        if not name:
            return HandlerResponse(
                output=format_error("Missing entity name", "invalid_path"),
                exit_code=1,
                error_type="invalid_path",
            )
        lang = ctx.effective_language(self._config.default_language)

        if route == "page_nav.list_categories":
            return self._handle_list_categories(name, command, flags, ctx, lang)
        if route == "page_nav.get_category_md":
            cat = params.get("cat", "").replace(".md", "")
            return self._handle_get_category(
                name, cat, command, flags, ctx, lang
            )
        if route == "page_nav.list_links":
            return self._handle_list_links(name, command, flags, ctx, lang)
        if route == "page_nav.get_link_md":
            target = params.get("target", "").replace(".md", "")
            return self._handle_get_link(name, target, command, flags, ctx, lang)
        return HandlerResponse(
            output=format_error(f"Unknown route: {route}", "invalid_command"),
            exit_code=1,
            error_type="invalid_command",
        )

    def _wiki_title(
        self, name: str, ctx: TraceContext, lang: str
    ) -> tuple[str | None, HandlerResponse | None]:
        entity_id, wiki_title, suggestions = _entity_resolve(
            self._wikidata, name, lang, ctx
        )
        if entity_id is None or not wiki_title:
            err = HandlerResponse(
                output=format_error(
                    f"Entity not found: {name}",
                    "entity_not_found",
                    suggestions=suggestions[:5] if suggestions else None,
                ),
                exit_code=2,
                error_type="entity_not_found",
                suggestions=suggestions[:5] if suggestions else None,
            )
            return None, err
        return wiki_title, None

    def _handle_list_categories(
        self,
        name: str,
        command: str,
        flags: list[str],
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        if command != "ls":
            return HandlerResponse(
                output=format_error(
                    "Only ls lists categories/ (try cat on a .md file)",
                    "invalid_command",
                ),
                exit_code=1,
                error_type="invalid_command",
            )
        wiki_title, err = self._wiki_title(name, ctx, lang)
        if err:
            return err
        assert wiki_title is not None
        try:
            cats = self._wikipedia.get_page_categories(wiki_title, lang, ctx)
        except WikipediaError as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        detailed = "-l" in flags
        entries: list[tuple[str, str | None]] = [
            (f"{title_to_nav_slug(c)}.md", "[lazy]" if detailed else None)
            for c in cats
        ]
        output = format_directory_listing(entries, detailed=detailed)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_get_category(
        self,
        name: str,
        slug: str,
        command: str,
        flags: list[str],
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        if command not in ("cat", "head", "tail"):
            return HandlerResponse(
                output=format_error(
                    f"Use cat, head, or tail for category files (got {command})",
                    "invalid_command",
                ),
                exit_code=1,
                error_type="invalid_command",
            )
        if not slug:
            return HandlerResponse(
                output=format_error("Missing category filename", "invalid_path"),
                exit_code=1,
                error_type="invalid_path",
            )
        wiki_title, err = self._wiki_title(name, ctx, lang)
        if err:
            return err
        assert wiki_title is not None
        try:
            cats = self._wikipedia.get_page_categories(wiki_title, lang, ctx)
        except WikipediaError as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        full = resolve_nav_slug(slug, cats)
        if full is None:
            return HandlerResponse(
                output=format_error(f"Category not listed on page: {slug}", "not_found"),
                exit_code=2,
                error_type="not_found",
            )
        try:
            summary = self._wikipedia.get_summary(full.replace(" ", "_"), lang, ctx)
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        body = summary.extract_markdown or summary.extract or ""
        header = f"# {summary.title}\n\n"
        raw = header + body
        text, ferr = apply_head_tail(raw, command, flags)
        if ferr:
            return HandlerResponse(
                output=format_error(ferr, "invalid_flag"),
                exit_code=1,
                error_type="invalid_flag",
            )
        fname = f"{slug}.md"
        return HandlerResponse(
            output=format_file_content(text, fname),
            exit_code=0,
        )

    def _handle_list_links(
        self,
        name: str,
        command: str,
        flags: list[str],
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        if command != "ls":
            return HandlerResponse(
                output=format_error(
                    "Only ls lists links/ (try cat on a .md file)",
                    "invalid_command",
                ),
                exit_code=1,
                error_type="invalid_command",
            )
        wiki_title, err = self._wiki_title(name, ctx, lang)
        if err:
            return err
        assert wiki_title is not None
        try:
            links = self._wikipedia.get_page_links(wiki_title, lang, ctx)
        except WikipediaError as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        detailed = "-l" in flags
        entries: list[tuple[str, str | None]] = [
            (f"{title_to_nav_slug(t)}.md", "[lazy]" if detailed else None)
            for t in links
        ]
        output = format_directory_listing(entries, detailed=detailed)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_get_link(
        self,
        name: str,
        slug: str,
        command: str,
        flags: list[str],
        ctx: TraceContext,
        lang: str,
    ) -> HandlerResponse:
        if command not in ("cat", "head", "tail"):
            return HandlerResponse(
                output=format_error(
                    f"Use cat, head, or tail for link files (got {command})",
                    "invalid_command",
                ),
                exit_code=1,
                error_type="invalid_command",
            )
        if not slug:
            return HandlerResponse(
                output=format_error("Missing link filename", "invalid_path"),
                exit_code=1,
                error_type="invalid_path",
            )
        wiki_title, err = self._wiki_title(name, ctx, lang)
        if err:
            return err
        assert wiki_title is not None
        try:
            links = self._wikipedia.get_page_links(wiki_title, lang, ctx)
        except WikipediaError as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        full = resolve_nav_slug(slug, links)
        if full is None:
            return HandlerResponse(
                output=format_error(f"Link not listed on page: {slug}", "not_found"),
                exit_code=2,
                error_type="not_found",
            )
        try:
            summary = self._wikipedia.get_summary(full.replace(" ", "_"), lang, ctx)
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        body = summary.extract_markdown or summary.extract or ""
        header = f"# {summary.title}\n\n"
        raw = header + body
        text, ferr = apply_head_tail(raw, command, flags)
        if ferr:
            return HandlerResponse(
                output=format_error(ferr, "invalid_flag"),
                exit_code=1,
                error_type="invalid_flag",
            )
        fname = f"{slug}.md"
        return HandlerResponse(
            output=format_file_content(text, fname),
            exit_code=0,
        )
