from cryptography.fernet import Fernet
import os


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


# Пример генерации ключа для Fernet в терминале
# from encryption.crypto import generate_key
# print(generate_key())  скопируй и вставь в .env
def generate_key() -> str:
    """Генерирует новый Fernet-ключ"""
    return Fernet.generate_key().decode()
