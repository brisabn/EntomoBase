from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

PREFIXO_HASH = "$argon2"
TAMANHO_MINIMO_SENHA = 8

# hash de uma senha qualquer; serve para gastar o mesmo tempo quando o e-mail não existe
_HASH_FALSO = _hasher.hash("senha-que-ninguem-usa")


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def ja_e_hash(valor: str) -> bool:
    return (valor or "").startswith(PREFIXO_HASH)


def verificar_senha(senha: str, hash_guardado: str | None) -> bool:
    if not hash_guardado or not ja_e_hash(hash_guardado):
        # usuário inexistente: gasta o mesmo tempo de uma verificação real, para o tempo de resposta
        # não revelar se o e-mail existe, e recusa sempre
        try:
            _hasher.verify(_HASH_FALSO, senha)
        except (VerificationError, InvalidHashError):
            pass
        return False
    try:
        return _hasher.verify(hash_guardado, senha)
    except (VerificationError, InvalidHashError):
        return False


def precisa_novo_hash(hash_guardado: str) -> bool:
    return _hasher.check_needs_rehash(hash_guardado)
