# Third-party notices

Fortune Copilot itself is distributed under the MIT License. The application uses the following principal third-party runtime components; each remains governed by its own license and upstream notices.

| Component | Role | License |
| --- | --- | --- |
| React / React DOM | Browser UI runtime | MIT |
| Apache ECharts | Local SVG charts | Apache-2.0 |
| FastAPI | HTTP API framework | MIT |
| SQLAlchemy / Alembic | Persistence and migrations | MIT |
| Pydantic / pydantic-settings | Schema and configuration validation | MIT |
| HTTPX | Optional provider HTTP client | BSD-3-Clause |
| Uvicorn | ASGI server | BSD-3-Clause |
| psycopg | Optional PostgreSQL driver | LGPL-3.0-only |
| python-multipart | Restricted upload parsing | Apache-2.0 |
| ReportLab | PDF generation | BSD-style ReportLab license |
| nginx | Static frontend and same-origin reverse proxy | BSD-2-Clause |
| PostgreSQL | Optional database container | PostgreSQL License |
| WenQuanYi Zen Hei | Chinese glyph fallback in the backend image | GPL-2.0 with the upstream font embedding exception; not copied into this repository |

Build and test dependencies, including Vite, TypeScript, Vitest, Playwright, ESLint and Testing Library, are development tooling and are not loaded by the browser at runtime. Exact dependency versions and transitive packages are recorded in `package-lock.json`, `frontend/package-lock.json`, and `backend/pyproject.toml`. Container base-image notices remain available in their respective images.

The repository does not redistribute real bank SDKs, proprietary model weights, commercial product catalogs, or third-party customer data. Product, customer, policy-cache and bank-adapter records used by the Demo are synthetic or controlled local fixtures.
