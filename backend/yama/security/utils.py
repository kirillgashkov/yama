from uuid import UUID


# FIXME: Use Argon2id
def hash_password(password: str) -> str:
    return f"hash({password})"


# FIXME: Use Argon2id
def is_password_valid(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


# FIXME: Use JWT
def create_access_token(user_id: UUID) -> str:
    return f"access_token({user_id})"


# FIXME: Use JWT
def is_access_token_valid(access_token: str) -> bool:
    return access_token.startswith("access_token(") and access_token.endswith(")")
