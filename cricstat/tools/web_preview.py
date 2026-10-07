"""Local preview of the cricstat pages before anything goes public (P0.4).

    python3 cricstat/tools/web_preview.py            # http://127.0.0.1:8090/cricket/

Mirrors what Nginx will do, without touching the live site:
  /cricket/api/...            → the running cricstat-api on 127.0.0.1:8040 (prefix stripped)
  /cricket/players/<slug>/    → the API's /pages/players/<slug>/ (server-rendered head, P0.6), or the
                                plain shell if the API is down (same for countries); run a dev API
                                on the branch with CRICSTAT_WEB_DIR=cricstat/tools/staging/web and
                                point CRICSTAT_API at it
  /cricket/sitemap.xml        → the API's /pages/sitemap.xml
  /cricket/photos/<hash>.jpg  → CRICSTAT_PHOTO_DIR (default cricstat/data/photos)
  /cricket/...                → cricstat/tools/staging/web/... (else cricstat/web/...)
  /, /privacy/, /sitemap.xml  → the STAGED copies in cricstat/tools/staging/ (not the live files)
  /admin-preview/cricket/     → a static snapshot of /admin/cricket rendered from local templates
  /feedback/...               → 204 (the widget's endpoints are not needed for a preview)
  anything else               → website/ (vendor scripts, og image, …)
Binds to 127.0.0.1 only: open it from your laptop through VS Code's port forwarding (Ports panel).
"""
import http.server
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGING = os.path.join(ROOT, "cricstat", "tools", "staging")
# cricstat/web is bind-mounted LIVE into nginx, so work in review is generated into staging/web
# (gen_pages.py default); the preview serves that copy when it exists.
WEB = os.path.join(STAGING, "web") if os.path.isdir(os.path.join(STAGING, "web")) else os.path.join(ROOT, "cricstat", "web")
SITE = os.path.join(ROOT, "website")
API = os.environ.get("CRICSTAT_API", "http://127.0.0.1:8040")
STAGED = {"/": "homepage.html", "/index.html": "homepage.html", "/privacy/": "privacy.html",
          "/sitemap.xml": "sitemap.xml", "/robots.txt": "robots.txt",
          "/admin-preview/cricket/": "admin-cricket.html"}   # static snapshot, not the live admin
PHOTOS = os.environ.get("CRICSTAT_PHOTO_DIR", os.path.join(ROOT, "cricstat", "data", "photos"))
PHOTO = re.compile(r"^/cricket/photos/([0-9a-f]{16}\.(?:jpg|png|webp))$")
DYNAMIC = re.compile(r"^/cricket/(players|countries)/[a-z0-9-]+/$")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/cricket/api/"):
            return self.proxy(self.path[len("/cricket/api"):])
        if path.startswith("/feedback/"):
            self.send_response(204)
            self.end_headers()
            return None
        if path == "/cricket":
            return self.redirect("/cricket/")
        if path in STAGED:
            return self.file(os.path.join(STAGING, STAGED[path]))
        m = DYNAMIC.match(path)
        if m:                                   # like Nginx since P0.6: the API renders the head
            return self.page(path[len("/cricket"):], os.path.join(WEB, m.group(1), "index.html"))
        if path == "/cricket/sitemap.xml":
            return self.page("/sitemap.xml", "")
        m = PHOTO.match(path)
        if m:                                   # player photos (P0.5), like Nginx's regex location
            return self.file(os.path.join(PHOTOS, m.group(1)))
        if path.startswith("/cricket/"):
            return self.file(self.safe(WEB, path[len("/cricket/"):]))
        return self.file(self.safe(SITE, path.lstrip("/")))

    def safe(self, base, rel):
        full = os.path.realpath(os.path.join(base, rel))
        if not full.startswith(os.path.realpath(base)):
            return ""
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        return full

    def file(self, full):
        if not full or not os.path.isfile(full):
            self.send_error(404)
            return
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(full)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def proxy(self, rest):
        try:
            with urllib.request.urlopen(API + rest, timeout=30) as r:
                status, body, ctype = r.status, r.read(), r.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            status, body, ctype = e.code, e.read(), e.headers.get("Content-Type")
        except OSError as e:
            status, body, ctype = 502, str(e).encode(), "text/plain"
        self.send_response(status)
        self.send_header("Content-Type", ctype or "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def page(self, rest, shell):
        """/pages<rest> from the API, passing 301s and 404s through; the plain shell if the API
        is down (Nginx's error_page fallback)."""
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(API + "/pages" + rest, timeout=30) as r:
                status, body, headers = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            status, body, headers = e.code, e.read(), e.headers
        except OSError:
            status, body, headers = 502, b"", {}
        if status in (502, 503, 504):
            return self.file(shell)
        if status in (301, 302):
            return self.redirect(headers.get("Location"))
        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type") or "text/html")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, to):
        self.send_response(301)
        self.send_header("Location", to)
        self.end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("preview: " + fmt % args + "\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    print("cricstat preview on http://127.0.0.1:%d/cricket/ (Ctrl-C to stop)" % port, flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
