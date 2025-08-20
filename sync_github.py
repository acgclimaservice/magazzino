#!/usr/bin/env python3
import subprocess
import sys
from datetime import datetime

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"$ {cmd}")
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(f"ERROR: {result.stderr.strip()}")
    return result.returncode == 0

def main():
    # Commit message con timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"Auto-sync {timestamp}"
    
    print("🔄 Sincronizzazione GitHub...")
    
    # Git operations
    if not run_cmd("git add ."):
        sys.exit(1)
    
    if not run_cmd(f'git commit -m "{message}"'):
        print("Nessun cambiamento da committare")
    
    if not run_cmd("git push origin main"):
        sys.exit(1)
    
    print("✅ Sincronizzazione completata!")

if __name__ == "__main__":
    main()
