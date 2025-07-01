from cryptography.fernet import Fernet


# Пример генерации ключа для Fernet в терминале
# from encryption.crypto import generate_key
# print(generate_key())  скопируй и вставь в .env
def generate_key() -> str:
    """Генерирует новый Fernet-ключ"""
    return Fernet.generate_key().decode()