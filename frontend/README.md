# Tax Tracker Frontend

React + TypeScript + Vite frontend for the Tax Tracker API.

## Tooling

- Package manager: `pnpm`
- Linting: `oxlint`
- Formatting: `oxfmt`
- Build tool: `Vite`

## Commands

```bash
pnpm install
pnpm dev
pnpm build
pnpm typecheck
pnpm lint
pnpm lint:fix
pnpm format
pnpm format:fix
```

## Environment

- `VITE_API_BASE_URL`: optional FastAPI server URL override
- Default behavior: same-origin requests with Vite proxy forwarding API routes to `http://127.0.0.1:8000`
