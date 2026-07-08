"""End-to-end smoke test for the licensing backend (no network, TestClient)."""
import os
import tempfile

os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_TOKEN"] = "test-admin"

from fastapi.testclient import TestClient  # noqa: E402

from backend.database import init_db  # noqa: E402
from backend.main import app  # noqa: E402

init_db()
c = TestClient(app)

# health
r = c.get("/api/health")
assert r.status_code == 200, r.text
print("health:", r.json())

# trial creation
r = c.post("/api/licenses/trial", json={"name": "Ada", "email": "ada@x.com"})
assert r.status_code == 200, r.text
tok = r.json()["token"]
assert tok.startswith("SG-"), tok
print("trial token:", tok[:24], "...  expires", r.json()["expires_at"])

# duplicate trial blocked
r = c.post("/api/licenses/trial", json={"name": "Ada", "email": "ada@x.com"})
assert r.status_code == 409, r.text
print("duplicate trial blocked ->", r.status_code)

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

# billing disabled -> 501
r = c.post("/api/billing/checkout", json={"email": "ada@x.com"})
assert r.status_code == 501, r.text
print("billing stub (no keys) ->", r.status_code)

# static + pages
assert c.get("/").status_code == 200
assert c.get("/admin").status_code == 200
assert c.get("/static/css/styles.css").status_code == 200
print("pages + static served ok")

print("\nALL SMOKE TESTS PASSED")
