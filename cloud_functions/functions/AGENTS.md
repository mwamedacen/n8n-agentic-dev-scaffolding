# Cloud Function Implementation Guidelines

## Rules

1. **Self-contained**: NO imports from other project files. Each function file must be completely independent -- do not import from `registry.py`, `app.py`, or any other module outside `functions/`.

2. **Base64 for file data**: All file data (Excel, PDF, images) must be passed as base64-encoded strings. Functions cannot read from the filesystem.

3. **Standard library + requirements.txt only**: Only use Python standard library modules or packages listed in `cloud_functions/requirements.txt`. If you need a new dependency, add it to `requirements.txt` first.

4. **Pure functions**: No side effects, no file I/O, no database calls, no HTTP requests, no external state. Input goes in, output comes out. This makes functions testable, cacheable, and safe to retry.

5. **Type hints required**: All function parameters and return types must have type annotations. The `app.py` endpoint generator uses these to build query parameter schemas.

6. **JSON-serializable output**: Return dicts or lists that can be directly serialized to JSON. No custom objects, datetime instances, or bytes in the return value.

## Function Signature

```python
def my_function(param1: str, param2: int = 0) -> dict:
    """Description of what this function does."""
    # Process data using only the input parameters
    result = process(param1, param2)
    return {"result": result, "status": "ok"}
```

## Endpoint

Each function is auto-exposed as: `POST /{function_name}`

- **Request**: JSON body with function parameters as keys
- **Response**: The function's return value as JSON
- **Errors**: Exceptions are caught by `app.py` and returned as HTTP 500 with `{"detail": "Error message"}`

## Example

```python
# functions/validate_data.py

def validate_data(rows_json: str, schema_name: str = "default") -> dict:
    """Validate rows against a named schema."""
    import json
    rows = json.loads(rows_json)
    errors = []
    for i, row in enumerate(rows):
        if not row.get("id"):
            errors.append(f"Row {i}: missing id")
    return {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors
    }
```

After adding to `registry.py`, this is available at `POST /validate_data` (send JSON body with `rows_json` and `schema_name` parameters).
