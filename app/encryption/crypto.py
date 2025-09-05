import os

from cryptography.fernet import Fernet


# Получаем ключ из переменной окружения
FERNET_KEY = os.environ.get("FERNET_KEY")


if not FERNET_KEY:
    raise ValueError("FERNET_KEY не найден. Установите его в переменных окружения")

fernet = Fernet(FERNET_KEY)


def encrypt(data: str) -> str:
    """Шифрует строку"""
    return fernet.encrypt(data.encode()).decode()


def decrypt(token: str) -> str:
    """Дешифрует строку"""
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        # Если не удалось расшифровать, значит данные уже в открытом виде
        return token
