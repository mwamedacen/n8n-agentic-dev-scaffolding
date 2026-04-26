"""Test the hello_world cloud function locally."""
import requests

BASE_URL = "http://localhost:8000"

def test_hello_world():
    response = requests.post(f"{BASE_URL}/hello_world", json={"name": "Bootstrap"})
    assert response.status_code == 200
    data = response.json()
    assert "greeting" in data
    assert data["greeting"] == "Hello, Bootstrap!"
    print(f"PASS: {data}")

def test_hello_world_default():
    response = requests.post(f"{BASE_URL}/hello_world", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["greeting"] == "Hello, World!"
    print(f"PASS: {data}")

if __name__ == "__main__":
    test_hello_world()
    test_hello_world_default()
    print("\nAll tests passed!")
