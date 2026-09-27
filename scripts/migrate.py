"""Run Alembic migrations to head. Called before starting the API in production."""
import subprocess
import sys

if __name__ == "__main__":
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.stdout:
            print(result.stdout)
        if result.returncode != 0:
            print(f"Warning: Alembic migration non-zero exit:\n{result.stderr}", file=sys.stderr)
        else:
            print("Database migrations applied successfully.")
    except subprocess.TimeoutExpired:
        print("Warning: Database migration timed out after 20s. Proceeding with server start.", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Database migration encountered an error: {e}. Proceeding with server start.", file=sys.stderr)
    
    # Always exit 0 so container continues to start Uvicorn
    sys.exit(0)
