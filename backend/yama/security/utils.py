# FIXME: Use Argon2id
def hash_password(password: str) -> str:
    return f"hash({password})"


# FIXME: Use Argon2id
def is_password_valid(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash
