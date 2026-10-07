import requests

# Login
r = requests.post("http://localhost:8001/api/auth/login",
                  json={"email": "demo@example.com", "password": "demo"})
print("Login:", r.status_code)
token = r.json()["token"]

# Get papers
r = requests.get("http://localhost:8001/api/papers",
                 headers={"Authorization": f"Bearer {token}"})
print("Papers:", r.status_code)
papers = r.json()
print("Count:", len(papers))
for p in papers:
    print(" -", p["id"], p["filename"], p["status"], "| file_url:", p.get("file_url", "N/A")[:50])

# Test PDF access
if papers:
    paper_id = papers[0]["id"]
    r = requests.get(f"http://localhost:8001/api/papers/{paper_id}",
                     headers={"Authorization": f"Bearer {token}"})
    print("\nPaper detail:", r.status_code)
    detail = r.json()
    print(" file_url:", detail.get("file_url"))
