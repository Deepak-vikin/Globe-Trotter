"""Quick test of the recommendations API endpoint."""
import httpx

email = "giridharan.ja25@gmail.com"
url = "http://localhost:8000/api/recommendations"

print(f"Testing recommendations for: {email}")
print("-" * 50)

try:
    r = httpx.get(url, params={"email": email}, timeout=120)
    print(f"Status: {r.status_code}")
    d = r.json()

    if r.status_code != 200:
        print(f"Error: {d}")
    else:
        print(f"Region: {d.get('region', 'N/A')}")
        print(f"Location: {d.get('location', 'N/A')}")
        spots = d.get("spots", [])
        print(f"Spots ({len(spots)}):")
        for i, s in enumerate(spots):
            print(f"  {i+1}. {s['name']} ({s['type']}) - img: {s.get('image', 'N/A')[:50]}...")
except Exception as e:
    print(f"Error: {e}")
