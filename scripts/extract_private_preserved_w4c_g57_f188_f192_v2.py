#!/usr/bin/env python3
import importlib.util
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

BASE = pathlib.Path(__file__).with_name("extract_private_preserved_w4c_g57_f188_f192.py")
spec = importlib.util.spec_from_file_location("w4c_g57_base", BASE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

staged = {}

def stage_put(path, data, token, message):
    # Buffer only W4C-owned descendants/packages. No canonical or cross-worker writes.
    if not path.startswith(mod.OUTROOT + "/"):
        raise RuntimeError("W4C_OUTPUT_BOUNDARY_VIOLATION:" + path)
    staged[path] = bytes(data)
    return {"staged": True, "path": path}

mod.private_put_bytes = stage_put

exit_code = 0
try:
    mod.main()
except SystemExit as exc:
    try:
        exit_code = int(exc.code or 0)
    except Exception:
        exit_code = 1

# Even on per-F extraction failure, persist the exact package(s) and common blocker/handoff once.
token = (os.getenv("MN_PRIVATE_SINK_TOKEN") or "").strip()
if not token:
    raise SystemExit("PRIVATE_SINK_WRITE_CREDENTIAL_MISSING")
if not staged:
    raise SystemExit(exit_code or 1)

work = pathlib.Path(tempfile.mkdtemp(prefix="mn-w4c-g57-private-sink-"))
repo = work / "private"
remote = f"https://x-access-token:{token}@github.com/{mod.PRIVATE_REPO}.git"
env = os.environ.copy()
env["GIT_TERMINAL_PROMPT"] = "0"
try:
    subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--branch", mod.PRIVATE_BRANCH, remote, str(repo)], check=True, env=env)
    for rel, data in staged.items():
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Mobilidade Norte W4C"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "w4c@users.noreply.github.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "--", mod.OUTROOT], check=True)
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--", mod.OUTROOT], check=True, capture_output=True, text=True).stdout.strip()
    if status:
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "W4C G57: persist exact-byte ingress F188-F192"], check=True)
        pushed = False
        for attempt in range(3):
            p = subprocess.run(["git", "-C", str(repo), "push", "origin", f"HEAD:{mod.PRIVATE_BRANCH}"], env=env)
            if p.returncode == 0:
                pushed = True
                break
            # Concurrent private-branch writers are expected. Rebase only this W4C output commit and retry.
            subprocess.run(["git", "-C", str(repo), "fetch", "origin", mod.PRIVATE_BRANCH], check=True, env=env)
            subprocess.run(["git", "-C", str(repo), "rebase", f"origin/{mod.PRIVATE_BRANCH}"], check=True, env=env)
            time.sleep(1 + attempt)
        if not pushed:
            raise SystemExit("PRIVATE_SINK_ATOMIC_GIT_PUSH_FAILED_AFTER_REBASE_RETRIES")
finally:
    shutil.rmtree(work, ignore_errors=True)

raise SystemExit(exit_code)
