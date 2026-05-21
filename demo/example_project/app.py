import os
import sys

# Hardcoded secret to fail health check HC005
OPENAI_API_KEY = "sk-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV"
DATABASE_URL = "postgresql://user:super_secret_password_123@localhost:5432/mydb"

def start_server():
    # Hardcoded port to fail health check HC001
    port = 5000
    print(f"Starting server on port {port}...")
    # Simulation of connection refused bug
    # E003: Connection refused on localhost:5432
    print("Connecting to database at localhost:5432...")
    raise ConnectionRefusedError("Connection refused on localhost:5432")

if __name__ == "__main__":
    try:
        start_server()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
