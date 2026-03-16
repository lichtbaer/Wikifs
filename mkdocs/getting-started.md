# Getting Started

Run your first WikiFS command in under 5 minutes.

## Prerequisites

- Python 3.11 or later
- Internet connection (Wikipedia and Wikidata APIs)

## Installation

```bash
# Clone the repository
git clone https://github.com/Lichtbaer/wikifs.git
cd wikifs

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install WikiFS
pip install -e .
```

## First Command

List the contents of an entity directory:

```bash
wikifs ls /wiki/entities/Frankfurt_am_Main/
```

Expected output (excerpt):

```
article.md
summary.md
properties/
relations/
sections/
meta.json
```

## Next Steps

1. **Read an article**: `wikifs cat /wiki/entities/Frankfurt_am_Main/article.md`
2. **Read a property**: `wikifs cat /wiki/entities/Frankfurt_am_Main/properties/population.txt`
3. **Search entities**: `wikifs search "Goethe" --type entity --limit 5`
4. **Grep within files**: `wikifs grep "Frankfurt" /wiki/entities/Frankfurt_am_Main/summary.md`

See the [Command Reference](commands/index.md) for syntax, flags, and more examples.
