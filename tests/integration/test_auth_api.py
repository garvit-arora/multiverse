def test_signup_login_and_me(client):
    signup = client.post("/api/v1/auth/signup", json={
        "email": "dev@multiverse.example.com",
        "password": "correct-horse-battery-staple",
        "workspace_name": "Test Universe",
    })
    assert signup.status_code == 201, signup.text
    token = signup.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "dev@multiverse.example.com"
    assert me.json()["workspaces"][0]["name"] == "Test Universe"

    bad_login = client.post("/api/v1/auth/login", json={"email": "dev@multiverse.example.com", "password": "wrong"})
    assert bad_login.status_code == 401

    login = client.post("/api/v1/auth/login", json={
        "email": "dev@multiverse.example.com",
        "password": "correct-horse-battery-staple",
    })
    assert login.status_code == 200


def test_authenticated_application_registry(client):
    signup = client.post("/api/v1/auth/signup", json={
        "email": "registry@example.com",
        "password": "correct-horse-battery-staple",
        "workspace_name": "Registry Universe",
    })
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/v1/apps", headers=headers, json={
        "id": "demo-shop",
        "name": "Multiverse Shop",
        "base_url": "http://localhost:5173/demo/shop",
        "build_id": "shop-1.0.0",
    })
    assert created.status_code == 201, created.text
    listed = client.get("/api/v1/apps", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == "demo-shop"
    assert listed.json()["items"][0]["environments"] == []
