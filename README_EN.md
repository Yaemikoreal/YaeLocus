# YaeLocus - Geocoding + Route Planning + AI Analysis

**[English](README_EN.md) | [中文](README.md)**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.7.0](https://img.shields.io/badge/version-1.7.0-green.svg)](https://github.com/Yaemikoreal/YaeLocus)
[![PyPI](https://img.shields.io/badge/pypi-yaelocus-blue.svg)](https://pypi.org/project/yaelocus/)
[![Ink TUI](https://img.shields.io/badge/TUI-Ink%20%2B%20React-9cf.svg)](https://github.com/vadimdemedes/ink)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)

**Author: [Yaemikoreal](https://github.com/Yaemikoreal)**

A geocoding tool based on multi-API hybrid calls, supporting batch address conversion, high-performance caching, route planning, itinerary optimization, AI data analysis, and interactive terminal interface.

**Project URL**: https://github.com/Yaemikoreal/YaeLocus

## Features

### Core Features
- **Multi-API Rotation**: Smart rotation of Amap/Baidu/Tianditu APIs, total free quota 21,000 calls/day
- **High-performance Cache**: SQLite + WAL persistence, delayed commit optimization, resume from breakpoint
- **Coordinate Conversion**: Auto-convert to WGS-84 coordinate system, supports GCJ-02/BD-09 bidirectional conversion
- **Reverse Geocoding**: Convert coordinates to address
- **Multi-format Support**: CSV, Excel, JSON, GeoJSON input/output

### Map & Visualization
- **Interactive Maps**: Point clustering + heatmap + route visualization (Folium + Amap tiles)
- **Map Generation**: Batch result maps, route maps, AI analysis panels

### New Features (v1.7.0)
- **Geocoding Precision Enhancement**: New precision level detection, province/city/district level results auto-marked as untrustworthy
- **Smart Retry Strategy**: Single address encoding continues trying other APIs if first result has insufficient confidence
- **Batch Encoding Field Expansion**: Batch results now include formatted_address, province/city/district, precision level, status fields
- **CSV Write Safety Mechanism**: File lock + retry (3 times) + fallback path, prevents concurrent write conflicts
- **Cache Corruption Recovery Enhancement**: Corrupted database auto-backup (`.corrupted.{timestamp}`) before rebuild

### Previous Version (v1.6.0)
- **Route Planning**: Multi-mode route planning (walking/driving/transit), supports AI engine and API engine
- **Itinerary Optimization**: DBSCAN clustering + TSP solver, multi-strategy route recommendations
- **AI Features**: Integrated DeepSeek/Qwen/GLM/Moonshot, supports data analysis and route planning conversations
- **Ink TUI**: React + Ink 5 terminal interface, communicates with Python backend via FastAPI
- **API Server**: FastAPI headless service, supports SSE streaming response
- **Backward Compatibility**: Old commands auto-redirect to new grouped commands

## Installation

### Version Selection

| Version | Description | Install Command |
|---------|-------------|-----------------|
| **CLI-only Stable** (Recommended) | CLI only, suitable for AI Agents and daily use | `pip install yaelocus` |
| **Full Beta** | Includes Web API + AI features, TUI requires extra installation | `pip install "yaelocus[beta]"` |

### extras Groups

```bash
pip install yaelocus              # CLI-only stable version
pip install "yaelocus[ai]"        # + AI features
pip install "yaelocus[web]"       # + Web API server
pip install "yaelocus[beta]"      # + AI + Web (full beta version)
pip install "yaelocus[dev]"       # + development testing tools
```

### PyPI Installation (Recommended)

```bash
pip install yaelocus
```

### Source Installation

```bash
git clone https://github.com/Yaemikoreal/YaeLocus.git
cd YaeLocus
pip install -e .                    # CLI-only stable version
pip install -e ".[beta]"            # Full beta version
pip install -e ".[dev,beta]"        # Development environment
```

### Windows One-click Installation

Double-click `install.bat` for automatic installation.

### Ink TUI Installation (Optional for Beta)

```bash
cd tui && npm install && npm run build
```

## Configuration

```bash
yaelocus config setup               # Interactive configuration wizard
```

Configure at least one API key:

| API | Free Quota | Coordinate System | Apply URL |
|-----|------------|-------------------|-----------|
| Amap | 5,000/day | GCJ-02 | https://lbs.amap.com |
| Tianditu | 10,000/day | CGCS2000 | https://www.tianditu.gov.cn |
| Baidu | 6,000/day | BD-09 | https://lbsyun.baidu.com |

**AI Feature Configuration** (Optional):

```
AI_ENABLED=true
AI_PROVIDER=deepseek              # deepseek/qwen/glm/moonshot
DEEPSEEK_API_KEY=xxx              # Corresponding API Key
```

## CLI Commands

### Group Structure

Run without arguments to start interactive TUI:

```bash
yaelocus                          # Launch Ink TUI (preferred) or Rich TUI (fallback)
```

#### geocode - Geocoding

```bash
yaelocus geocode single "北京市朝阳区"         # Single address conversion
yaelocus geocode single "天安门" --json        # JSON output
yaelocus geocode batch -i data/清单.xlsx       # Batch conversion
yaelocus geocode batch -i data/清单.xlsx -w 5  # 5 threads parallel
yaelocus geocode batch -i data/清单.xlsx -f xlsx --skip-cached
yaelocus geocode reverse 39.9 116.4            # Reverse geocoding
yaelocus geocode reverse 39.9 116.4 --json
yaelocus geocode convert 39.9 116.4 --from gcj02 --to wgs84
yaelocus geocode convert 39.9 116.4 --from bd09 --to wgs84 --json
```

#### map - Map & Visualization

```bash
yaelocus map list                 # List processable files in data/
yaelocus map list --detail        # Show detailed info
yaelocus map create -i output/csv/结果.csv -t "My Map"
```

#### ai - AI Features

```bash
yaelocus ai chat "Analyze this data" -i output/csv/结果.csv
yaelocus ai analyze -i output/csv/结果.csv    # Data analysis
yaelocus ai route -i output/csv/结果.csv      # AI route planning
```

#### config - Configuration Management

```bash
yaelocus config setup             # Interactive configuration
yaelocus config check             # Environment diagnostics
yaelocus config test-api          # Test API connectivity
yaelocus config cache stats       # Cache statistics
yaelocus config cache stats --json
yaelocus config cache clear       # Clear cache
yaelocus config cache cleanup     # Cleanup expired records
yaelocus config cache export      # Export cache JSON
```

#### serve - API Server

```bash
yaelocus serve                    # Start API server + Ink TUI
yaelocus serve --web              # Legacy Web interface
yaelocus serve --no-gui           # API server only

# Headless mode (for frontend calls)
python -m geocode.api --port 8765
python -m geocode.api --port 0    # Random port
```

### Backward Compatibility

Old commands auto-redirect to new grouped commands:

| Old Command | New Command | Description |
|-------------|-------------|-------------|
| `yaelocus run -i <file>` | `yaelocus geocode batch -i <file>` | Batch conversion |
| `yaelocus geocode "address"` | `yaelocus geocode single "address"` | Single address |
| `yaelocus reverse` | `yaelocus geocode reverse` | Reverse geocoding |
| `yaelocus convert` | `yaelocus geocode convert` | Coordinate conversion |
| `yaelocus cache stats` | `yaelocus config cache stats` | Cache stats |
| `yaelocus files` | `yaelocus map list` | File list |
| `yaelocus doctor` | `yaelocus config check` | Environment diagnostics |
| `yaelocus config` | `yaelocus config setup` | Configuration wizard |
| `yaelocus ai "message"` | `yaelocus ai chat "message"` | AI chat |
| `yaelocus route` | `yaelocus ai route` | Route planning |

## Python API

```python
from geocode import Geocoder, CacheManager, create_map, ItineraryOptimizer

# Basic usage: context manager auto-closes
with CacheManager() as cache:
    geocoder = Geocoder(cache)

    # Single address conversion -> dict
    result = geocoder.geocode("北京市朝阳区建国路88号")
    print(result['longitude'], result['latitude'])

    # Reverse geocoding
    addr = geocoder.reverse_geocode(39.9, 116.4)
    print(addr['formatted_address'])

    # Batch conversion -> list[dict]
    results = geocoder.batch_geocode(["Address1", "Address2", "Address3"])

# Map visualization
valid = [r for r in results if r.get("success")]
create_map(valid, output_file="output/map/result_map.html")

# Itinerary optimization (DBSCAN clustering + TSP solver)
optimizer = ItineraryOptimizer()
optimizer.analyze(valid)                # Cluster analysis
routes = optimizer.recommend_routes()   # Multi-strategy route recommendations

# AI features (optional module)
from geocode import AIClient
client = AIClient()
response = client.chat("Analyze the distribution of these locations", context=str(valid))
```

## TUI Dual Mode

Auto-select when running `yaelocus` without arguments:

| Mode | Technology | Condition |
|------|------------|-----------|
| **Ink TUI** | React + Ink 5 + FastAPI | Node.js available + tui/node_modules exists |
| **Rich TUI** | Python + Rich | Fallback solution |

**Ink TUI Features**:
- 8 components: Messages, PromptInput, MapPicker, HelpPanel, Toast, etc.
- 4 hooks: useStream (SSE streaming), useAPI, useCommandHistory, useTypeahead
- Agent Loop: Supports `[CMD]...[/CMD]` protocol for command execution
- Port negotiation: API server writes to `~/.yaelocus_port.json` on startup

## Project Structure

```
geocode-tool/
├── geocode/                  # Core modules
│   ├── __init__.py           # Public API export (__version__ = "1.7.0")
│   ├── geocoder.py           # Geocoding core
│   ├── cache.py              # SQLite cache (WAL + delayed commit)
│   ├── config.py             # API keys + OutputPaths
│   ├── coords.py             # Coordinate conversion (gcj02/bd09/wgs84)
│   ├── api.py                # FastAPI headless server
│   ├── router.py             # RouteWizard interactive wizard
│   ├── map_visualizer.py     # Folium map generation
│   ├── models.py             # GeocodeResult, APILog dataclass
│   ├── errors.py             # GeocodeError exception hierarchy
│   │
│   ├── cli/                  # CLI group structure
│   │   ├── app.py            # Typer entry + deprecated aliases
│   │   ├── groups.py         # Four subcommand groups
│   │   ├── repl.py           # Rich TUI (~1065 lines)
│   │   ├── utils.py          # Console + CITY_COORDS
│   │   ├── completions.py    # Command completion engine
│   │   ├── theme.py          # TUI semantic colors
│   │   └── commands/         # Command implementations
│   │
│   ├── ai/                   # AI module (optional)
│   │   ├── client.py         # AIClient (streaming/non-streaming)
│   │   ├── providers.py      # DeepSeek/Qwen/GLM/Moonshot
│   │   └── system_prompt.py  # TUI Agent dynamic prompt
│   │
│   ├── routing/              # Route planning
│   │   ├── models.py         # RoutePoint, RouteResult, TravelMode
│   │   ├── directions.py     # DirectionsClient (Amap/Baidu)
│   │   ├── planner.py        # RoutePlanner
│   │   └── ai_engine.py      # AIDirectionEngine
│   │
│   ├── optimizer/            # Itinerary optimization
│   │   ├── analyzer.py       # LocationAnalyzer (DBSCAN)
│   │   ├── planner.py        # RouteRecommender
│   │   ├── tsp.py            # TSP solver (greedy + 2-opt)
│   │   └── models.py         # LocationCluster, RecommendedRoute
│   │
│   └── web/                  # Legacy Web GUI
│       └── app.py            # Inline HTML template
│
├── tui/                      # Ink TUI (React + Ink 5)
│   ├── package.json          # Dependencies and build scripts
│   ├── src/
│   │   └── index.tsx         # Entry component
│   │   └── components/       # 8 UI components
│   │   └── hooks/            # 4 React hooks
│   └── dist/
│       └── index.js          # esbuild bundle output
│
├── tests/                    # pytest test suite
├── data/                     # Input data directory
├── output/                   # Output directory
│   ├── csv/                  # Conversion results
│   ├── map/                  # Map HTML
│   ├── database/             # SQLite cache
│   ├── log/                  # API call logs
│   └── export/               # Export files
│
├── skills/                   # Claude Code Skill
│   └── yaelocus.md           # AI call skill definition
├── install.bat               # Windows one-click install
├── pyproject.toml            # Project configuration
├── CHANGELOG.md              # Update log
└── .env.example              # API key template
```

## API Server

FastAPI headless service for Ink TUI or other frontends:

| Endpoint | Description |
|----------|-------------|
| `/api/health` | Health check |
| `/api/config` | Configuration info |
| `/api/geocode/single` | Single address conversion |
| `/api/geocode/batch` | Batch conversion |
| `/api/geocode/reverse` | Reverse geocoding |
| `/api/geocode/convert` | Coordinate conversion |
| `/api/chat` | AI chat |
| `/api/chat/stream` | SSE streaming AI chat |
| `/api/cache/stats` | Cache statistics |
| `/api/files` | File browsing |
| `/api/execute` | Command execution (TUI Agent protocol) |

## FAQ

**Q: Command not found on first run?**
```bash
pip install yaelocus
yaelocus config check
```

**Q: API quota exhausted?**
The tool auto-rotates three APIs, total 21,000 calls/day.

**Q: Ink TUI won't start?**
```bash
cd tui && npm install && npm run build
```

**Q: How to get API keys?**
- Amap: https://lbs.amap.com (Register → Console → App Management → Create App → Add Key)
- Tianditu: https://www.tianditu.gov.cn (Register → Resources → Apply for Key)
- Baidu: https://lbsyun.baidu.com (Register → Console → Create App)

**Q: How to uninstall?**
```bash
pip uninstall yaelocus
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## License

[MIT License](LICENSE)

---

**YaeLocus** - Made with ❤️ by [Yaemikoreal](https://github.com/Yaemikoreal)