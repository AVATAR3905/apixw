#!/usr/bin/env python3
"""Unified Startup Runner for India Airfare Price Observatory.

Launches both the FastAPI REST API backend (Port 8000) and Next.js Dashboard
(Port 3000) concurrently, with live process health checks and graceful shutdown.
"""

import os
import subprocess
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "apps", "dashboard")


def print_banner():
    print("\n" + "=" * 80)
    print("      INDIA AIRFARE PRICE OBSERVATORY — UNIFIED PLATFORM LAUNCHER      ")
    print("      Official High-Frequency Aviation Price Index for MoSPI / NSO     ")
    print("=" * 80)
    print(" [1] FastAPI Backend:       http://localhost:8000")
    print("     - OpenAPI Specs:       http://localhost:8000/docs")
    print("     - Redoc Documentation: http://localhost:8000/redoc")
    print("     - Background Cron:     Active (Lifespan Managed @ 18:00 IST)")
    print(" [2] Next.js Dashboard:     http://localhost:3000")
    print("     - Live Data Mode:      100% Dynamic Direct Database Queries")
    print("     - Active Corridors:    10 DGCA-Weighted Routes")
    print("=" * 80)
    print(" Press Ctrl+C at any time to gracefully terminate both services.\n")


def main():
    print_banner()

    processes = []
    try:
        # 1. Start FastAPI Backend
        print("[*] Launching FastAPI Backend on http://localhost:8000 ...")
        api_cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
        api_proc = subprocess.Popen(
            api_cmd,
            cwd=PROJECT_ROOT,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        processes.append(("FastAPI Backend", api_proc))

        # Give API a moment to spin up and bind port
        time.sleep(2)

        # 2. Start Next.js Dashboard
        print("[*] Launching Next.js Dashboard on http://localhost:3000 ...")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        dash_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=DASHBOARD_DIR,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        processes.append(("Next.js Dashboard", dash_proc))

        print("\n[+] Both services are online and operating live.")
        print("[+] Access Dashboard: http://localhost:3000\n")

        # Monitor processes
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n[!] Process {name} exited with code {ret}. Terminating platform...")
                    return
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[*] Shutdown signal received (Ctrl+C). Terminating all services...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"[*] Stopping {name} (PID: {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[+] All services cleanly terminated.")


if __name__ == "__main__":
    main()
