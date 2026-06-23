"""Start the backend server for local development using subprocess."""
import subprocess, sys, os, time

env = os.environ.copy()
env["DATABASE_URL"] = "postgresql://whatsapp_user:secure_password@localhost:5432/whatsapp_bot"
env["REDIS_URL"] = "redis://localhost:6379/0"
env["QUEUE_REDIS_URL"] = "redis://localhost:6379/1"

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"],
    cwd="e:\\codex\\WhatsApp",
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

print(f"Server started, PID={proc.pid}", flush=True)

# Keep running until stdin closes (or process dies)
try:
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        print(line.decode("utf-8", errors="replace").rstrip(), flush=True)
except KeyboardInterrupt:
    pass
finally:
    proc.terminate()
    proc.wait(timeout=5)
    print("Server stopped", flush=True)
