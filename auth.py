import os


def auth(username: str, password: str) -> dict:
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "admin")

    if username != expected_username or password != expected_password:
        raise ValueError("Invalid username or password")

    return {
        "role": os.getenv("ADMIN_ROLE", "admin"),
        "info": {
            "username": username,
        },
    }
