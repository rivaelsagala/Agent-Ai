"""Run PostgreSQL migrations with `python -m app.database.migrate`."""
from app.database.postgres import Database


def main() -> None:
    Database().migrate()
    print("Database migration completed.")


if __name__ == "__main__":
    main()
