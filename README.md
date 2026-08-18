# Pharma

Project for managing pharmacy data with a FastAPI backend and a Streamlit frontend.

Personalized Genomic Decision Support prototype: upload a VCF, get clinically
annotated variants (gene, mutation, disease, targeted drug, evidence tier) from
a CIViC-derived knowledge base, visualized in a table and an interactive
knowledge graph, with an exportable PDF clinical report.

## Requirements

- Python 3 (with `venv` support)
- Linux/macOS for `run.sh` or Windows with PowerShell for `run.ps1`

## Quick start

Run the script for your platform:

```bash
# for Linux/macos
./run.sh

# Windows
.\run.ps1
```

Creates an environment

Once started:

- Backend: http://127.0.0.1:8000
- Frontend: http://localhost:8501

Press `Ctrl+C` to stop both services.

## Backend API

| Endpoint | Method | Description |
| --- | --- | --- |
| `/health` | GET | Liveness check |
| `/api/v1/analyze` | POST | Upload a VCF → annotated variants as JSON (`file` form field) |
| `/api/v1/report` | POST | Upload a VCF → downloadable PDF clinical report |
| `/api/v1/graph` | POST | Upload a VCF → self-contained HTML knowledge graph |

Interactive API docs at http://127.0.0.1:8000/docs.

## Clinical knowledge base

The SQLite database (`backend/data/raw/clinical_kb.db`) ships with ~2,500 real
CIViC evidence records, so the app works offline out of the box. To refresh it
from the latest CIViC release (requires network):

```bash
cd backend
../.venv/bin/python -m app.db.bootstrap
```

The script falls back to a curated 4-record panel if the download fails.

## Frontend configuration

The backend URL can be overridden with an environment variable:

```bash
PHARMA_BACKEND_URL=http://127.0.0.1:9000 ./run.sh --backend-port 9000
```

## Tests

```bash
.venv/bin/python -m pytest backend/tests -q
```

## run.sh (Linux / macOS)

Usage:

```bash
./run.sh [options]
```

Options:

| Option | Description | Default |
| --- | --- | --- |
| `--backend-host HOST` | Backend bind host | `127.0.0.1` |
| `--backend-port PORT` | Backend bind port | `8000` |
| `--frontend-port PORT` | Streamlit frontend port | `8501` |
| `--skip-install` | Skip venv creation and pip install | off |
| `-h`, `--help` | Show help | - |

Example with custom ports:

```bash
./run.sh --backend-port 9000 --frontend-port 9001
```

## run.ps1 (Windows)

Usage:

```powershell
.\run.ps1 [-BackendHost HOST] [-BackendPort PORT] [-FrontendPort PORT] [-SkipInstall]
```

Parameters:

| Parameter | Description | Default |
| --- | --- | --- |
| `-BackendHost HOST` | Backend bind host | `127.0.0.1` |
| `-BackendPort PORT` | Backend bind port | `8000` |
| `-FrontendPort PORT` | Streamlit frontend port | `8501` |
| `-SkipInstall` | Skip venv creation and pip install | off |

Example with custom ports:

```powershell
.\run.ps1 -BackendPort 9000 -FrontendPort 9001
```

If PowerShell blocks script execution, allow it with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
