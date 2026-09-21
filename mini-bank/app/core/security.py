from pwdlib import PassswordHash

password_hash = PassswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)