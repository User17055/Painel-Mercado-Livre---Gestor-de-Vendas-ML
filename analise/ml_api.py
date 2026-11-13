# -*- coding: utf-8 -*-
"""ml_api.py: acesso a API do Mercado Livre, SO LEITURA. Somente biblioteca padrao. Nunca imprime token nem Secret.

  Coleta(conta).get(path, params)   UNICA funcao que le dados da API (so GET; repete em 429/5xx; erro fica em .erros)
  obter_token(conta)                access token valido; renova sozinho quando falta pouco para vencer

O que NAO faz: autorizar uma conta pela primeira vez (o token ja tem de existir na pasta de tokens).

Segredos (nunca em arquivo do projeto, chat ou log):
  - ML_CLIENT_ID e ML_CLIENT_SECRET: variaveis de ambiente (no Windows, tambem as do usuario).
  - tokens: <pasta pessoal de quem roda>/.ml-api/token_<CONTA>.json, ou a pasta da variavel ML_API_DIR (no Docker, /segredos).
    O refresh token e de USO UNICO: so UMA maquina renova. Se outra ferramenta da mesma maquina usa estes tokens, ela deve
    apontar para esta MESMA pasta (uma copia separada faria uma derrubar a outra). Formato do arquivo: conta, user_id,
    access_token, refresh_token, scope, expira_em, gravado_em (a renovacao mantem as chaves que ja existiam).

A unica escrita em rede e a renovacao do token (POST no endereco de login do ML, _post_token): nao altera nada na conta.
testes/test_regras_do_codigo.py confere que nenhum outro codigo faz POST/PUT/PATCH/DELETE.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.mercadolibre.com"
TOKEN_URL = API + "/oauth/token"
CONTAS = ("PD", "TPP")
MARGEM_RENOVACAO = 300  # renova se faltar menos de 5 min para vencer
PAUSA = 0.15            # segundos entre chamadas (bem abaixo dos limites)
TENTATIVAS = 6          # em limite de chamadas (429) ou erro do servidor: espera cada vez mais e repete (ate ~2 min no total)


class ErroAPI(RuntimeError):
    """Falta credencial/token ou o ML recusou a renovacao. A mensagem nunca leva token nem Secret."""


def pasta() -> Path:
    p = Path(os.environ.get("ML_API_DIR") or (Path.home() / ".ml-api"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _arq(conta: str) -> Path:
    if conta not in CONTAS:
        raise ErroAPI(f"conta invalida: use {' ou '.join(CONTAS)} (recebi {conta!r})")
    return pasta() / f"token_{conta}.json"


def _env_usuario(nome: str) -> str:
    """Variavel de ambiente do USUARIO no registro do Windows (terminal aberto antes de ela existir). Fora do Windows: vazio."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, nome)[0] or ""
    except (ImportError, OSError):
        return ""


def _cred() -> tuple[str, str]:
    cid = os.environ.get("ML_CLIENT_ID", "") or _env_usuario("ML_CLIENT_ID")
    sec = os.environ.get("ML_CLIENT_SECRET", "") or _env_usuario("ML_CLIENT_SECRET")
    if not cid or not sec:
        raise ErroAPI("faltam as variaveis de ambiente ML_CLIENT_ID e/ou ML_CLIENT_SECRET")
    return cid, sec


def _ler(conta: str) -> dict:
    f = _arq(conta)
    if not f.exists():
        raise ErroAPI(f"conta {conta} sem token em {pasta()} (autorizar a conta antes)")
    return json.loads(f.read_text(encoding="utf-8"))


def _gravar(caminho: Path, dados: dict) -> None:
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    os.replace(tmp, caminho)  # troca atomica: nunca fica meio gravado


def _post_token(corpo: dict) -> dict:
    """Renovacao do token: o UNICO POST do projeto, e so para o endereco de login (nao altera nada na conta)."""
    req = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(corpo).encode(), method="POST",
                                 headers={"accept": "application/json", "content-type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        det = e.read().decode(errors="replace")
        try:
            j = json.loads(det)
            det = f"{j.get('error')}: {j.get('error_description') or j.get('message')}"  # so codigo e texto, sem eco do corpo
        except ValueError:
            det = det[:200]
        raise ErroAPI(f"erro {e.code} do Mercado Livre ao renovar o token: {det}") from None


def renovar(conta: str) -> dict:
    ant = _ler(conta)
    if not ant.get("refresh_token"):
        raise ErroAPI(f"conta {conta} sem refresh token (autorizar a conta de novo)")
    cid, sec = _cred()
    resp = _post_token({"grant_type": "refresh_token", "client_id": cid, "client_secret": sec,
                        "refresh_token": ant["refresh_token"]})
    agora = int(time.time())
    dados = {**ant, "access_token": resp["access_token"],
             "refresh_token": resp.get("refresh_token") or ant["refresh_token"],   # o antigo morreu: grava o novo ja
             "scope": resp.get("scope") or ant.get("scope"),
             "expira_em": agora + int(resp.get("expires_in", 21600)), "gravado_em": agora}
    _gravar(_arq(conta), dados)
    return dados


def obter_token(conta: str) -> str:
    d = _ler(conta)
    if d["expira_em"] - time.time() < MARGEM_RENOVACAO:
        d = _ler(conta)  # rele: outra ferramenta da mesma maquina pode ter acabado de renovar
        if d["expira_em"] - time.time() < MARGEM_RENOVACAO:
            d = renovar(conta)
    return d["access_token"]


def id_vendedor(conta: str) -> int:
    """Id do vendedor gravado junto com o token na autorizacao (nao fica escrito no codigo)."""
    uid = _ler(conta).get("user_id")
    if not uid:
        raise ErroAPI(f"token da conta {conta} sem user_id")
    return int(uid)


class Coleta:
    """Uma rodada de leitura de uma conta: conta chamadas e guarda os erros (nunca o corpo da resposta)."""

    def __init__(self, conta: str):
        self.conta = conta
        self.uid = id_vendedor(conta)
        self.chamadas = 0
        self.erros: list[list] = []

    def get(self, path: str, params: dict | None = None, ref: str = "", headers: dict | None = None):
        """UNICA funcao que le a API, e so faz GET. Devolve o JSON ou None (erro registrado em self.erros)."""
        # safe="[],": a doc usa listas com virgula sem codificar
        url = API + path + ("?" + urllib.parse.urlencode(params, safe="[],", quote_via=urllib.parse.quote) if params else "")
        ultimo = [ref, path, "desistiu", "429/5xx repetido"]   # so a falha FINAL vira erro (tentativa que deu certo depois nao conta)
        for tentativa in range(TENTATIVAS):
            cab = {"Authorization": f"Bearer {obter_token(self.conta)}", "accept": "application/json", **(headers or {})}
            req = urllib.request.Request(url, method="GET", headers=cab)
            time.sleep(PAUSA)
            self.chamadas += 1
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                msg = ""
                try:
                    j = json.loads(e.read().decode(errors="replace"))
                    msg = f"{j.get('error', '')}: {j.get('message', '')}"[:200]
                except ValueError:
                    pass
                # passageiro: espera e repete. A cobranca devolve o limite de chamadas como 400 com "[429]" na mensagem.
                if e.code in (409, 429) or e.code >= 500 or (e.code == 400 and "[429]" in msg):
                    time.sleep(min(2 ** (tentativa + 1), 60))   # 2, 4, 8, 16, 32, 60 s
                    continue
                self.erros.append([ref, path, e.code, msg])
                return None
            except (urllib.error.URLError, TimeoutError, ValueError) as e:  # rede, JSON: espera e repete
                ultimo = [ref, path, "rede", type(e).__name__]
                time.sleep(2)
        self.erros.append(ultimo)
        return None
