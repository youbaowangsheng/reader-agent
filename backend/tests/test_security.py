from app.core.security import create_access_token, decode_access_token, validate_login_credentials


def test_token_round_trip():
    token = create_access_token("demo@example.com")
    payload = decode_access_token(token)
    assert payload["email"] == "demo@example.com"
    assert "sub" in payload
    assert payload["exp"] > payload["iat"]


def test_login_credential_validation():
    assert validate_login_credentials("demo@example.com", "demo") is True
    assert validate_login_credentials("demo@example.com", "wrong") is False
    assert validate_login_credentials("nobody@example.com", "demo") is False
