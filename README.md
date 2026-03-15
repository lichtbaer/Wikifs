# WikiFS

Virtual Filesystem over Wikipedia & Wikidata for AI Agents.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# oder: .venv\Scripts\activate  # Windows

pip install -e .
```

## Usage

```bash
wikifs --help
wikifs --version
wikifs ls
wikifs cat
wikifs search
# ... weitere Subcommands
```

## Development

```bash
ruff check .
mypy --strict wikifs/
pytest
```
