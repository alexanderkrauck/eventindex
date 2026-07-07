"""Create an API key and print it. NOTE: the moment the first active key
exists, the API stops being open (bootstrap rule, see api/app.py).

Run: uv run python scripts/create_api_key.py <name>
"""

import secrets
import sys

from eventindex import db


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "default"
    key = secrets.token_urlsafe(32)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO api_key (key, name) VALUES (%s, %s)", (key, name)
        )
        conn.commit()
    print(f"api key '{name}': {key}")
    print("use header X-API-Key or query param ?api_key= (for .ics subscriptions)")


if __name__ == "__main__":
    main()
