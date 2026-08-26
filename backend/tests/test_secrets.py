import pytest
from cryptography.fernet import Fernet

from devstacks_domain import FernetTokenCipher, TokenCipherError


def test_fernet_token_cipher_encrypts_and_decrypts_connector_tokens():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))

    ciphertext = cipher.encrypt("github-access-token")

    assert ciphertext != "github-access-token"
    assert cipher.decrypt(ciphertext) == "github-access-token"


def test_fernet_token_cipher_rejects_invalid_key_and_tampered_ciphertext():
    with pytest.raises(TokenCipherError, match="key"):
        FernetTokenCipher("invalid-key")

    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    with pytest.raises(TokenCipherError, match="ciphertext"):
        cipher.decrypt("tampered-token")