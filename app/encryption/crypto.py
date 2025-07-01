import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv


load_dotenv()


# Получаем ключ из переменной окружения или .env файла
FERNET_KEY = os.getenv("FERNET_KEY")


if not FERNET_KEY:
    raise ValueError("FERNET_KEY не найден. Установите его в .env")

fernet = Fernet(FERNET_KEY.encode())


def encrypt(data: str) -> str:
    """Шифрует строку"""
    return fernet.encrypt(data.encode()).decode()


def decrypt(token: str) -> str:
    """Дешифрует строку"""
    return fernet.decrypt(token.encode()).decode()
