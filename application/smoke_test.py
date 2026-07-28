"""End-to-end smoke test for the licensing backend (no network, TestClient)."""
import os
import tempfile

os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_TOKEN"] = "test-admin"

from backend.database import init_db  # noqa: E402
from backend.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

init_db()
c = TestClient(app)

# health
r = c.get("/api/health")
assert r.status_code == 200, r.text
print("health:", r.json())

# free token creation
r = c.post("/api/licenses/free", json={"name": "Ada", "email": "ada@x.com"})
assert r.status_code == 200, r.text
body = r.json()
tok = body["token"]
assert tok.startswith("SG-"), tok
assert body["type"] == "community", body
assert body["expires_at"] is None, body          # community licenses never expire
print("free token:", tok[:24], "...  expires", body["expires_at"])

# asking again returns the same token (idempotent, so a lost token is recoverable)
r = c.post("/api/licenses/free", json={"name": "Ada", "email": "ada@x.com"})
assert r.status_code == 200, r.text
assert r.json()["token"] == tok, r.text
print("repeat request -> same token")

# validate valid token
r = c.post("/api/licenses/validate", json={"token": tok})
assert r.status_code == 200 and r.json()["valid"], r.text
print("validate ok ->", r.json()["type"], r.json()["email"])

# validate tampered token
r = c.post("/api/licenses/validate", json={"token": tok[:-3] + "xyz"})
assert r.json()["valid"] is False, r.text
print("tampered token rejected ->", r.json()["reason"])

# admin unauthorized
r = c.get("/api/admin/licenses")
assert r.status_code == 401, r.text
print("admin unauth ->", r.status_code)

# admin authorized
r = c.get("/api/admin/licenses", headers={"Authorization": "Bearer test-admin"})
assert r.status_code == 200, r.text
jti = r.json()["licenses"][0]["jti"]
print("admin list ->", r.json()["stats"])

# revoke + re-validate
r = c.post(f"/api/admin/licenses/{jti}/revoke", headers={"Authorization": "Bearer test-admin"})
assert r.status_code == 200, r.text
r = c.post("/api/licenses/validate", json={"token": tok})
assert r.json()["valid"] is False and r.json()["reason"] == "revoked", r.text
print("revoked token rejected ->", r.json()["reason"])

# revoked email cannot mint a fresh token
r = c.post("/api/licenses/free", json={"name": "Ada", "email": "ada@x.com"})
assert r.status_code == 403, r.text
print("revoked email blocked ->", r.status_code)

# billing endpoints are gone
assert c.post("/api/billing/checkout", json={"email": "ada@x.com"}).status_code == 404
print("billing routes removed -> 404")

# static + pages
assert c.get("/").status_code == 200
assert c.get("/admin").status_code == 200
assert c.get("/static/css/styles.css").status_code == 200
print("pages + static served ok")

print("\nALL SMOKE TESTS PASSED")
