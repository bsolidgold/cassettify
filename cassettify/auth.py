from __future__ import annotations
import datetime
import ipaddress
import os
import ssl
import stat
import tempfile
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from cassettify.config import Config, CONFIG_DIR

SCOPE = "playlist-read-private playlist-read-collaborative"
_CACHE_PATH = str(CONFIG_DIR / ".spotify_cache")
_REDIRECT_URI = "https://127.0.0.1:8888/callback"
_PORT = 8888

_DONE_HTML = b"""<!DOCTYPE html><html><body style="background:#111;color:#eee;
font-family:sans-serif;display:flex;align-items:center;justify-content:center;
height:100vh;margin:0"><div style="text-align:center">
<h1 style="color:#1DB954">&#127925; Cassettify</h1>
<p>Authorization complete. You can close this tab.</p>
</div></body></html>"""


def _make_self_signed_cert() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cf:
        cf.write(cert_pem)
        cert_file = cf.name
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as kf:
        kf.write(key_pem)
        key_file = kf.name
    return cert_file, key_file


def _catch_callback(auth_url: str) -> str:
    """Start a local HTTPS server, open the browser, return the auth code."""
    cert_file, key_file = _make_self_signed_cert()
    code_holder: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                code_holder.append(params["code"][0])
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(_DONE_HTML)
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *args):
            pass

    try:
        server = HTTPServer(("127.0.0.1", _PORT), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        server.timeout = 120

        webbrowser.open(auth_url)
        print(
            "\n[cassettify] Browser opened for Spotify login."
            "\n             If you see a certificate warning, click Advanced → Proceed."
        )

        while not code_holder:
            server.handle_request()

        server.server_close()
        return code_holder[0]
    finally:
        os.unlink(cert_file)
        os.unlink(key_file)


class _LocalHTTPSAuth(SpotifyOAuth):
    def get_auth_response(self, open_browser=None):
        return _catch_callback(self.get_authorize_url())


def get_client(config: Config) -> spotipy.Spotify:
    auth_manager = _LocalHTTPSAuth(
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri=_REDIRECT_URI,
        scope=SCOPE,
        cache_path=_CACHE_PATH,
        open_browser=True,
    )
    client = spotipy.Spotify(auth_manager=auth_manager)
    _secure_cache_file()
    return client


def _secure_cache_file() -> None:
    from pathlib import Path
    cache = Path(_CACHE_PATH)
    if cache.exists():
        cache.chmod(stat.S_IRUSR | stat.S_IWUSR)
