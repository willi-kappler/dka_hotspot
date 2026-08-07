import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from storage.users_db import create_user


def main() -> None:
    username = input("Username: ").strip()
    role = input("Role (user/scientist/admin): ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        raise SystemExit("Passwords do not match.")

    create_user(username, password, role)
    print(f"Created {role} user: {username}")


if __name__ == "__main__":
    main()
