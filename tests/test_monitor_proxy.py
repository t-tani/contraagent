"""The monitor behind nginx under a base path, with the documentation's configuration
(`docs/examples/proxy/nginx.conf`): the page, the API and a live feed through `/monitor/`.
The browser's side of it is web/e2e/base-path.spec.ts."""

import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

pytest.importorskip("fastapi")

from contraagent._internal import docs

NGINX = shutil.which("nginx")
EXAMPLE = docs.DIR / "examples" / "proxy" / "nginx.conf"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, proc: subprocess.Popen, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"{proc.args[0]} ended: {proc.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except urllib.error.HTTPError as e:  # nginx answers 502 until the monitor listens
            e.close()
            time.sleep(0.1)
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.1)
    raise AssertionError(f"no answer from {url}")


def _get(url: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode()
    except urllib.error.HTTPError as e:
        with e:  # an error answer holds its body open, in a temporary file on Python 3.14
            return e.code, e.headers.get("Content-Type", ""), ""


@pytest.mark.skipif(NGINX is None, reason="no nginx on this host")
def test_the_documented_nginx_block_serves_the_monitor_under_its_base_path(demo_runs, tmp_path):
    monitor_port, site_port = _free_port(), _free_port()
    block = tmp_path / "monitor.conf"
    block.write_text(EXAMPLE.read_text(encoding="utf-8").replace("127.0.0.1:8787", f"127.0.0.1:{monitor_port}"), encoding="utf-8")
    temp = {name: tmp_path / name for name in ("client_body", "proxy", "fastcgi", "uwsgi", "scgi")}
    conf = tmp_path / "nginx.conf"
    conf.write_text(
        f"""pid {tmp_path / "nginx.pid"};
error_log {tmp_path / "error.log"};
events {{}}
http {{
    access_log off;
    {"".join(f"{name}_temp_path {path};" for name, path in temp.items())}
    server {{
        listen 127.0.0.1:{site_port};
        location / {{ return 404 "the rest of the site"; }}
        include {block};
    }}
}}
""",
        encoding="utf-8",
    )
    argv = ["monitor", "--runs-dir", str(demo_runs), "--port", str(monitor_port), "--base-path", "/monitor"]
    monitor = subprocess.Popen([sys.executable, "-m", "contraagent", *argv], stderr=subprocess.DEVNULL)
    nginx = subprocess.Popen([NGINX, "-p", str(tmp_path), "-c", str(conf), "-g", "daemon off;"], stderr=subprocess.DEVNULL)
    try:
        _wait(f"http://127.0.0.1:{monitor_port}/api/info", monitor)
        site = f"http://127.0.0.1:{site_port}"
        _wait(f"{site}/monitor/api/info", nginx)

        status, kind, page = _get(f"{site}/monitor/")
        assert status == 200 and kind.startswith("text/html")
        assert '<ca-monitor base-url="/monitor">' in page and 'src="/monitor/app.js"' in page
        assert _get(f"{site}/monitor/app.js")[:2] == (200, "text/javascript; charset=utf-8")
        assert _get(f"{site}/monitor/favicon.svg")[0] == 200
        status, _, runs = _get(f"{site}/monitor/api/runs")
        assert status == 200 and '"docs"' in runs
        assert _get(f"{site}/api/runs")[0] == 404  # the site's own /api is not the monitor's

        # The run feed through nginx: its first events arrive while the feed stays open.
        with urllib.request.urlopen(f"{site}/monitor/events?run=docs", timeout=10) as feed:
            assert feed.headers["Content-Type"].startswith("text/event-stream")
            head = b""
            while b"event: ready" not in head:
                line = feed.readline()
                assert line, "the feed ended"
                head += line
        assert b"event: journal" in head
    finally:
        for proc in (nginx, monitor):
            proc.terminate()
            proc.wait(timeout=10)


def test_the_example_block_turns_buffering_off_and_names_the_base_path():
    text = EXAMPLE.read_text(encoding="utf-8")
    for directive in ("location /monitor/", "proxy_pass http://127.0.0.1:8787/;", "proxy_buffering off;", "proxy_read_timeout"):
        assert directive in text, directive
    assert "--base-path /monitor" in text
