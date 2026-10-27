from jose import JWTError, jwt

login_token = input("Enter LOGIN access token: ").strip()
refreshed_token = input("Enter REFRESHED access token: ").strip()

try:
    login_payload = jwt.get_unverified_claims(login_token)
    refreshed_payload = jwt.get_unverified_claims(refreshed_token)

    login_session = login_payload.get("sid")
    refreshed_session = refreshed_payload.get("sid")

    print("Login session present:", bool(login_session))
    print("Refreshed session present:", bool(refreshed_session))
    print(
        "Session ID preserved:",
        bool(login_session) and login_session == refreshed_session,
    )

except JWTError as error:
    print("JWT inspection failed:", error)