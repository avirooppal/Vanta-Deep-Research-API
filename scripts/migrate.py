"""Run Alembic migrations to head. Called before starting the API in production."""
import subprocess
import sys

if __name__ == "__main__":
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print("Migrations complete.")
