import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def main():
    print("Launching Flash Talk Demo UI...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", os.path.join(ROOT, "frontend", "app.py")], cwd=ROOT)

if __name__ == "__main__":
    main()
