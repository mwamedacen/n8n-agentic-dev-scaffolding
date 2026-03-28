def hello_world(name: str = "World") -> dict:
    """Sample cloud function."""
    return {"greeting": f"Hello, {name}!", "source": "cloud_function"}
