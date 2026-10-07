import requests
import json

# Login
r = requests.post("http://localhost:8001/api/auth/login",
                  json={"email": "demo@example.com", "password": "demo"})
print("Login:", r.status_code)
token = r.json()["token"]

# Get papers
r = requests.get("http://localhost:8001/api/papers",
                 headers={"Authorization": f"Bearer {token}"})
papers = r.json()
print("Papers:", len(papers))

# Test Q&A with first ready paper
for p in papers:
    if p["status"] == "ready":
        paper_id = p["id"]
        break

print(f"\nTesting Q&A with paper: {paper_id}")

# Test search
r = requests.post(f"http://localhost:8001/api/papers/{paper_id}/chunks/search",
                  headers={"Authorization": f"Bearer {token}",
                           "Content-Type": "application/json"},
                  json={"query": "What is this paper about?", "top_k": 3})
print(f"Search status: {r.status_code}")
if r.ok:
    chunks = r.json()
    print(f"Found {len(chunks)} chunks")
else:
    print(f"Error: {r.text[:200]}")

# Test QA
session_id = "550e8400-e29b-41d4-a716-446655440000"
r = requests.post(f"http://localhost:8001/api/papers/{paper_id}/chunks/qa",
                  headers={"Authorization": f"Bearer {token}",
                           "X-Session-ID": session_id,
                           "Content-Type": "application/json"},
                  json={"question": "What is this paper about?"})
print(f"\nQA status: {r.status_code}")
if r.ok:
    result = r.json()
    print(f"Answer: {result.get('answer', '')[:200]}...")
    print(f"Citations: {len(result.get('citations', []))}")
else:
    print(f"Error: {r.text[:500]}")
