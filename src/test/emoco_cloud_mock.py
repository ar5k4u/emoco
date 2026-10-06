#!/usr/bin/env python3
"""Minimal Emoco Cloud mock server for app development and tests.

Implements the API contract the Emoco app relies on (see the Emoco Cloud design
document) with in-memory data and no dependencies beyond the standard library:

    POST /api/v1/accounts/users/authenticate
    GET  /api/v1/acoffees
    POST /api/v1/aroast
    GET  /api/v1/aroast/{roast_id}
    PUT  /api/v1/aroast/{roast_id}/profile
    POST /api/v1/aschedule/lock
    GET  /api/v1/notifications
    POST /api/v1/signup/ticket

Usage:
    python3 test/emoco_cloud_mock.py [--port 8765] [--record DIR]

Run the app against it with
    EMOCO_CLOUD_URL=http://127.0.0.1:8765 python3 artisan.py
and sign in with test@emoco.kr / emoco1234.

With --record DIR every request body received is written to DIR as a sample
file (roast records as JSON, profiles as .alog.gz) for the server developers.
"""

import argparse
import datetime
import gzip
import json
import os
import secrets
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

USER = {'email': 'test@emoco.kr', 'password': 'emoco1234', 'nickname': '테스트', 'user_id': 'u-0001', 'org_id': 'org-0001'}
TOKEN = 'mock-token-' + secrets.token_hex(8)

STOCK = {
    'coffees': [
        {'hr_id': 'C1001', 'label': '에티오피아 구지 워시드', 'origin': 'Ethiopia', 'varietals': ['Heirloom'],
         'processing': 'washed', 'crop_date': {'picked': [2025], 'landed': [2025, 6]},
         'moisture': 10.8, 'density': 720, 'screen_size': {'min': 15, 'max': 17},
         'default_unit': {'name': 'bag', 'size': 60},
         'stock': [{'location_hr_id': 'L1001', 'location_label': '본점 창고', 'amount': 42.5}]},
        {'hr_id': 'C1002', 'label': '콜롬비아 우일라', 'origin': 'Colombia', 'varietals': ['Caturra'],
         'processing': 'washed', 'crop_date': {'picked': [2025]},
         'moisture': 11.2, 'density': 740, 'screen_size': {'min': 16, 'max': 18},
         'default_unit': {'name': 'bag', 'size': 70},
         'stock': [{'location_hr_id': 'L1001', 'location_label': '본점 창고', 'amount': 18.0}]},
    ],
    'blends': [
        {'hr_id': 'B1001', 'label': '하우스 블렌드',
         'ingredients': [{'coffee': 'C1001', 'ratio': 0.6}, {'coffee': 'C1002', 'ratio': 0.4}]},
    ],
    'replBlends': [],
    'schedule': [],
}
ROASTS: dict[str, dict] = {}
PROFILES: dict[str, bytes] = {}
TICKETS: dict[str, float] = {}
SERVER_TIME = int(time.time())
ACCOUNT_STATE = {'ol': {'rlimit': -1, 'rused': 0}, 'pu': '2099-12-31T00:00:00Z', 'notifications': {'unqualified': 0, 'machines': []}}


class Handler(BaseHTTPRequestHandler):
    record_dir: str | None = None
    server_version = 'EmocoCloudMock/0.1'

    def log_message(self, fmt, *args):  # noqa: A003
        print(f'{datetime.datetime.now():%H:%M:%S} {self.command} {self.path} -> ' + (fmt % args), flush=True)

    # --- helpers
    def _json(self, code: int, payload: dict | None = None) -> None:
        if payload is None:
            self.send_response(204)
            self.end_headers()
            return
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b''
        if self.headers.get('Content-Encoding', '').lower() == 'gzip' and raw:
            raw = gzip.decompress(raw)
        return raw

    def _authorized(self) -> bool:
        return self.headers.get('Authorization') == f'Bearer {TOKEN}'

    def _record(self, name: str, data: bytes) -> None:
        if self.record_dir:
            os.makedirs(self.record_dir, exist_ok=True)
            with open(os.path.join(self.record_dir, name), 'wb') as f:
                f.write(data)

    # --- routes
    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path = url.path
        if path == '/api/v1/accounts/users/authenticate':
            data = json.loads(self._body() or b'{}')
            if data.get('email') != USER['email']:
                return self._json(404, {'success': False, 'result': '', 'error': f"User with email {data.get('email')} not found"})
            if data.get('password') != USER['password']:
                return self._json(401, {'success': False, 'result': '', 'error': 'Wrong password'})
            return self._json(200, {'success': True, 'result': {'user': {
                'token': TOKEN, 'nickname': USER['nickname'], 'language': 'ko', 'user_id': USER['user_id'],
                'account': {'_id': USER['org_id'], 'subscription': 'emoco', 'paidUntil': ACCOUNT_STATE['pu'],
                            'limit': ACCOUNT_STATE['ol']}}},
                'notifications': ACCOUNT_STATE['notifications']})
        if path == '/api/v1/signup/ticket':
            ua = self.headers.get('User-Agent', '')
            if not ua.startswith('Emoco/'):
                return self._json(403, {'success': False, 'result': '', 'error': 'Registration is only possible from the Emoco app'})
            data = json.loads(self._body() or b'{}')
            ticket = secrets.token_hex(32)
            TICKETS[ticket] = time.time() + 1800
            self._record('signup_ticket_request.json', json.dumps(data, ensure_ascii=False, indent=2).encode())
            return self._json(200, {'success': True, 'result': {
                'ticket': ticket,
                'register_url': f'http://{self.headers.get("Host")}/register?ticket={ticket}',
                'expires_at': datetime.datetime.fromtimestamp(TICKETS[ticket], datetime.timezone.utc).isoformat()}})
        if not self._authorized():
            return self._json(401, {'success': False, 'result': '', 'error': 'Unauthorized'})
        if path == '/api/v1/aroast':
            raw = self._body()
            data = json.loads(raw or b'{}')
            rid = data.get('roast_id')
            if not rid:
                return self._json(400, {'success': False, 'result': '', 'error': 'roast_id missing'})
            stored = ROASTS.get(rid, {})
            stored.update(data)
            stored.setdefault('modified_at', datetime.datetime.now(datetime.timezone.utc).isoformat())
            ROASTS[rid] = stored
            self._record(f'roast_{rid}.json', json.dumps(data, ensure_ascii=False, indent=2).encode())
            return self._json(200, {'success': True, 'result': {'roast_id': rid}, **ACCOUNT_STATE})
        if path == '/api/v1/aschedule/lock':
            self._body()
            return self._json(200, {'success': True, 'result': {}})
        return self._json(404, {'success': False, 'result': '', 'error': 'not found'})

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not self._authorized():
            return self._json(401, {'success': False, 'result': '', 'error': 'Unauthorized'})
        parts = path.strip('/').split('/')
        if len(parts) == 5 and parts[:3] == ['api', 'v1', 'aroast'] and parts[4] == 'profile':
            rid = parts[3]
            n = int(self.headers.get('Content-Length') or 0)
            raw_gz = self.rfile.read(n) if n else b''
            if n > 5 * 1024 * 1024:
                return self._json(413, {'success': False, 'result': '', 'error': 'profile too large'})
            if rid not in ROASTS:
                return self._json(404, {'success': False, 'result': '', 'error': 'roast record not found'})
            raw = gzip.decompress(raw_gz) if self.headers.get('Content-Encoding', '').lower() == 'gzip' else raw_gz
            PROFILES[rid] = raw
            self._record(f'profile_{rid}.alog.gz', raw_gz if raw_gz[:2] == b'\x1f\x8b' else gzip.compress(raw))
            return self._json(200, {'success': True, 'result': {'roast_id': rid, 'coffee': ROASTS[rid].get('coffee'), 'bytes': len(raw)}})
        return self._json(404, {'success': False, 'result': '', 'error': 'not found'})

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path = url.path
        qs = parse_qs(url.query)
        if path == '/register':
            ticket = (qs.get('ticket') or [''])[0]
            ok = ticket in TICKETS and TICKETS[ticket] > time.time()
            body = ('<h1>Emoco Cloud 가입</h1>' if ok else '<h1>Emoco 앱에서 가입을 눌러 주세요</h1>').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self._authorized():
            return self._json(401, {'success': False, 'result': '', 'error': 'Unauthorized'})
        if path == '/api/v1/acoffees':
            lsrt = qs.get('lsrt')
            if lsrt and int(float(lsrt[0])) >= SERVER_TIME:
                return self._json(204)
            return self._json(200, {'success': True, 'result': {'serverTime': SERVER_TIME, **STOCK}, **ACCOUNT_STATE})
        if path == '/api/v1/notifications':
            return self._json(200, {'success': True, 'result': []})
        parts = path.strip('/').split('/')
        if len(parts) == 4 and parts[:3] == ['api', 'v1', 'aroast']:
            rid = parts[3]
            if rid not in ROASTS:
                return self._json(404, {'success': False, 'result': '', 'error': 'roast not found'})
            if qs.get('modified_at'):
                return self._json(204)  # the client copy is as new as ours
            return self._json(200, {'success': True, 'result': ROASTS[rid]})
        return self._json(404, {'success': False, 'result': '', 'error': 'not found'})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--record', default=None, help='directory to store received request bodies as sample files')
    args = ap.parse_args()
    Handler.record_dir = args.record
    srv = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Emoco Cloud mock listening on http://127.0.0.1:{args.port}  (login {USER["email"]} / {USER["password"]})', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
