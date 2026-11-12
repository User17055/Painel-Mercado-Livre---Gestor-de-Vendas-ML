# -*- coding: utf-8 -*-
"""Atualizador: controla o botao "Atualizar agora". Uma atualizacao por vez e intervalo minimo entre duas.

Por que: o refresh token do ML e de uso unico (duas renovacoes ao mesmo tempo derrubam o acesso) e a doc pede para nao repetir
chamadas em sequencia. A trava e um arquivo criado de forma atomica (O_EXCL); trava mais velha que `trava_max_min` e considerada
abandonada (processo que caiu) e e removida.
O que a atualizacao FAZ (ex.: coletar pedidos novos) e passado como funcao em executar(): este modulo nao chama a API.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from painel.nucleo import caminhos


class AtualizacaoRecusada(Exception):
    """Ja tem uma atualizacao rodando, ou a ultima foi ha menos que o intervalo minimo."""


class Atualizador:
    def __init__(self, intervalo_min: float, trava: Path = caminhos.TRAVA_ATUALIZACAO,
                 registro: Path = caminhos.REGISTRO_ATUALIZACAO, trava_max_min: float = 30):
        self.intervalo = timedelta(minutes=intervalo_min)
        self.trava, self.registro = Path(trava), Path(registro)
        self.trava_max = timedelta(minutes=trava_max_min)

    def ultima(self) -> dict | None:
        """{'inicio', 'fim', 'ok', 'resumo'} da ultima atualizacao, ou None."""
        try:
            return json.loads(self.registro.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def pode_atualizar(self, agora: datetime | None = None) -> tuple[bool, str]:
        agora = agora or datetime.now()
        if self.trava.exists():
            idade = agora - datetime.fromtimestamp(self.trava.stat().st_mtime)
            if idade < self.trava_max:
                return False, "já tem uma atualização em andamento"
        u = self.ultima()
        if u and u.get("ok") and u.get("fim"):
            falta = datetime.fromisoformat(u["fim"]) + self.intervalo - agora
            if falta > timedelta(0):
                return False, f"atualizado às {u['fim'][11:16]}; próxima liberada em {int(falta.total_seconds() // 60) + 1} min"
        return True, ""

    def _pegar_trava(self) -> None:
        if self.trava.exists() and datetime.now() - datetime.fromtimestamp(self.trava.stat().st_mtime) >= self.trava_max:
            self.trava.unlink(missing_ok=True)          # trava abandonada
        try:
            fd = os.open(self.trava, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise AtualizacaoRecusada("já tem uma atualização em andamento") from None
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)

    def executar(self, tarefa: Callable[[], dict]) -> dict:
        """Roda tarefa() (que devolve um resumo) sob a trava e registra inicio, fim e resultado. Recusa se nao pode."""
        ok, motivo = self.pode_atualizar()
        if not ok:
            raise AtualizacaoRecusada(motivo)
        self._pegar_trava()
        inicio, resumo, deu_certo = datetime.now(), {}, False
        try:
            resumo = tarefa() or {}
            deu_certo = True
            return resumo
        finally:
            reg = {"inicio": inicio.isoformat(timespec="seconds"), "fim": datetime.now().isoformat(timespec="seconds"),
                   "ok": deu_certo, "resumo": resumo}
            tmp = self.registro.with_suffix(".tmp")
            tmp.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.registro)
            self.trava.unlink(missing_ok=True)
