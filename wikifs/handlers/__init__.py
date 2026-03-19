"""Request handlers and handler registry."""

from __future__ import annotations

from typing import Any

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient
from wikifs.cache import Cache
from wikifs.config import ApiConfig
from wikifs.errors import ErrorCollector
from wikifs.handlers.article import ArticleHandler
from wikifs.handlers.classes import ClassesHandler
from wikifs.handlers.entity import EntityHandler
from wikifs.handlers.page_nav import PageNavHandler
from wikifs.handlers.properties import PropertiesHandler
from wikifs.handlers.relations import RelationsHandler
from wikifs.handlers.search import SearchHandler
from wikifs.models import Handler, HandlerConfig


def create_handler_config(config_dict: dict[str, Any]) -> HandlerConfig:
    """Create HandlerConfig from loaded config dict."""
    wikifs = config_dict.get("wikifs", {})
    pagination = config_dict.get("pagination", {})
    return HandlerConfig(
        default_language=str(wikifs.get("default_language", "de")),
        supported_languages=list(wikifs.get("supported_languages", ["de", "en"])),
        pagination_default_limit=int(pagination.get("default_limit", 100)),
        pagination_max_limit=int(pagination.get("max_limit", 500)),
    )


def create_handlers(
    api_config: ApiConfig,
    cache: Cache,
    handler_config: HandlerConfig,
    error_collector: ErrorCollector | None = None,
) -> tuple[dict[str, Handler], WikidataClient]:
    """Create all handlers with shared dependencies. Returns (handlers, wikidata)."""
    wikidata = WikidataClient(api_config, cache, error_collector)
    wikipedia = WikipediaClient(api_config, cache, error_collector)
    entity = EntityHandler(wikidata, wikipedia, handler_config)
    properties = PropertiesHandler(wikidata, wikipedia, handler_config)
    relations = RelationsHandler(wikidata, wikipedia, handler_config)
    article = ArticleHandler(wikidata, wikipedia, handler_config)
    classes = ClassesHandler(wikidata, wikipedia, handler_config)
    search = SearchHandler(wikidata, wikipedia, handler_config)
    page_nav = PageNavHandler(wikidata, wikipedia, handler_config)
    return {
        "entity.list_entity": entity,
        "entity.get_meta": entity,
        "properties.list_properties": properties,
        "properties.get_property": properties,
        "properties.get_all_properties": properties,
        "relations.list_relations": relations,
        "relations.list_relation_targets": relations,
        "article.get_article": article,
        "article.get_article_lang": article,
        "article.get_summary": article,
        "article.list_sections": article,
        "article.get_section": article,
        "classes.list_classes": classes,
        "classes.list_class_members": classes,
        "classes.list_class_segment": classes,
        "search.entities": search,
        "search.sparql_query": search,
        "page_nav.list_categories": page_nav,
        "page_nav.get_category_md": page_nav,
        "page_nav.list_links": page_nav,
        "page_nav.get_link_md": page_nav,
    }, wikidata
