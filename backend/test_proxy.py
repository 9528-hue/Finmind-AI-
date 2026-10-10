"""Optional live smoke check for the local frontend API proxy.

Set FINMIND_TEST_EMAIL and FINMIND_TEST_PASSWORD for an existing test account
before running this script. It never relies on a built-in demo account.
"""

import os

import httpx


def main():
    email = os.environ.get("FINMIND_TEST_EMAIL")
    password = os.environ.get("FINMIND_TEST_PASSWORD")
    if not email or not password:
        raise SystemExit(
            "Set FINMIND_TEST_EMAIL and FINMIND_TEST_PASSWORD to run this smoke check."
        )

    client = httpx.Client(base_url="http://localhost:3000", follow_redirects=True)
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    if response.status_code != 200:
        raise SystemExit(f"Login failed: HTTP {response.status_code}: {response.text}")

    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    checks = {
        "ANALYTICS": client.get("/api/analytics/", headers=headers),
        "TRANSACTIONS": client.get("/api/transactions/", headers=headers),
        "ALERTS": client.get("/api/alerts/", headers=headers),
        "CSV REPORT": client.get("/api/reports/transactions/csv", headers=headers),
        "PDF REPORT": client.get("/api/reports/summary/pdf", headers=headers),
    }
    for name, result in checks.items():
        print(f"{name}: HTTP {result.status_code}")
        result.raise_for_status()


if __name__ == "__main__":
    main()
