import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

FAKE = str(Path(__file__).parent / "fake_repl.py")
ROOT = Path(__file__).resolve().parent.parent


def _health(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
        return json.loads(r.read())


def _children(ppid):
    """PIDs hijos leyendo /proc (la imagen de Docker puede no traer pgrep)."""
    out = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                stat = open(f"/proc/{d}/stat").read()
                if int(stat.rsplit(")", 1)[1].split()[1]) == ppid:
                    out.append(int(d))
            except OSError:
                pass
    return out


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_sigterm_cierra_servidor_y_repl_sin_dejar_huerfanos(tmp_path):
    port = _free_port()
    pidfile = tmp_path / "srv.pid"
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.verify_server", "--project", str(tmp_path), "--port", str(port),
         "--pidfile", str(pidfile),
         "--repl-cmd", json.dumps([sys.executable, FAKE])],
        cwd=ROOT, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            try:
                if _health(port)["status"] == "ready":
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("el servidor no llegó a ready")
        children = _children(proc.pid)
        assert children, "debería haber un REPL hijo"
        assert pidfile.read_text() == str(proc.pid)
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
        time.sleep(0.3)
        assert not any(_alive(c) for c in children), "quedó un REPL huérfano"
        assert not pidfile.exists(), "debería borrar su pidfile al salir"
    finally:
        if proc.poll() is None:
            proc.kill()


def test_segundo_servidor_en_el_mismo_puerto_falla_rapido(tmp_path):
    port = _free_port()
    args = [sys.executable, "-m", "src.verify_server", "--project", str(tmp_path), "--port", str(port),
            "--pidfile", str(tmp_path / "srv.pid"),
            "--repl-cmd", json.dumps([sys.executable, FAKE])]
    first = subprocess.Popen(args, cwd=ROOT, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                _health(port)
                break
            except OSError:
                time.sleep(0.1)
        second = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=15)
        assert second.returncode != 0 and "Address already in use" in second.stderr
    finally:
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=15)
