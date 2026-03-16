"""Path router — regex-based route matching for WikiFS."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RouteMatch:
    """Result of a successful route match."""

    handler: str  # Handler name
    params: dict[str, str]  # Extracted path parameters
    pattern: str  # The matched pattern


class Router:
    """Routes paths to handler names using regex patterns."""

    def __init__(self) -> None:
        self._routes: list[tuple[re.Pattern[str], str, list[str]]] = []

    def register(self, pattern: str, handler_name: str) -> None:
        """Register a route pattern. Use {name} for named capture groups."""
        # Escape regex special chars first, then replace {param} with capture groups
        regex_pattern = re.escape(pattern)
        param_names: list[str] = []
        for match in re.finditer(r"\\\{(\w+)\\\}", regex_pattern):
            param_name = match.group(1)
            param_names.append(param_name)
            regex_pattern = regex_pattern.replace(
                match.group(0), f"(?P<{param_name}>[^/]+)", 1
            )
        # Trailing slash optional (paths are normalized to no trailing slash)
        if regex_pattern.endswith("/"):
            regex_pattern = regex_pattern[:-1] + "/?"
        # Anchor start and end
        if not regex_pattern.startswith("^"):
            regex_pattern = "^" + regex_pattern
        if not regex_pattern.endswith("$"):
            regex_pattern = regex_pattern + "$"
        compiled = re.compile(regex_pattern)
        self._routes.append((compiled, handler_name, param_names))

    def match(self, path: str) -> RouteMatch | None:
        """Match path against registered routes. Returns RouteMatch or None."""
        for compiled, handler_name, param_names in self._routes:
            m = compiled.match(path)
            if m:
                params = {name: m.group(name) for name in param_names}
                return RouteMatch(
                    handler=handler_name,
                    params=params,
                    pattern=compiled.pattern,
                )
        return None


def normalize_path(path: str) -> str:
    """Normalize path: strip trailing slashes."""
    if path == "/":
        return path
    return path.rstrip("/") or "/"


def create_default_router() -> Router:
    """Create router with all WikiFS route patterns registered."""
    router = Router()
    router.register("/wiki/entities/{name}/", "entity.list_entity")
    router.register("/wiki/entities/{name}/article.md", "article.get_article")
    router.register(
        "/wiki/entities/{name}/article.{lang}.md", "article.get_article_lang"
    )
    router.register("/wiki/entities/{name}/summary.md", "article.get_summary")
    router.register(
        "/wiki/entities/{name}/properties/", "properties.list_properties"
    )
    router.register(
        "/wiki/entities/{name}/properties/{prop}.txt",
        "properties.get_property",
    )
    router.register(
        "/wiki/entities/{name}/properties/_all.json",
        "properties.get_all_properties",
    )
    router.register(
        "/wiki/entities/{name}/relations/", "relations.list_relations"
    )
    router.register(
        "/wiki/entities/{name}/relations/{relation}/",
        "relations.list_relation_targets",
    )
    router.register(
        "/wiki/entities/{name}/sections/", "article.list_sections"
    )
    router.register(
        "/wiki/entities/{name}/sections/{section}.md",
        "article.get_section",
    )
    router.register(
        "/wiki/entities/{name}/meta.json", "entity.get_meta"
    )
    router.register("/wiki/classes/", "classes.list_classes")
    router.register(
        "/wiki/classes/{class}/{segment}/",
        "classes.list_class_segment",
    )
    router.register("/wiki/classes/{class}/", "classes.list_class_members")
    router.register("/wiki/search", "search.entities")
    router.register("/wiki/sparql/result.csv", "search.sparql_query")
    return router
