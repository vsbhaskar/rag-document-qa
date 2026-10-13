import pytest


def test_signup_creates_account_with_lowercase_email(client):
    r = client.post("/auth/signup", json={"email": "Alice@Example.com", "password": "correct-horse-1"})
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com"
    assert "password" not in r.text


def test_duplicate_email_is_rejected(client):
    body = {"email": "alice@example.com", "password": "correct-horse-1"}
    assert client.post("/auth/signup", json=body).status_code == 201
    assert client.post("/auth/signup", json=body).status_code == 409


def test_duplicate_email_ignores_case(client):
    client.post("/auth/signup", json={"email": "alice@example.com", "password": "correct-horse-1"})
    r = client.post("/auth/signup", json={"email": "ALICE@example.com", "password": "correct-horse-1"})
    assert r.status_code == 409


def test_short_password_is_rejected(client):
    r = client.post("/auth/signup", json={"email": "alice@example.com", "password": "short"})
    assert r.status_code == 422


def test_invalid_email_is_rejected(client):
    r = client.post("/auth/signup", json={"email": "not-an-email", "password": "correct-horse-1"})
    assert r.status_code == 422


def test_login_returns_bearer_token(client):
    client.post("/auth/signup", json={"email": "alice@example.com", "password": "correct-horse-1"})
    r = client.post("/auth/login", data={"username": "alice@example.com", "password": "correct-horse-1"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_wrong_password_and_unknown_email_give_the_same_error(client):
    client.post("/auth/signup", json={"email": "alice@example.com", "password": "correct-horse-1"})
    wrong_pw = client.post("/auth/login", data={"username": "alice@example.com", "password": "wrong-password"})
    unknown = client.post("/auth/login", data={"username": "nobody@example.com", "password": "correct-horse-1"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


@pytest.mark.parametrize("method, path, kwargs", [
    ("get", "/auth/me", {}),
    ("get", "/documents", {}),
    ("post", "/ask", {"json": {"question": "hello"}}),
    ("post", "/upload", {"files": {"file": ("a.pdf", b"x", "application/pdf")}}),
])
def test_protected_endpoints_require_a_token(client, method, path, kwargs):
    assert getattr(client, method)(path, **kwargs).status_code == 401


def test_me_returns_the_logged_in_user(client, alice):
    r = client.get("/auth/me", headers=alice)
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


def test_garbage_token_is_rejected(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer nonsense"})
    assert r.status_code == 401