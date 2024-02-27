from fastapi.security import OAuth2PasswordBearer

get_oauth2_token = OAuth2PasswordBearer(tokenUrl="/security/tokens")
get_oauth2_token_or_none = OAuth2PasswordBearer(tokenUrl="/security/tokens", auto_error=False)
