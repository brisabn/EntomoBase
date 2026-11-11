import math
import threading
import time


# conta falhas por chave dentro de uma janela de tempo e diz quando a chave está bloqueada
# o contador fica na memória do processo: reinicia junto com a API e não é compartilhado entre processos
class LimiteTentativas:
    def __init__(self, maximo: int, janela_segundos: int, relogio=time.monotonic):
        self.maximo = maximo
        self.janela = janela_segundos
        self._relogio = relogio
        self._falhas: dict = {}
        self._trava = threading.Lock()

    def _recentes(self, chave, agora: float) -> list:
        recentes = [t for t in self._falhas.get(chave, []) if agora - t < self.janela]
        if recentes:
            self._falhas[chave] = recentes
        else:
            self._falhas.pop(chave, None)
        return recentes

    # segundos até a chave poder tentar de novo; 0 se não está bloqueada
    def segundos_restantes(self, chave) -> int:
        with self._trava:
            agora = self._relogio()
            recentes = self._recentes(chave, agora)
            if len(recentes) < self.maximo:
                return 0
            return max(1, math.ceil(recentes[0] + self.janela - agora))

    def registrar_falha(self, chave) -> None:
        with self._trava:
            agora = self._relogio()
            self._recentes(chave, agora)
            self._falhas.setdefault(chave, []).append(agora)
            # evita que o dicionário cresça sem limite com chaves antigas
            if len(self._falhas) > 10000:
                for outra in list(self._falhas):
                    self._recentes(outra, agora)

    def zerar(self, chave) -> None:
        with self._trava:
            self._falhas.pop(chave, None)
