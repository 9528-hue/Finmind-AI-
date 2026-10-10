"""Optional live report smoke check for a locally running FastAPI backend.

Set FINMIND_TEST_EMAIL and FINMIND_TEST_PASSWORD for an existing test account
before running this script.
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

    client = httpx.Client(base_url="http://localhost:8000")
    response = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    if response.status_code != 200:
        raise SystemExit(f"Login failed: HTTP {response.status_code}: {response.text}")

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    csv_response = client.get("/reports/transactions/csv", headers=headers)
    csv_response.raise_for_status()
    print("CSV report:", csv_response.status_code, "bytes:", len(csv_response.content))

    pdf_response = client.get("/reports/summary/pdf", headers=headers, timeout=30)
    pdf_response.raise_for_status()
    if not pdf_response.content.startswith(b"%PDF"):
        raise SystemExit("PDF endpoint returned an invalid document.")
    print("PDF report:", pdf_response.status_code, "bytes:", len(pdf_response.content))


if __name__ == "__main__":
    main()
