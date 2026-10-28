import asyncio
import sys
import os

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import httpx
from app.main import app

async def run_e2e_tests():
    print("=" * 60)
    print("  ROBU / ARMS PLATFORM — BACKEND END-TO-END VERIFICATION")
    print("=" * 60)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        print("[PASS] [GET /health] ->", res.json())

        # 2. Login as Admin
        res = await client.post("/api/v1/auth/login", json={"email": "admin@arms.io", "password": "admin12345"})
        assert res.status_code == 200, f"Login failed: {res.text}"
        tokens = res.json()
        token = tokens["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        print("[PASS] [POST /api/v1/auth/login] -> Success (JWT issued)")

        # 3. Get /me
        res = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert res.status_code == 200, f"/me failed: {res.text}"
        user_info = res.json()
        print(f"[PASS] [GET /api/v1/auth/me] -> Authenticated as {user_info['full_name']} ({user_info['role']})")

        # 4. List Products
        res = await client.get("/api/v1/products", headers=auth_headers)
        assert res.status_code == 200, f"/products failed: {res.text}"
        products = res.json()
        print(f"[PASS] [GET /api/v1/products] -> {len(products)} products found")

        # 5. List Orders
        res = await client.get("/api/v1/orders", headers=auth_headers)
        assert res.status_code == 200, f"/orders failed: {res.text}"
        print(f"[PASS] [GET /api/v1/orders] -> {len(res.json())} orders found")

        # 6. List Shipments
        res = await client.get("/api/v1/shipments", headers=auth_headers)
        assert res.status_code == 200, f"/shipments failed: {res.text}"
        print(f"[PASS] [GET /api/v1/shipments] -> {len(res.json())} shipments found")

        # 7. List Inventory
        res = await client.get("/api/v1/shipments/inventory", headers=auth_headers)
        assert res.status_code == 200, f"/shipments/inventory failed: {res.text}"
        print(f"[PASS] [GET /api/v1/shipments/inventory] -> {len(res.json())} inventory records")

        # 8. List Robots
        res = await client.get("/api/v1/robots", headers=auth_headers)
        assert res.status_code == 200, f"/robots failed: {res.text}"
        robots = res.json()
        print(f"[PASS] [GET /api/v1/robots] -> {len(robots)} robots registered")

        # 9. Robot Comm Health
        res = await client.get("/api/v1/robot-communication/health", headers=auth_headers)
        assert res.status_code == 200, f"/robot-communication/health failed: {res.text}"
        print("[PASS] [GET /api/v1/robot-communication/health] ->", res.json().get("status"))

        # 10. Slotting Engine Optimize
        res = await client.post("/api/v1/slotting/optimize", headers=auth_headers)
        assert res.status_code == 200, f"/slotting/optimize failed: {res.text}"
        print(f"[PASS] [POST /api/v1/slotting/optimize] -> {res.json()['recommendations_generated']} recommendations generated")

        # 11. Slotting Recommendations
        res = await client.get("/api/v1/slotting/recommendations", headers=auth_headers)
        assert res.status_code == 200, f"/slotting/recommendations failed: {res.text}"
        print(f"[PASS] [GET /api/v1/slotting/recommendations] -> {len(res.json())} active slot recommendations")

        # 12. Slotting History
        res = await client.get("/api/v1/slotting/history", headers=auth_headers)
        assert res.status_code == 200, f"/slotting/history failed: {res.text}"
        print(f"[PASS] [GET /api/v1/slotting/history] -> {len(res.json())} optimizer runs recorded")

        # 13. Stock Movements
        res = await client.get("/api/v1/stock-movements", headers=auth_headers)
        assert res.status_code == 200, f"/stock-movements failed: {res.text}"
        print(f"[PASS] [GET /api/v1/stock-movements] -> {len(res.json())} movement ledger records")

        # 14. Admin Users
        res = await client.get("/api/v1/admin/users", headers=auth_headers)
        assert res.status_code == 200, f"/admin/users failed: {res.text}"
        users = res.json()
        print(f"[PASS] [GET /api/v1/admin/users] -> {len(users)} organization users listed")

        # 15. Admin Stats
        res = await client.get("/api/v1/admin/stats", headers=auth_headers)
        assert res.status_code == 200, f"/admin/stats failed: {res.text}"
        print("[PASS] [GET /api/v1/admin/stats] ->", res.json())

        # 16. Admin Settings
        res = await client.get("/api/v1/admin/settings", headers=auth_headers)
        assert res.status_code == 200, f"/admin/settings failed: {res.text}"
        print("[PASS] [GET /api/v1/admin/settings] ->", res.json()["database_provider"])

    print("\n" + "=" * 60)
    print("  ALL 16 CRITICAL API ENDPOINTS PASSED VERIFICATION!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
