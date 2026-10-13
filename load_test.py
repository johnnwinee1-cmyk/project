"""Concurrent-user load test against a running server (python -m evaluation.load_test [base_url] [users] [requests])."""
import json
import re
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

from config import Config

QUESTIONS = ["Can one person register a company?", "How many days of annual leave am I entitled to?",
             "Do I have to pay money for police bail?", "What is the minimum wage in Nigeria now?",
             "Dem sack me for work without notice, I don work there two years."]


def user_session(base, n_req):
    s = requests.Session()
    token = re.search(r'name="csrf_token" value="([^"]+)"', s.get(f"{base}/register").text).group(1)
    page = s.post(f"{base}/register", data={"csrf_token": token, "email": f"load{uuid.uuid4().hex[:8]}@example.com",
                                             "password": "password123", "consent": "1"}, allow_redirects=True)
    s.headers["X-CSRFToken"] = re.search(r'name="csrf-token" content="([^"]+)"', page.text).group(1)
    out = []
    for i in range(n_req):
        t0 = time.perf_counter()
        r = s.post(f"{base}/api/chat", json={"message": QUESTIONS[i % len(QUESTIONS)]})
        out.append((r.status_code, (time.perf_counter() - t0) * 1000))
    return out


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    users = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    n_req = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as ex:
        results = [x for res in ex.map(lambda _: user_session(base, n_req), range(users)) for x in res]
    wall = time.perf_counter() - t0
    lat = sorted(ms for code, ms in results if code == 200)
    summary = {"users": users, "requests": len(results), "success": len(lat),
               "error_rate": round(1 - len(lat) / len(results), 4),
               "median_ms": round(statistics.median(lat), 1), "p95_ms": round(lat[int(0.95 * (len(lat) - 1))], 1),
               "max_ms": round(lat[-1], 1), "throughput_rps": round(len(results) / wall, 3), "wall_s": round(wall, 1)}
    (Config.BASE_DIR / "evaluation" / "results" / f"load_{users}u.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
