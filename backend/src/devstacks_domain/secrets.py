from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


class TokenCipherError(ValueError):
    """Raised when connector token encryption configuration or ciphertext is invalid."""


@dataclass(frozen=True)
class FernetTokenCipher:
    key: str

    def __post_init__(self) -> None:
        try:
            Fernet(self.key.encode("ascii"))
        except (TypeError, UnicodeEncodeError, ValueError) as error:
            raise TokenCipherError("connector token encryption key is invalid") from error

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise TokenCipherError("connector token plaintext is required")
        return Fernet(self.key.encode("ascii")).encrypt(plaintext.encode("utf-8")).decode(
            "ascii"
        )

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            raise TokenCipherError("connector token ciphertext is required")
        try:
            return Fernet(self.key.encode("ascii")).decrypt(ciphertext.encode("ascii")).decode(
                "utf-8"
            )
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as error:
            raise TokenCipherError("connector token ciphertext is invalid") from error