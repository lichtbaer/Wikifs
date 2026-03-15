"""Article handler — full article, summary, sections."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient
from wikifs.formatter import format_directory_listing, format_error, format_file_content
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


class ArticleHandler:
    """Handler for Wikipedia articles and sections."""

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
        """Handle article requests."""
        name = params.get("name", "")
        if not name:
            return HandlerResponse(
                output=format_error("Missing entity name", "invalid_path"),
                exit_code=1,
                error_type="invalid_path",
            )
        lang = self._config.default_language

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
        title = wiki_title or (entity.label.replace(" ", "_") if entity else name)

        if command == "grep":
            if route == "article.get_article":
                return self._handle_grep_article(title, lang, ctx, flags, pattern)
            if route == "article.get_article_lang":
                article_lang = params.get("lang", "en")
                if article_lang in self._config.supported_languages:
                    return self._handle_grep_article(
                        title, article_lang, ctx, flags, pattern
                    )
            if route == "article.get_summary":
                return self._handle_grep_summary(title, lang, ctx, flags, pattern)
            if route == "article.get_section":
                section_name = params.get("section", "")
                return self._handle_grep_section(
                    title, section_name, lang, ctx, flags, pattern
                )

        if route == "article.get_article":
            return self._handle_article(title, lang, ctx)
        if route == "article.get_article_lang":
            article_lang = params.get("lang", "en")
            if article_lang not in self._config.supported_languages:
                return HandlerResponse(
                    output=format_error(
                        f"Unsupported language: {article_lang}",
                        "invalid_path",
                    ),
                    exit_code=1,
                    error_type="invalid_path",
                )
            return self._handle_article(title, article_lang, ctx)
        if route == "article.get_summary":
            return self._handle_summary(title, lang, ctx)
        if route == "article.list_sections":
            return self._handle_list_sections(title, lang, ctx)
        if route == "article.get_section":
            section_name = params.get("section", "")
            return self._handle_get_section(title, section_name, lang, ctx)
        return HandlerResponse(
            output=format_error(f"Unknown route: {route}", "invalid_command"),
            exit_code=1,
            error_type="invalid_command",
        )

    def _handle_article(
        self,
        title: str,
        lang: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle cat article.md or article.{lang}.md."""
        try:
            content = self._wikipedia.get_article(title, lang=lang, ctx=ctx)
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        return HandlerResponse(
            output=format_file_content(content.markdown, "article.md"),
            exit_code=0,
        )

    def _handle_summary(
        self,
        title: str,
        lang: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle cat summary.md."""
        try:
            summary = self._wikipedia.get_summary(title, lang=lang, ctx=ctx)
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        return HandlerResponse(
            output=format_file_content(summary.extract_markdown, "summary.md"),
            exit_code=0,
        )

    def _handle_list_sections(
        self,
        title: str,
        lang: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle ls sections/."""
        try:
            sections = self._wikipedia.get_sections(title, lang=lang, ctx=ctx)
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        entries = [(f"{s.title}.md", None) for s in sections]
        output = format_directory_listing(entries, detailed=False)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_get_section(
        self,
        title: str,
        section_name: str,
        lang: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle cat sections/{section}.md."""
        section_name_base = section_name.replace(".md", "").strip()
        try:
            section = self._wikipedia.get_section(
                title, section_name_base, lang=lang, ctx=ctx
            )
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        if section is None:
            return HandlerResponse(
                output=format_error(f"Section not found: {section_name_base}", "not_found"),
                exit_code=2,
                error_type="not_found",
            )
        return HandlerResponse(
            output=format_file_content(section.markdown, f"{section.title}.md"),
            exit_code=0,
        )

    def _grep_in_content(
        self,
        content: str,
        fname: str,
        pattern: str | None,
        flags: list[str],
    ) -> HandlerResponse:
        """Grep within content. Returns matches or count."""
        if not pattern:
            return HandlerResponse(
                output=format_error("grep requires a pattern", "invalid_command"),
                exit_code=1,
                error_type="invalid_command",
            )
        case_insensitive = "-i" in flags
        count_only = "-c" in flags
        regex_flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(re.escape(pattern), regex_flags)
        except re.error:
            regex = re.compile(re.escape(pattern), regex_flags)
        matches: list[tuple[int, str]] = []
        for i, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                matches.append((i, line.strip()))
        if count_only:
            return HandlerResponse(output=str(len(matches)), exit_code=0)
        lines = [f"{fname}:{i}: {text}" for i, text in matches]
        return HandlerResponse(output="\n".join(lines), exit_code=0)

    def _handle_grep_article(
        self,
        title: str,
        lang: str,
        ctx: TraceContext,
        flags: list[str],
        pattern: str | None,
    ) -> HandlerResponse:
        """Grep within article.md."""
        try:
            content = self._wikipedia.get_article(title, lang=lang, ctx=ctx)
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        return self._grep_in_content(
            content.markdown, "article.md", pattern, flags
        )

    def _handle_grep_summary(
        self,
        title: str,
        lang: str,
        ctx: TraceContext,
        flags: list[str],
        pattern: str | None,
    ) -> HandlerResponse:
        """Grep within summary.md."""
        try:
            summary = self._wikipedia.get_summary(title, lang=lang, ctx=ctx)
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        return self._grep_in_content(
            summary.extract_markdown, "summary.md", pattern, flags
        )

    def _handle_grep_section(
        self,
        title: str,
        section_name: str,
        lang: str,
        ctx: TraceContext,
        flags: list[str],
        pattern: str | None,
    ) -> HandlerResponse:
        """Grep within sections/{section}.md."""
        section_name_base = section_name.replace(".md", "").strip()
        try:
            section = self._wikipedia.get_section(
                title, section_name_base, lang=lang, ctx=ctx
            )
        except Exception as e:
            return HandlerResponse(
                output=format_error(str(e), "article_not_found"),
                exit_code=2,
                error_type="article_not_found",
            )
        if section is None:
            return HandlerResponse(
                output=format_error(
                    f"Section not found: {section_name_base}", "not_found"
                ),
                exit_code=2,
                error_type="not_found",
            )
        fname = f"sections/{section.title}.md"
        return self._grep_in_content(
            section.markdown, fname, pattern, flags
        )
