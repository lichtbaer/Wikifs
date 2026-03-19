"""Wikipedia API client — Article summaries, full content, sections."""

from __future__ import annotations

import json
import re
import unicodedata
from contextlib import nullcontext
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlencode

import requests
from markdownify import markdownify as md

from wikifs.backends.wikipedia_models import (
    ArticleContent,
    ArticleSummary,
    Section,
)
from wikifs.cache import Cache
from wikifs.config import ApiConfig
from wikifs.errors import ErrorCollector
from wikifs.tracing import TraceContext


class WikipediaError(Exception):
    """Base exception for Wikipedia client errors."""

    pass


class WikipediaNotFoundError(WikipediaError):
    """HTTP 404 — Article does not exist in this language."""

    pass


class WikipediaTimeoutError(WikipediaError):
    """Request timeout."""

    pass


def _summary_cache_key(title: str, lang: str) -> str:
    return f"wikipedia:summary:{title}:{lang}"


def _article_cache_key(title: str, lang: str) -> str:
    return f"wikipedia:article:{title}:{lang}"


def _sections_cache_key(title: str, lang: str) -> str:
    return f"wikipedia:sections:{title}:{lang}"


def _categories_cache_key(title: str, lang: str) -> str:
    return f"wikipedia:categories:{title}:{lang}"


def _links_cache_key(title: str, lang: str) -> str:
    return f"wikipedia:links:{title}:{lang}"


def _mediawiki_api_url(base_template: str, lang: str, params: dict[str, str]) -> str:
    """Build MediaWiki action API URL (query.php)."""
    url_base = base_template.replace("{lang}", lang).rstrip("/")
    return f"{url_base}/w/api.php?{urlencode(params)}"


def _build_url(base: str, lang: str, path: str, title: str) -> str:
    """Build Wikipedia REST API URL."""
    url_base = base.replace("{lang}", lang).rstrip("/")
    encoded_title = quote(title.replace(" ", "_"), safe="")
    return f"{url_base}/api/rest_v1/page/{path}/{encoded_title}"


def _record_api_error(
    error_collector: ErrorCollector | None,
    ctx: TraceContext | None,
    category: str,
    severity: str,
    message: str,
    details: dict[str, Any],
) -> None:
    """Record error if collector and ctx available."""
    if error_collector is None:
        return
    trace_id = ctx._trace_id if ctx else None
    run_id = ctx._run_id if ctx else None
    command = ctx._command if ctx else None
    path = ctx._path if ctx else None
    error_collector.record(
        category=category,
        severity=severity,
        message=message,
        details=details,
        trace_id=trace_id,
        run_id=run_id,
        command=command,
        path=path,
    )


def _http_get(
    url: str,
    config: ApiConfig,
    ctx: TraceContext | None = None,
    allow_redirect: bool = True,
    error_collector: ErrorCollector | None = None,
) -> tuple[bytes, str]:
    """Perform HTTP GET. Returns (body, final_url). Follows redirects."""
    headers = {"User-Agent": config.user_agent}
    timeout = config.request_timeout_seconds

    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirect,
        )
    except requests.Timeout as e:
        _record_api_error(
            error_collector,
            ctx,
            "timeout",
            "error",
            f"Request timeout: {url}",
            {"url": url, "error": str(e)},
        )
        raise WikipediaTimeoutError(f"Request timeout: {url}") from e

    if resp.status_code == 404:
        _record_api_error(
            error_collector,
            ctx,
            "api",
            "warning",
            f"Article not found in this language: {url}",
            {"url": url, "status_code": 404},
        )
        raise WikipediaNotFoundError(
            f"Article not found in this language: {url}"
        ) from None

    if resp.status_code != 200:
        _record_api_error(
            error_collector,
            ctx,
            "api",
            "error",
            f"HTTP {resp.status_code}: {url}",
            {"url": url, "status_code": resp.status_code},
        )
        raise WikipediaError(f"HTTP {resp.status_code}: {url}") from None

    data: bytes = resp.content
    if ctx is not None:
        ctx.record_api_call(url, len(data))
    return data, resp.url


def _html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown with spec config and post-processing."""
    try:
        result = md(
            html,
            strip=["img", "script", "style"],
            heading_style="ATX",
            bullets="-",
        )
    except Exception:
        return html  # Graceful degradation: return raw text

    # Post-processing
    # Remove reference numbers [1], [23], [1][2]
    result = re.sub(r"\[\d+\](?:\[\d+\])*", "", result)
    # Remove empty paragraphs (multiple newlines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    # Normalize excessive whitespace
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r" *\n *", "\n", result)
    return result.strip()


def _slugify_anchor(text: str) -> str:
    """Create URL-safe anchor from heading text (Wikipedia-style)."""
    # Normalize unicode, lowercase, replace spaces with underscore
    normalized = unicodedata.normalize("NFKC", text)
    slug = re.sub(r"[^\w\s-]", "", normalized)
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")
    return slug or ""


class _SectionParser(HTMLParser):
    """Extract sections (h2, h3, h4) with id, level, and content from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.sections: list[tuple[str, int, str, str]] = []  # title, level, anchor, html
        self._current: list[str] = []
        self._in_heading = False
        self._heading_level = 0
        self._heading_id = ""
        self._heading_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("h2", "h3", "h4"):
            self._flush_content()
            self._in_heading = True
            self._heading_level = int(tag[1])
            self._heading_id = ""
            self._heading_text = []
            for k, v in attrs:
                if k == "id" and v:
                    self._heading_id = v
                    break
        tag_text = self.get_starttag_text()
        self._current.append(tag_text if tag_text else "")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h2", "h3", "h4") and self._in_heading:
            self._current.append(f"</{tag}>")
            title = "".join(self._heading_text).strip()
            anchor = self._heading_id or _slugify_anchor(title)
            self.sections.append((title, self._heading_level, anchor, "".join(self._current)))
            self._current = []
            self._in_heading = False
        else:
            self._current.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_text.append(data)
        self._current.append(data)

    def _flush_content(self) -> None:
        if self._current and self.sections:
            # Append to last section's content
            last = self.sections[-1]
            self.sections[-1] = (last[0], last[1], last[2], last[3] + "".join(self._current))
        self._current = []

    def get_sections(self) -> list[tuple[str, int, str, str]]:
        self._flush_content()
        if self._current and self.sections:
            last = self.sections[-1]
            self.sections[-1] = (last[0], last[1], last[2], last[3] + "".join(self._current))
        return self.sections


def _extract_sections_from_html(html: str) -> list[tuple[str, int, str, str]]:
    """Extract (title, level, anchor, html_content) from section HTML."""
    parser = _SectionParser()
    try:
        parser.feed(html)
        return parser.get_sections()
    except Exception:
        return []


def _word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


class WikipediaClient:
    """Wikipedia API client with caching and trace integration."""

    def __init__(
        self,
        config: ApiConfig,
        cache: Cache,
        error_collector: ErrorCollector | None = None,
    ) -> None:
        self._config = config
        self._cache = cache
        self._error_collector = error_collector
        self._base = config.wikipedia_base_url

    def get_summary(
        self,
        title: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> ArticleSummary:
        """Get article summary (lead section)."""
        key = _summary_cache_key(title, lang)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            data = json.loads(cached)
            return ArticleSummary(
                title=data["title"],
                extract=data["extract"],
                extract_markdown=data["extract_markdown"],
                description=data.get("description"),
                thumbnail_url=data.get("thumbnail_url"),
                page_url=data["page_url"],
            )

        url = _build_url(self._base, lang, "summary", title)
        cm = ctx.phase("get_summary") if ctx else nullcontext()
        with cm:
            data_bytes, _ = _http_get(url, self._config, ctx, error_collector=self._error_collector)
        data = json.loads(data_bytes)

        # Handle redirects
        if "redirect" in data:
            return self.get_summary(data["redirect"], lang, ctx)

        page_title = data.get("title", title)
        extract = data.get("extract", "") or ""
        extract_html = data.get("extract_html", "") or ""
        if extract_html:
            extract_markdown = _html_to_markdown(extract_html)
        else:
            extract_markdown = extract

        description = data.get("description")
        thumbnail = data.get("thumbnail", {})
        thumbnail_url = thumbnail.get("source") if isinstance(thumbnail, dict) else None

        content_urls = data.get("content_urls", {})
        desktop = content_urls.get("desktop", {}) if isinstance(content_urls, dict) else {}
        page_url = desktop.get("page", "") if isinstance(desktop, dict) else ""
        if not page_url:
            encoded = quote(page_title.replace(" ", "_"), safe="")
            page_url = f"https://{lang}.wikipedia.org/wiki/{encoded}"

        summary = ArticleSummary(
            title=page_title,
            extract=extract,
            extract_markdown=extract_markdown,
            description=description,
            thumbnail_url=thumbnail_url,
            page_url=page_url,
        )

        to_cache = json.dumps({
            "title": summary.title,
            "extract": summary.extract,
            "extract_markdown": summary.extract_markdown,
            "description": summary.description,
            "thumbnail_url": summary.thumbnail_url,
            "page_url": summary.page_url,
        }).encode()
        self._cache.set(key, to_cache)
        return summary

    def get_article(
        self,
        title: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> ArticleContent:
        """Get full article HTML and Markdown."""
        key = _article_cache_key(title, lang)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            data = json.loads(cached)
            return ArticleContent(
                title=data["title"],
                markdown=data["markdown"],
                html=data["html"],
                word_count=data["word_count"],
                page_url=data["page_url"],
            )

        url = _build_url(self._base, lang, "html", title)
        cm = ctx.phase("get_article") if ctx else nullcontext()
        with cm:
            html_bytes, _ = _http_get(url, self._config, ctx, error_collector=self._error_collector)
        html = html_bytes.decode("utf-8", errors="replace")

        # Extract body content (skip head)
        body_match = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.IGNORECASE)
        body_html = body_match.group(1) if body_match else html

        markdown = _html_to_markdown(body_html)
        word_count = _word_count(markdown)

        page_url = f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"

        content = ArticleContent(
            title=title,
            markdown=markdown,
            html=html,
            word_count=word_count,
            page_url=page_url,
        )

        to_cache = json.dumps({
            "title": content.title,
            "markdown": content.markdown,
            "html": content.html,
            "word_count": content.word_count,
            "page_url": content.page_url,
        }).encode()
        self._cache.set(key, to_cache)
        return content

    def get_page_categories(
        self,
        page_title: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> list[str]:
        """Category titles on a page (e.g. ``Kategorie:…`` / ``Category:…``), excluding hidden."""
        key = _categories_cache_key(page_title, lang)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            data = json.loads(cached)
            return list(data)

        params = {
            "action": "query",
            "format": "json",
            "redirects": "1",
            "titles": page_title.replace(" ", "_"),
            "prop": "categories",
            "cllimit": "500",
            "clshow": "!hidden",
        }
        url = _mediawiki_api_url(self._base, lang, params)
        cm = ctx.phase("mediawiki_categories") if ctx else nullcontext()
        with cm:
            data_bytes, _ = _http_get(
                url, self._config, ctx, error_collector=self._error_collector
            )
        payload = json.loads(data_bytes)
        if "error" in payload:
            raise WikipediaError(
                f"MediaWiki API error: {payload.get('error', {})}"
            )
        titles: list[str] = []
        for _pid, pg in payload.get("query", {}).get("pages", {}).items():
            if not isinstance(pg, dict):
                continue
            for c in pg.get("categories", []) or []:
                if isinstance(c, dict) and "title" in c:
                    titles.append(str(c["title"]))
        titles = sorted(set(titles))
        self._cache.set(key, json.dumps(titles).encode())
        return titles

    def get_page_links(
        self,
        page_title: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> list[str]:
        """Outgoing main-namespace (article) links from the page."""
        key = _links_cache_key(page_title, lang)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            data = json.loads(cached)
            return list(data)

        params = {
            "action": "query",
            "format": "json",
            "redirects": "1",
            "titles": page_title.replace(" ", "_"),
            "prop": "links",
            "plnamespace": "0",
            "pllimit": "500",
        }
        url = _mediawiki_api_url(self._base, lang, params)
        cm = ctx.phase("mediawiki_links") if ctx else nullcontext()
        with cm:
            data_bytes, _ = _http_get(
                url, self._config, ctx, error_collector=self._error_collector
            )
        payload = json.loads(data_bytes)
        if "error" in payload:
            raise WikipediaError(
                f"MediaWiki API error: {payload.get('error', {})}"
            )
        titles: list[str] = []
        for _pid, pg in payload.get("query", {}).get("pages", {}).items():
            if not isinstance(pg, dict):
                continue
            for ln in pg.get("links", []) or []:
                if isinstance(ln, dict) and "title" in ln:
                    titles.append(str(ln["title"]))
        titles = sorted(set(titles))
        self._cache.set(key, json.dumps(titles).encode())
        return titles

    def get_sections(
        self,
        title: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> list[Section]:
        """Get all sections of article. Parsed from HTML (mobile-sections deprecated)."""
        key = _sections_cache_key(title, lang)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            data = json.loads(cached)
            return [Section(**s) for s in data]

        content = self.get_article(title, lang, ctx)
        body_match = re.search(
            r"<body[^>]*>(.*)</body>",
            content.html,
            re.DOTALL | re.IGNORECASE,
        )
        body_html = body_match.group(1) if body_match else content.html

        raw_sections = _extract_sections_from_html(body_html)
        sections: list[Section] = []
        for s_title, level, anchor, s_html in raw_sections:
            s_md = _html_to_markdown(s_html)
            sections.append(
                Section(
                    title=s_title,
                    level=level,
                    markdown=s_md,
                    anchor=anchor,
                )
            )

        to_cache = json.dumps([
            {"title": s.title, "level": s.level, "markdown": s.markdown, "anchor": s.anchor}
            for s in sections
        ]).encode()
        self._cache.set(key, to_cache)
        return sections

    def get_section(
        self,
        title: str,
        section_name: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> Section | None:
        """Get single section by name. Returns None if not found."""
        sections = self.get_sections(title, lang, ctx)
        section_name_norm = section_name.strip().lower()
        for s in sections:
            if s.title.strip().lower() == section_name_norm:
                return s
        return None
