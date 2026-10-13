"""Public, credential-free smoke test for a deployed CampusRipple URL."""
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

base = os.environ.get('CAMPUSRIPPLE_BASE_URL', '').strip().rstrip('/')
if not base:
    raise SystemExit('Set CAMPUSRIPPLE_BASE_URL, e.g. https://your-staging-domain.example')
parsed = urlparse(base)
if parsed.scheme not in ('http', 'https') or not parsed.netloc:
    raise SystemExit('CAMPUSRIPPLE_BASE_URL must be an absolute HTTP(S) URL.')
if parsed.scheme != 'https':
    print('WARNING: URL is not HTTPS; do not use it for production credentials.', file=sys.stderr)

def fetch(path):
    request = urllib.request.Request(base + path, headers={'User-Agent': 'CampusRipple-SmokeTest/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.headers, response.read(1024 * 1024)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read(1024 * 1024)

status, headers, body = fetch('/healthz')
if status != 200 or b'"status": "ok"' not in body and b'"status":"ok"' not in body:
    raise SystemExit(f'/healthz failed: HTTP {status}; check app/database health.')
print('PASS /healthz')
status, headers, body = fetch('/')
if status != 200 or b'CampusRipple' not in body:
    raise SystemExit(f'Homepage smoke test failed: HTTP {status}.')
print('PASS homepage')
if 'X-Content-Type-Options' not in headers:
    raise SystemExit('Missing X-Content-Type-Options security header.')
if 'Content-Security-Policy' not in headers:
    raise SystemExit('Missing Content-Security-Policy security header.')
if parsed.scheme == 'https' and 'Strict-Transport-Security' not in headers:
    raise SystemExit('HTTPS deployment is missing the HSTS response header.')
print('PASS response security headers')
print('Public deployment smoke checks passed. Authenticated role/workflow checks still need staging test accounts.')
