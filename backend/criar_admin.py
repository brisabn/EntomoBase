# cria um usuário ou troca a senha de um existente
#
# uso (dentro de backend, com o ambiente virtual ativo):
#     python criar_admin.py email@exemplo.br
#
# a senha é pedida no terminal e não aparece na tela
import getpass
import sys

import models
from database import SessionLocal, engine
from seguranca import TAMANHO_MINIMO_SENHA, gerar_hash


def principal() -> int:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Uso: python criar_admin.py email@exemplo.br")
        return 1
    email = sys.argv[1].strip().lower()

    senha = getpass.getpass("Senha: ")
    if len(senha) < TAMANHO_MINIMO_SENHA:
        print(f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")
        return 1
    if getpass.getpass("Repita a senha: ") != senha:
        print("As senhas não conferem.")
        return 1

    # só garante que a tabela de usuários existe; não precisa da SECRET_KEY nem da API
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
        if usuario:
            usuario.senha = gerar_hash(senha)
            print(f"Senha de {email} atualizada.")
        else:
            db.add(models.Usuario(email=email, senha=gerar_hash(senha)))
            print(f"Usuário {email} criado.")
        db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(principal())
