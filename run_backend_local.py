"""
Local dev backend runner.
Overrides Docker-only hostnames (postgres -> localhost, redis -> localhost)
and starts uvicorn with explicit subprocess for reliability.
Usage: .\Scripts\python.exe run_backend_local.py
"""
import os, sys, subprocess, signal, time

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
PORT = 8012

env = os.environ.copy()
env["DATABASE_URL"] = "postgresql://whatsapp_user:secure_password@localhost:5432/whatsapp_bot"
env["REDIS_URL"] = "redis://localhost:6379/0"
env["QUEUE_REDIS_URL"] = "redis://localhost:6379/1"

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(PORT)],
    cwd=WORKSPACE,
    env=env,
)

print(f"Backend starting on port {PORT} (PID={proc.pid})", flush=True)

# Print stdout/stderr
while True:
    try:
        line = proc.stdout.readline()
        if line:
            print(line.decode("utf-8", errors="replace").rstrip(), flush=True)
    except (ValueError, AttributeError):
        pass
    ret = proc.poll()
    if ret is not None:
        print(f"Backend exited with code {ret}", flush=True)
        break
    time.sleep(0.5)
