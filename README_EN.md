<div align="center">

# DeckView

**Lightweight Web Document Viewer + Markdown Online Editor**

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.1.0-orange)](https://github.com/your-repo/deckview)

[中文](README.md) | English

A Python-based local document server that supports online preview of PPT, PDF, Word, and Markdown files, with built-in Markdown creation and editing capabilities.

**Can be used as a self-hosted note-taking application** — use the scanned directory as your personal notebook or team knowledge base

</div>

---

## Features

### Core Features

| Feature | Description |
|:---:|:---|
| **Directory Scanning** | Start with a specified directory, automatically scan all document files |
| **Tree Navigation** | Left sidebar with tree structure, supports search, collapse, **resizable width** |
| **PPT/Word Preview** | Auto-convert to high-quality PDF for online preview |
| **PDF Preview** | Direct preview with zoom, pagination, **high-DPI screen optimization** |
| **Markdown Rendering** | GFM syntax support with code highlighting |
| **Markdown Editing** | Create and edit Markdown files online, live preview, auto-save |
| **File Upload** | Upload documents to specified directories |
| **Real-time Monitoring** | Auto-refresh directory tree on file changes (SSE push) |

### Enhanced Preview

| Feature | Description |
|:---:|:---|
| **Quick Preview** | Click file to preview on the right side without opening a new page |
| **Thumbnail Navigation** | Auto-generate high-resolution page thumbnails (600px) for PDF/PPT |
| **Drawing Annotation** | Draw annotations on PDF/PPT, multiple colors and line widths |
| **Eraser** | Erase annotations with adjustable size |
| **Undo/Redo** | Support undo and redo for annotation operations |
| **HD Rendering** | High-DPI screen support (Retina) for crisp display |

### Interface & Themes

| Feature | Description |
|:---:|:---|
| **Multiple Themes** | Light, Dark, Eye-care Green, Deep Blue Ocean |
| **Sidebar Adjustment** | Drag to resize sidebar width, settings auto-saved |
| **Responsive Layout** | Adapts to different screen sizes |

### Advanced Features

| Feature | Description |
|:---:|:---|
| **Service Registry** | Optional ServiceAtlas integration for service discovery |
| **Cache Management** | Auto-manage conversion cache, clean orphaned files |
| **Lossless Conversion** | PPT/Word to PDF with lossless compression, preserving image quality |

## Use Cases

- **Personal Notes** — Deploy locally or on a server, access and record notes anytime via browser
- **Team Knowledge Base** — LAN deployment for team document sharing and collaborative editing
- **Document Library** — Centralized management of PDF, PPT, Word, Markdown and other formats
- **Presentation Viewer** — Online PPT preview with annotation tools for presentations

## Quick Start

### Requirements

- **Python** 3.9+
- **LibreOffice** (optional, for PPT/Word to PDF conversion)

### Installation

```bash
# pip install (recommended)
pip install .

# Development mode installation
pip install -e .
```

### Start Service

```bash
# Basic usage - scan specified directory
deckview /path/to/your/docs

# Scan current directory
deckview .

# Specify port
deckview /path/to/docs -p 8080

# Allow LAN access
deckview /path/to/docs --host 0.0.0.0

# Development mode (auto-reload on code changes)
deckview /path/to/docs --reload
```

After starting, visit: **http://localhost:8000**

### CLI Arguments

```
deckview [directory] [options]

Positional arguments:
  directory              Document directory to scan (defaults to current directory)

Options:
  -p, --port PORT        Service port (default: 8000)
  --host HOST            Listen address (default: 127.0.0.1)
  --no-watch             Disable file change monitoring
  --reload               Development mode: auto-reload on code changes
  -v, --version          Show version number
  -h, --help             Show help
```

## Installing LibreOffice

PPT/Word conversion requires LibreOffice:

<table>
<tr>
<th>Ubuntu/Debian</th>
<th>macOS</th>
<th>Windows</th>
</tr>
<tr>
<td>

```bash
sudo apt install libreoffice-core
```

</td>
<td>

```bash
brew install libreoffice
```

</td>
<td>

Download and install from [libreoffice.org](https://www.libreoffice.org/)

</td>
</tr>
</table>

## Interface Guide

### Main Operations

- **Preview File**: Click a file on the left to quick preview on the right
- **Open Viewer**: Click "Open in Viewer" button to open full viewer in new page
- **Draw Annotations**: Click pen icon to annotate on PDF/PPT
- **Resize Sidebar**: Drag the sidebar right edge to adjust width, double-click to reset
- **Switch Theme**: Click theme button at bottom-right to change display theme
- **Create File**: Click "📝" button in toolbar to create new Markdown file
- **Upload File**: Click "📤" button in toolbar to upload documents

## Project Structure

```
DeckView/
├── pyproject.toml           # Package configuration
└── src/deckview/            # Python package
    ├── main.py              # FastAPI entry point
    ├── cli.py               # CLI entry point
    ├── api/library.py       # API routes
    ├── core/config.py       # Configuration management
    ├── services/            # Business logic layer
    │   ├── library.py       # File scanning service
    │   ├── watcher.py       # File monitoring service
    │   ├── conversion.py    # PPT/Word → PDF (lossless compression)
    │   ├── thumbnail.py     # Thumbnail generation
    │   ├── cache_manager.py # Cache management
    │   └── registry.py      # ServiceAtlas service registration
    └── web/                 # Frontend resources
        ├── templates/       # HTML templates
        └── static/          # CSS/JS
```

## API Reference

> API Documentation: http://localhost:8000/api/docs

| Endpoint | Method | Description |
|----------|:------:|-------------|
| `/api/library/tree` | GET | Get directory tree |
| `/api/library/files/{id}` | GET | Get file information |
| `/api/library/files/{id}/pdf` | GET | Get PDF file |
| `/api/library/files/{id}/thumbnails/{page}` | GET | Get thumbnail |
| `/api/library/files/{id}/content` | GET/PUT | Get/Update Markdown content |
| `/api/library/upload` | POST | Upload file |
| `/api/library/create` | POST | Create Markdown file |
| `/api/library/events` | GET | SSE event stream (file change notifications) |
| `/health` | GET | Health check |

## Environment Variables

| Variable | Default | Description |
|----------|:-------:|-------------|
| `DECKVIEW_HOST` | `127.0.0.1` | Listen address |
| `DECKVIEW_PORT` | `8000` | Service port |
| `DECKVIEW_DATA_DIR` | `~/.deckview` | Data directory (cached PDFs and thumbnails) |
| `LIBREOFFICE_PATH` | `soffice` | LibreOffice executable path |
| `CONVERSION_TIMEOUT` | `120` | Conversion timeout in seconds |
| `DECKVIEW_BASE_PATH` | (empty) | URL prefix for reverse proxy scenarios |

### Reverse Proxy Configuration (Base Path)

When DeckView is accessed through an authentication gateway (e.g., Aegis), set the `DECKVIEW_BASE_PATH` environment variable to ensure static resources and API requests work correctly.

**Scenario Description**:
- Direct access: `http://localhost:8080/` → No configuration needed
- Gateway proxy access: `http://aegis:8000/s/deckview/` → Set `DECKVIEW_BASE_PATH=/s/deckview`

**Startup Examples**:

```bash
# Direct access mode (no setting)
deckview /path/to/docs --host 127.0.0.1 --port 8080

# Through Aegis gateway proxy (set BASE_PATH)
DECKVIEW_BASE_PATH=/s/deckview deckview /path/to/docs --host 127.0.0.1 --port 8080
```

**Note**: After setting `DECKVIEW_BASE_PATH`, direct access to `http://localhost:8080/` will not work properly, as static resource and API paths will become `/s/deckview/static/...` and `/s/deckview/api/...`. Choose whether to set this based on your actual access method.

## Data Directory

DeckView stores cached data in `~/.deckview/`:

```
~/.deckview/
├── converted/      # Converted PDF files from PPT/Word
├── thumbnails/     # Page thumbnails
├── cache/          # Other cache
└── lo_profile/     # LibreOffice high-quality export configuration
```

Clear cache:
```bash
# Clear all cache (re-convert all files)
rm -rf ~/.deckview/converted/* ~/.deckview/thumbnails/*
```

## Notes

- Listens on `127.0.0.1` by default, local access only
- Use `--host 0.0.0.0` for external access, but be mindful of security
- **When using as a note-taking app**: Recommend internal network deployment only, or add authentication via reverse proxy
- Ensure the scanned directory has write permissions to support create and edit features
- PPT/Word conversion depends on LibreOffice, first conversion may be slow
- Lossless compression is used for conversion, resulting in larger but higher-quality PDF files
- Regularly backup important files in your notes directory

## Future Plans

<details>
<summary><b>PPT Animation Playback Support</b></summary>

Currently PPT files are previewed by converting to PDF, which cannot preserve animations and transitions. Possible future improvements:

| Solution | Description | Pros | Cons |
|----------|-------------|------|------|
| **OnlyOffice** | Integrate OnlyOffice Document Server | Open source, free, supports presentation mode | Complex deployment, high resource usage |
| **Collabora Online** | Online version based on LibreOffice | Open source, supports presentation mode | Limited support for complex animations |
| **PPTX → Video** | Export PPT to MP4 video | Full animation preservation | Loses interactivity |
| **Commercial SDK** | Commercial solutions like Aspose.Slides | High fidelity, HTML5 output | Requires paid license |

If you have specific needs, feel free to open an Issue for discussion.

</details>

## License

[MIT License](LICENSE)

---

<div align="center">

**If this project helps you, please consider giving it a Star!**

</div>
