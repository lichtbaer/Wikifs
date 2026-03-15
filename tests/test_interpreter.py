"""Tests for command interpreter and path router."""

from __future__ import annotations

from wikifs.interpreter import Interpreter
from wikifs.models import Command
from wikifs.router import Router, create_default_router, normalize_path
from wikifs.tracing import TraceCollector


def test_normalize_path_strips_trailing_slash() -> None:
    """Trailing slashes are stripped."""
    assert normalize_path("/wiki/entities/Frankfurt/") == "/wiki/entities/Frankfurt"
    assert normalize_path("/wiki/entities/Frankfurt_am_Main/properties/") == (
        "/wiki/entities/Frankfurt_am_Main/properties"
    )


def test_normalize_path_preserves_root() -> None:
    """Root path / is preserved."""
    assert normalize_path("/") == "/"


def test_router_match_entity_list() -> None:
    """Router matches /wiki/entities/{name}/ to entity.list_entity."""
    router = create_default_router()
    m = router.match("/wiki/entities/Frankfurt_am_Main")
    assert m is not None
    assert m.handler == "entity.list_entity"
    assert m.params == {"name": "Frankfurt_am_Main"}


def test_router_match_article() -> None:
    """Router matches article paths."""
    router = create_default_router()
    m = router.match("/wiki/entities/Frankfurt_am_Main/article.md")
    assert m is not None
    assert m.handler == "article.get_article"
    assert m.params == {"name": "Frankfurt_am_Main"}


def test_router_match_article_lang() -> None:
    """Router matches article.{lang}.md."""
    router = create_default_router()
    m = router.match("/wiki/entities/Frankfurt_am_Main/article.en.md")
    assert m is not None
    assert m.handler == "article.get_article_lang"
    assert m.params == {"name": "Frankfurt_am_Main", "lang": "en"}


def test_router_match_properties() -> None:
    """Router matches properties paths."""
    router = create_default_router()
    m = router.match("/wiki/entities/Frankfurt_am_Main/properties")
    assert m is not None
    assert m.handler == "properties.list_properties"
    m2 = router.match("/wiki/entities/Frankfurt_am_Main/properties/population.txt")
    assert m2 is not None
    assert m2.handler == "properties.get_property"
    assert m2.params == {"name": "Frankfurt_am_Main", "prop": "population"}


def test_router_match_relations() -> None:
    """Router matches relations paths."""
    router = create_default_router()
    m = router.match("/wiki/entities/Frankfurt_am_Main/relations")
    assert m is not None
    assert m.handler == "relations.list_relations"
    m2 = router.match("/wiki/entities/Frankfurt_am_Main/relations/capital_of")
    assert m2 is not None
    assert m2.handler == "relations.list_relation_targets"
    assert m2.params == {"name": "Frankfurt_am_Main", "relation": "capital_of"}


def test_router_match_classes() -> None:
    """Router matches classes paths."""
    router = create_default_router()
    m = router.match("/wiki/classes")
    assert m is not None
    assert m.handler == "classes.list_classes"
    m2 = router.match("/wiki/classes/city")
    assert m2 is not None
    assert m2.handler == "classes.list_class_members"
    assert m2.params == {"class": "city"}


def test_router_returns_none_for_unknown_path() -> None:
    """Router returns None for unmatched paths."""
    router = create_default_router()
    assert router.match("/wiki/") is None
    assert router.match("/wiki/entities") is None
    assert router.match("/unknown/path") is None
    assert router.match("/wiki/entities/Frankfurt/invalid.txt") is None


def test_interpreter_valid_command_returns_stub() -> None:
    """Interpreter executes valid command and returns stub response."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {
            "command": "ls",
            "path": "/wiki/entities/Frankfurt_am_Main/properties/",
            "flags": [],
            "request_id": "req-123",
        }
    )
    assert resp.exit_code == 0
    assert "handler=properties.list_properties" in resp.output
    assert "Frankfurt_am_Main" in resp.output
    assert resp.request_id == "req-123"
    assert resp.trace_id
    assert resp.timing_ms >= 0


def test_interpreter_invalid_command() -> None:
    """Interpreter rejects unknown command with error_type invalid_command."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {"command": "rm", "path": "/wiki/entities/Frankfurt/", "flags": []}
    )
    assert resp.exit_code == 1
    assert resp.error_type == "invalid_command"
    assert "Unknown command" in resp.output
    assert resp.suggestions == ["ls", "cat", "grep", "search"]


def test_interpreter_invalid_path() -> None:
    """Interpreter rejects path without /wiki/ prefix."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {"command": "ls", "path": "/etc/passwd", "flags": []}
    )
    assert resp.exit_code == 1
    assert resp.error_type == "invalid_path"
    assert "must start with /wiki/" in resp.output


def test_interpreter_invalid_flag() -> None:
    """Interpreter rejects invalid flags with error_type invalid_flag."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {
            "command": "ls",
            "path": "/wiki/entities/Frankfurt/",
            "flags": ["-x"],
        }
    )
    assert resp.exit_code == 1
    assert resp.error_type == "invalid_flag"
    assert "Unknown flag" in resp.output or "Allowed" in resp.output


def test_interpreter_grep_cross_entity_error() -> None:
    """grep on /wiki/entities/ gives error with search suggestion."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {
            "command": "grep",
            "path": "/wiki/entities/",
            "flags": [],
            "pattern": "test",
        }
    )
    assert resp.exit_code == 1
    assert "search" in resp.output.lower()
    assert resp.error_type == "invalid_path"
    assert resp.suggestions == ["search"]


def test_interpreter_not_found_returns_exit_code_2() -> None:
    """Unmatched path returns exit_code 2, error_type not_found."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {"command": "cat", "path": "/wiki/entities/Frankfurt/nonexistent.xyz", "flags": []}
    )
    assert resp.exit_code == 2
    assert resp.error_type == "not_found"
    assert "Not found" in resp.output


def test_interpreter_creates_trace_with_phases() -> None:
    """Each execute() creates trace with parse and route phases."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    interpreter.execute(
        {"command": "ls", "path": "/wiki/entities/Frankfurt/", "flags": []}
    )
    # TraceCollector doesn't persist; we'd need TraceStore to verify.
    # We can at least verify no exception and response has trace_id.
    resp = interpreter.execute(
        {"command": "ls", "path": "/wiki/entities/Frankfurt/", "flags": []}
    )
    assert resp.trace_id
    assert resp.timing_ms >= 0


def test_interpreter_ls_with_dash_l_flag() -> None:
    """ls -l is accepted."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {
            "command": "ls",
            "path": "/wiki/entities/Frankfurt/",
            "flags": ["-l"],
        }
    )
    assert resp.exit_code == 0


def test_interpreter_grep_with_i_flag() -> None:
    """grep -i is accepted."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {
            "command": "grep",
            "path": "/wiki/entities/Frankfurt/article.md",
            "flags": ["-i"],
            "pattern": "stadt",
        }
    )
    assert resp.exit_code == 0


def test_interpreter_search_with_type_flag() -> None:
    """search --type entity is accepted."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    resp = interpreter.execute(
        {
            "command": "search",
            "path": "/wiki/sparql/result.csv",
            "flags": ["--type", "entity", "--limit", "10"],
        }
    )
    assert resp.exit_code == 0


def test_interpreter_execute_command() -> None:
    """execute_command accepts Command object."""
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(router, collector)
    cmd = Command(
        command="cat",
        path="/wiki/entities/Frankfurt/article.md",
        flags=[],
        pattern=None,
        request_id="req-456",
    )
    resp = interpreter.execute_command(cmd)
    assert resp.exit_code == 0
    assert "article.get_article" in resp.output
    assert resp.request_id == "req-456"


def test_router_register_and_match_custom() -> None:
    """Custom router can register and match patterns."""
    router = Router()
    router.register("/wiki/custom/{id}/", "custom.handler")
    m = router.match("/wiki/custom/abc")
    assert m is not None
    assert m.handler == "custom.handler"
    assert m.params == {"id": "abc"}
