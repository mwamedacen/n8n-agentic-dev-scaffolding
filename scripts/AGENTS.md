# Scripts

## Test Scripts

### test_hello_world.py

Tests the `hello_world` cloud function running locally. Start the cloud function service first, then run the test.

```bash
# Terminal 1: Start the service
cd cloud_functions && python app.py

# Terminal 2: Run tests
python3 scripts/test_hello_world.py
```

Tests:
- `test_hello_world()` -- Sends `{"name": "Bootstrap"}`, expects `{"greeting": "Hello, Bootstrap!"}`
- `test_hello_world_default()` -- Sends `{}`, expects `{"greeting": "Hello, World!"}`

## Prompt Engineering

The `prompt_engineering/` subdirectory provides a DSPy-based framework for evaluating and optimizing prompts stored in `common/prompts/`.

### Key Files

| File | Purpose |
|------|---------|
| `config.py` | LM provider configuration (OpenAI, OpenRouter, Anthropic) |
| `example_signature.py` | Define DSPy signatures matching `common/prompts/` schemas |
| `requirements.txt` | Dependencies: dspy, litellm, requests, python-dotenv |

### Usage

```bash
cd scripts/prompt_engineering
pip install -r requirements.txt

# Define and test a signature
python3 example_signature.py

# (Add your own evaluation and optimization scripts)
```

### Workflow

1. Define a `dspy.Signature` class matching your JSON schema fields
2. Create a `dspy.Module` wrapping the signature with `dspy.ChainOfThought`
3. Build evaluation datasets with expected inputs and outputs
4. Run DSPy optimizers (MIPROv2, BootstrapFewShot) to find better prompts
5. Export optimized prompts back to `common/prompts/` files

## How to Add New Test Scripts

1. Create `scripts/test_my_function.py`
2. Import `requests` and target `http://localhost:8000`
3. Write test functions with assertions
4. Add a `__main__` block that runs all tests
5. Document the script in this AGENTS.md
