# Cloud Functions

## Overview

FastAPI service hosting pure Python functions as HTTP endpoints. Deployed to Railway by default, adaptable to other platforms.

## Structure

```
cloud_functions/
  app.py              # FastAPI with dynamic endpoint registration
  registry.py         # EXPOSED_FUNCTIONS dict
  requirements.txt    # Python dependencies (fastapi, uvicorn)
  railway.toml        # Railway deployment config
  railpack.json       # Railpack build config
  functions/
    __init__.py
    hello_world.py                # Sample function
    validate_purchase_orders.py   # PO validation function
```

## Railway Setup

The service is pre-configured for Railway deployment:

- **`railway.toml`**: Configures the build (RAILPACK builder) and deploy (uvicorn start command, health check path, restart policy)
- **`railpack.json`**: Railpack-specific build config with the start command
- **Root Directory**: In Railway service settings, set the root directory to `cloud_functions/` (the monorepo subdirectory containing `app.py`)

### Deploying to Railway

1. Install CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Link project: `railway link`
4. Set **Root Directory** in Railway UI to the `cloud_functions/` subdirectory
5. Deploy: `railway up`

Railway automatically detects the Python project, installs dependencies from `requirements.txt`, and starts the service using the command in `railway.toml`.

## Local Development

```bash
cd cloud_functions
pip install -r requirements.txt
python app.py
```

The service runs at `http://localhost:8000`. Available endpoints:
- `GET /` -- Health check (basic)
- `GET /health` -- Detailed health check (lists registered functions)
- `GET /echo/{message}` -- Echo test
- `POST /hello_world` -- Sample function
- `POST /validate_purchase_orders` -- PO validation function

## Adding a New Function

1. Create `functions/my_function.py`:
   ```python
   def my_function(data: str, threshold: float = 0.5) -> dict:
       """Process data with the given threshold."""
       result = analyze(data, threshold)
       return {"output": result, "threshold_used": threshold}
   ```

2. Register it in `registry.py`:
   ```python
   from functions.my_function import my_function

   EXPOSED_FUNCTIONS = {
       "hello_world": hello_world,
       "validate_purchase_orders": validate_purchase_orders,
       "my_function": my_function,
   }
   ```

3. The endpoint is automatically available at `POST /my_function` (send JSON body with parameters)

No route definitions needed -- `app.py` dynamically generates endpoints from the registry using function signatures for query parameters.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Port for uvicorn to listen on | 8000 (local), set by Railway in production |
| `RAILWAY_ENVIRONMENT` | Set automatically by Railway | Not set locally |

## Adapting to other platforms

The pure-function pattern (JSON in, JSON out) ports to:

- **Supabase Edge Functions** — one Deno function per file under `supabase/functions/<name>/index.ts`. Port Python to TypeScript; deploy with `supabase functions deploy <name>`.
- **AWS Lambda** — wrap each function in a Lambda handler that JSON-decodes `event['body']` and JSON-encodes the result.
- **Google Cloud Functions** — wrap each function in an HTTP handler that reads `request.get_json()` and returns `jsonify(result)`.

In all three, deploy each function independently rather than as a single service.
