#!/usr/bin/env python3
"""zion.py - CLI para o Zion/Tasy 5.04 sem navegador.

Uso:
  python3 zion.py login                       # pede/grava credenciais e testa login + perfil
  python3 zion.py logout                      # apaga credenciais salvas
  python3 zion.py whoami                      # mostra só o usuário salvo
  python3 zion.py fila [--status N] [--exames] [--resumo]  # fila geral, sem atendimento
  python3 zion.py listar ATENDIMENTO          # linhas/status por fase
  python3 zion.py digitacao ATENDIMENTO [--dry-run] [--desde STATUS]
  python3 zion.py ler ATENDIMENTO              # valores salvos dos exames em Digitação
  python3 zion.py resultado AT --exame NA+=134.9 [--exame ...] [--dry-run] [--forcar]
  python3 zion.py gaso AT --na 134.9 --k 4.37 --ica 1.08 --cl 105.7 [--glu --lac --ph ...] [--dry-run] [--forcar]
  (nunca libera; após salvar relê via build e compara)
  Sorologias / exames externos NÃO são digitados (vão p/ outro lab).
  Testes rápidos (TRTOXO, HIV, TRS, …) continuam normais. sorologia ≠ teste rápido.

Credenciais: na 1ª vez o CLI pede usuário e senha (getpass) e grava em
~/.config/zion-cli/credentials.json (Windows: %APPDATA%\\zion-cli\\), permissão 600.
Precedência: flags/env (ZION_USER, ZION_PASSWORD) > arquivo salvo > prompt.
Sessão: session.json no mesmo diretório de config; renova/reloga sozinho.
Senha nunca é impressa.
"""
import argparse, copy, difflib, getpass, json, os, re, sys, time, datetime as dt
import requests

DEFAULT_URL = "https://sbsj.zion-srv.com"
DEFAULT_PROFILE = "HMMCC - Laboratório - Biomédico"
DEFAULT_SETOR = "HMMCC - Serv. Laboratório Análises Clínicas"
SCOPE = "WTASY"


def _load_env_files():
    """Carrega .env.example e .env com setdefault (env do processo ganha)."""
    here = os.path.dirname(os.path.abspath(__file__))
    vals = {}
    for name in (".env.example", ".env"):
        fp = os.path.join(here, name)
        if not os.path.exists(fp):
            continue
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if v:
                vals[k.strip()] = v
    for k, v in vals.items():
        os.environ.setdefault(k, v)


_load_env_files()


def config_dir():
    """Diretório de config por usuário (fora do repositório). ZION_CONFIG_DIR sobrescreve (testes)."""
    override = os.environ.get("ZION_CONFIG_DIR")
    if override:
        return os.path.abspath(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "zion-cli")
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(xdg, "zion-cli")


def creds_path():
    return os.path.join(config_dir(), "credentials.json")


def session_path():
    return os.path.join(config_dir(), "session.json")


def _is_tty():
    try:
        return sys.stdin.isatty() and sys.stderr.isatty()
    except Exception:
        return False


def read_creds():
    path = creds_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_creds(data):
    d = config_dir()
    os.makedirs(d, mode=0o700, exist_ok=True)
    path = creds_path()
    payload = {k: v for k, v in data.items() if v not in (None, "")}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    try:
        os.chmod(path, 0o600)
        os.chmod(d, 0o700)
    except OSError:
        pass


def delete_creds():
    path = creds_path()
    if os.path.exists(path):
        os.remove(path)
    # sessão antiga do mesmo usuário não deve sobreviver ao logout
    for p in (session_path(), os.path.join(os.path.dirname(os.path.abspath(__file__)), ".session.json")):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _prompt_username(default=""):
    hint = f" [{default}]" if default else ""
    while True:
        try:
            u = input(f"Usuário do Zion{hint}: ").strip()
        except EOFError:
            sys.exit("Usuário obrigatório (entrada encerrada).")
        if not u:
            u = default
        if u:
            return u
        print("Usuário obrigatório.", file=sys.stderr)


def _prompt_password(username):
    try:
        pw = getpass.getpass(f"Senha do Zion para {username}: ")
    except EOFError:
        sys.exit("Senha obrigatória (entrada encerrada).")
    if not pw:
        sys.exit("Senha vazia.")
    return pw


def resolve_auth(force_prompt=False, cli_user=None):
    """Resolve (username, password, source, meta).

    Precedência user/senha: CLI/--user e env > arquivo salvo > prompt.
    force_prompt (comando login): pede de novo se não houver env/flag; env ainda ganha
    (modo não-interativo para IAs).
    meta traz url/profile/setor já resolvidos (env > arquivo > defaults).
    """
    saved = read_creds()
    env_user = (cli_user or os.environ.get("ZION_USER") or "").strip()
    env_pw = os.environ.get("ZION_PASSWORD") or ""

    url = (os.environ.get("ZION_URL") or saved.get("url") or DEFAULT_URL).rstrip("/")
    profile = (os.environ.get("ZION_PROFILE") or saved.get("profile") or DEFAULT_PROFILE).strip()
    setor = (os.environ.get("ZION_SETOR") or saved.get("setor") or DEFAULT_SETOR).strip()
    meta = {"url": url, "profile": profile, "setor": setor}

    if env_user and env_pw:
        return env_user, env_pw, "env", meta

    if force_prompt:
        if not _is_tty() and not (env_user or env_pw or saved):
            sys.exit(
                "Sem terminal interativo. Defina ZION_USER e ZION_PASSWORD "
                "(ou rode `python3 zion.py login` num terminal)."
            )
        default_user = env_user or saved.get("username") or ""
        user = env_user or (_prompt_username(default_user) if _is_tty() else default_user)
        if not user:
            sys.exit("Falta ZION_USER (ou rode login num terminal).")
        pw = env_pw or (_prompt_password(user) if _is_tty() else "")
        if not pw:
            sys.exit("Falta ZION_PASSWORD (ou rode login num terminal).")
        return user, pw, "prompt", meta

    if env_user and not env_pw:
        # usuário via env, senha do arquivo do mesmo usuário ou prompt
        if saved.get("username") == env_user and saved.get("password"):
            return env_user, saved["password"], "file", meta
        if _is_tty():
            return env_user, _prompt_password(env_user), "prompt", meta
        sys.exit("Falta ZION_PASSWORD.")

    if not force_prompt and saved.get("username") and saved.get("password"):
        return saved["username"], saved["password"], "file", meta

    if _is_tty():
        user = _prompt_username(saved.get("username") or env_user or "")
        pw = _prompt_password(user)
        return user, pw, "prompt", meta

    sys.exit(
        "Credenciais não encontradas. Rode `python3 zion.py login` (pede usuário e senha) "
        "ou defina ZION_USER e ZION_PASSWORD no ambiente."
    )


def apply_runtime_config(meta, username=None):
    """Atualiza HOST/API/USER/PERFIL/SETOR/SESSION_FILE a partir do meta resolvido."""
    global HOST, API, USER, PERFIL_NOME, SETOR_NOME, SESSION_FILE
    HOST = (meta.get("url") or DEFAULT_URL).rstrip("/")
    API = HOST + "/TasyAppServer/resources"
    if username:
        USER = username
    PERFIL_NOME = meta.get("profile") or DEFAULT_PROFILE
    SETOR_NOME = meta.get("setor") or DEFAULT_SETOR
    SESSION_FILE = session_path()
    # migra sessão antiga ao lado do script, se existir e a nova ainda não
    old = os.path.join(HERE, ".session.json")
    if not os.path.exists(SESSION_FILE) and os.path.exists(old):
        try:
            os.makedirs(config_dir(), mode=0o700, exist_ok=True)
            os.rename(old, SESSION_FILE)
            try:
                os.chmod(SESSION_FILE, 0o600)
            except OSError:
                pass
        except OSError:
            SESSION_FILE = old  # fallback


# Valores iniciais (podem ser sobrescritos em apply_runtime_config / login)
HOST = (os.environ.get("ZION_URL") or DEFAULT_URL).rstrip("/")
API = HOST + "/TasyAppServer/resources"
USER = (os.environ.get("ZION_USER") or "").strip()
PERFIL_NOME = (os.environ.get("ZION_PROFILE") or DEFAULT_PROFILE).strip()
SETOR_NOME = (os.environ.get("ZION_SETOR") or DEFAULT_SETOR).strip()
HERE = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = session_path()
TPL = json.load(open(os.path.join(HERE, "templates.json"), encoding="utf-8"))
TZ = dt.timezone(dt.timedelta(hours=-3))
STATUS = {10: "Prescrições / Pendente coleta", 20: "Material Coletado", 25: "Em Análise",
          26: "Interfaceamento/Fase Analítica", 30: "Digitação do Resultado",
          35: "Resultado Aprovado (Laudado)", 40: "Exame Liberado", 45: "Entrega do exame"}
LIBERADO_STATUS = 40  # Exame Liberado (pós-analítica, IE_RESULT_STAGES)
# fase -> (master, child, campo de etapa)
PHASES = {
    10: ("428260_master", "428461_child", "IE_COLLECT_STAGES", "Pré-analítica"),
    20: ("428260_master", "428461_child", "IE_COLLECT_STAGES", "Pré-analítica"),
    25: ("428260_master", "428461_child", "IE_COLLECT_STAGES", "Pré-analítica"),
    26: ("456352_master", "459320_child", "IE_ANALYSIS_STAGES", "Analítica"),
    30: ("498026_master", "691864_child", "IE_RESULT_STAGES", "Pós-analítica"),
}
NEXT = {10: 20, 20: 25, 25: 26, 26: 30}
SENSITIVE = ("authorization", "crsftoken", "cookie")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


class Zion:
    def __init__(self, verbose=False, cli_user=None):
        self.cli_user = cli_user
        self.s = requests.Session()
        self.s.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": HOST, "Referer": HOST + "/",
            "Locale-Customization": "all", "Developer-Mode": "false",
            "tasyBackendVersion": "dev",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) zion-cli/1.0",
        })
        self.feat = {"Feature-Code": "722", "Active-Feature-Code": "722", "Feature-Route": "corlabf3"}
        self.sess = {}
        self.verbose = verbose
        self.ncalls = 0

    # ---------- sessão ----------
    def _save(self):
        d = os.path.dirname(SESSION_FILE)
        if d:
            os.makedirs(d, mode=0o700, exist_ok=True)
        fd = os.open(SESSION_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.sess, f)
        try:
            os.chmod(SESSION_FILE, 0o600)
        except OSError:
            pass

    def _apply(self):
        self.s.headers["Authorization"] = "Bearer " + self.sess["access_token"]
        if self.sess.get("xsrf"):
            self.s.headers["crsfToken"] = self.sess["xsrf"]
        # Origin/Referer podem mudar se a URL veio do arquivo de credenciais
        self.s.headers["Origin"] = HOST
        self.s.headers["Referer"] = HOST + "/"
        for c in self.sess.get("cookies", []):
            self.s.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))

    def _store_tokens(self, r):
        d = r.json()
        now = time.time()
        self.sess.update({
            "access_token": d["access_token"], "refresh_token": d.get("refresh_token", self.sess.get("refresh_token")),
            "access_exp": now + int(d.get("expires_in", 10)) * 60,
            "refresh_exp": now + int(d.get("refresh_expires", 1440)) * 60,
        })
        if r.headers.get("xsrf-token"):
            self.sess["xsrf"] = r.headers["xsrf-token"]
        self._apply()
        self.sess["cookies"] = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in self.s.cookies]

    def _pick_perfil(self, u, wanted):
        profiles = u.get("profiles") or []
        perfil = next((p for p in profiles if p.get("nmPerfil") == wanted), None)
        if perfil:
            return perfil, wanted
        if len(profiles) == 1:
            only = profiles[0]
            nome = only.get("nmPerfil") or wanted
            log(f"Perfil '{wanted}' não encontrado; usando o único disponível: {nome}")
            return only, nome
        nomes = [p.get("nmPerfil") for p in profiles if p.get("nmPerfil")]
        if _is_tty() and nomes:
            print("Perfis disponíveis:", file=sys.stderr)
            for i, n in enumerate(nomes, 1):
                print(f"  {i}) {n}", file=sys.stderr)
            while True:
                try:
                    raw = input("Escolha o número (ou digite o nome exato): ").strip()
                except EOFError:
                    break
                if raw.isdigit() and 1 <= int(raw) <= len(nomes):
                    nome = nomes[int(raw) - 1]
                    return next(p for p in profiles if p.get("nmPerfil") == nome), nome
                hit = next((p for p in profiles if p.get("nmPerfil") == raw), None)
                if hit:
                    return hit, raw
                print("Opção inválida.", file=sys.stderr)
        lista = ", ".join(nomes) if nomes else "(nenhum)"
        sys.exit(f"Perfil não encontrado: {wanted}. Disponíveis: {lista}")

    def login(self, force_prompt=False, save_creds=True):
        global USER, PERFIL_NOME, SETOR_NOME, HOST, API
        user, pw, source, meta = resolve_auth(force_prompt=force_prompt, cli_user=self.cli_user)
        apply_runtime_config(meta, username=user)
        self.s.headers["Origin"] = HOST
        self.s.headers["Referer"] = HOST + "/"

        self.s.cookies.clear(); self.s.headers.pop("Authorization", None); self.s.headers.pop("crsfToken", None)
        self.sess = {}
        body = {"username": user, "password": pw, "computerName": None, "osUsername": None, "scope": SCOPE,
                "timezone": "America/Sao_Paulo", "ipMachine": None, "sessionUnlock": False}
        r = self.s.post(API + "/public/security/oauth", json=body, timeout=30)
        if r.status_code != 200:
            try:
                msg = r.json().get("message")
            except Exception:
                msg = r.text[:200]
            # senha salva desatualizada → pede de novo e grava
            if source == "file" and _is_tty() and not force_prompt:
                log(f"Login com credenciais salvas falhou (HTTP {r.status_code}). Pedindo de novo…")
                return self.login(force_prompt=True, save_creds=True)
            sys.exit(f"Login falhou (HTTP {r.status_code}): {msg}")

        self._store_tokens(r)
        u = self.s.get(API + "/user/data", timeout=30).json()
        perfil, perfil_nome = self._pick_perfil(u, PERFIL_NOME)
        PERFIL_NOME = perfil_nome
        if u.get("cdPerfil") != perfil["cdPerfil"]:
            r = self.s.post(API + "/user/profile", json={"profile": perfil["cdPerfil"], "changingProfile": True}, timeout=30)
            r.raise_for_status()
            u = r.json() if r.content else self.s.get(API + "/user/data", timeout=30).json()
        setor = next((s for c in u.get("classificationSectors", []) for s in c.get("sectors", []) if s.get("nmSetor") == SETOR_NOME), None)
        if not setor:
            # tenta o setor atual do usuário; se houver só um, usa
            setores = [s for c in u.get("classificationSectors", []) for s in c.get("sectors", [])]
            if len(setores) == 1:
                setor = setores[0]
                SETOR_NOME = setor.get("nmSetor") or SETOR_NOME
                log(f"Setor padrão não encontrado; usando o único disponível: {SETOR_NOME}")
        self.sess.update({"cdPerfil": u.get("cdPerfil"), "cdSetor": u.get("cdSetorAtendimento"),
                          "nmUsuario": u.get("nmUsuario"), "cdEstab": u.get("cdEstabelecimento"),
                          "setor_esperado": setor and setor["cdSetor"]})
        if u.get("cdPerfil") != perfil["cdPerfil"]:
            sys.exit(f"Não consegui trocar para o perfil {PERFIL_NOME} (atual {u.get('cdPerfil')})")
        if setor and u.get("cdSetorAtendimento") != setor["cdSetor"]:
            log(f"AVISO: setor atual {u.get('cdSetorAtendimento')} != {SETOR_NOME} ({setor['cdSetor']})")
        self.sess["cookies"] = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in self.s.cookies]
        self._save()

        if save_creds:
            # grava sempre após login ok (env ou prompt) para próximos usos
            prev = read_creds()
            write_creds({
                "username": user,
                "password": pw,
                "url": HOST,
                "profile": PERFIL_NOME,
                "setor": SETOR_NOME,
                **{k: v for k, v in prev.items() if k not in ("username", "password", "url", "profile", "setor")},
            })
            if source != "file":
                log(f"Credenciais salvas em {creds_path()}")

        log(f"Login OK: {u.get('nmPessoaFisica')} ({u.get('nmUsuario')}), perfil {u.get('cdPerfil')} {PERFIL_NOME}, setor {u.get('cdSetorAtendimento')}")
        return u

    def refresh(self):
        r = self.s.post(API + "/public/security/oauth/refresh",
                        json={"refreshToken": self.sess["refresh_token"], "accessToken": self.sess["access_token"]}, timeout=30)
        if r.status_code != 200:
            return False
        self._store_tokens(r); self._save()
        return True

    def ensure(self):
        apply_runtime_config({
            "url": HOST, "profile": PERFIL_NOME, "setor": SETOR_NOME,
        }, username=USER or None)
        # se há credenciais/env, aplica URL/user delas antes de reusar sessão
        saved = read_creds()
        meta = {
            "url": (os.environ.get("ZION_URL") or saved.get("url") or HOST).rstrip("/"),
            "profile": (os.environ.get("ZION_PROFILE") or saved.get("profile") or PERFIL_NOME).strip(),
            "setor": (os.environ.get("ZION_SETOR") or saved.get("setor") or SETOR_NOME).strip(),
        }
        apply_runtime_config(meta, username=(os.environ.get("ZION_USER") or saved.get("username") or USER or None))

        if not self.sess and os.path.exists(SESSION_FILE):
            try:
                self.sess = json.load(open(SESSION_FILE)); self._apply()
            except Exception:
                self.sess = {}
        now = time.time()
        if not self.sess or now > self.sess.get("refresh_exp", 0) - 60:
            return self.login()
        if now > self.sess.get("access_exp", 0) - 60 and not self.refresh():
            return self.login()

    # ---------- chamadas ----------
    def post(self, path, body, feature=True, _retry=True):
        self.ensure()
        h = dict(self.feat) if feature else {}
        self.ncalls += 1
        r = self.s.post(API + "/service/" + path, json=body, headers=h, timeout=90)
        if r.status_code in (401, 403) and _retry:
            if not self.refresh():
                self.login()
            return self.post(path, body, feature, _retry=False)
        if r.status_code != 200:
            raise RuntimeError(f"{path}: HTTP {r.status_code} {r.text[:300]}")
        if r.headers.get("xsrf-token") and r.headers["xsrf-token"] != self.sess.get("xsrf"):
            self.sess["xsrf"] = r.headers["xsrf-token"]; self.s.headers["crsfToken"] = self.sess["xsrf"]; self._save()
        return r.json() if r.content else None

    def datasource(self, body):
        d = self.post("WCPanelDataProvider/getDataSource", [body])
        return (d or {}).get("dados", {}).get("linhasResultSet", [])


# ---------- montagem de corpos ----------
def date_range(days=4):
    today = dt.datetime.now(TZ).date()
    ini = dt.datetime.combine(today - dt.timedelta(days=days), dt.time(0, 0, 0), TZ)
    fim = dt.datetime.combine(today, dt.time(23, 59, 59), TZ)
    f = lambda x: {"@class": "java.time.Instant", "type": "INSTANT",
                   "value": x.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}
    return f(ini), f(fim)


def _set_filter(p, atend, status, stage_field, ini, fim):
    p["DT_INICIAL"], p["DT_FINAL"] = copy.deepcopy(ini), copy.deepcopy(fim)
    p["NR_ATENDIMENTO"] = atend
    p[stage_field] = status


def master_body(phase, atend):
    mk, _, sf, _ = PHASES[phase]
    b = copy.deepcopy(TPL[mk]); ini, fim = date_range()
    p = b["parameters"]
    _set_filter(p, atend, phase, sf, ini, fim); p["IE_STATUS_ATEND"] = phase
    if "filterValues" in b:
        _set_filter(b["filterValues"], atend, phase, sf, ini, fim)
    return b


def to_request_value(v):
    if isinstance(v, dict) and v.get("tipo") == "INSTANT":
        val = v["value"]
        if val.endswith("Z") and "." not in val:
            val = val[:-1] + ".000Z"
        return {"@class": "java.time.Instant", "type": "INSTANT", "value": val}
    return v


def child_body(phase, atend, row):
    _, ck, sf, _ = PHASES[phase]
    b = copy.deepcopy(TPL[ck]); ini, fim = date_range()
    p = b["parameters"]
    _set_filter(p["PARENT_FILTER_PARAMS"], atend, phase, sf, ini, fim)
    p["IE_STATUS_ATEND"] = phase
    p["DT_INICIAL"], p["DT_FINAL"] = ini, fim
    p["PENDING_PRESCRIPTION_VALUES"] = {k: to_request_value(v) for k, v in row.items()}
    return b


def collect(z, atend, phases=(10, 20, 25, 26, 30)):
    """Retorna lista de amostras: dict(fase, row, exames)."""
    out = []
    for ph in phases:
        for row in z.datasource(master_body(ph, atend)):
            ex = z.datasource(child_body(ph, atend, row))
            out.append({"fase": ph, "row": row, "exames": ex})
    return out


# ---------- sequência de "Alterar status" ----------
def H(v): return {"tipo": "HashMap", "valor": v}


def plan_sample(z, amostra, cur, target=30):
    row, ex = amostra["row"], amostra["exames"]
    nr = row["NR_PRESCRICAO"]; amos = row["NR_SEQ_AMOSTRA"]; pf = str(row.get("CD_PESSOA_FISICA"))
    seqs = [e["NR_SEQ_PRESCR"] for e in ex]
    if not seqs:
        return []
    lst = ",".join(map(str, seqs)); dsql = f" and c.nr_sequencia in ({lst})"
    sqlitem = "".join(f"{s} " for s in seqs)
    user = z.sess.get("nmUsuario") or USER
    steps = []
    while cur in NEXT and cur < target:
        nxt = NEXT[cur]; sn = str(nxt)
        R = lambda p, b, w=True: steps.append((cur, nxt, p, b, w))
        if cur != 26:
            R("MatrixServices/isActive", [], False)
        R("CorLabF3/executaProcedurePadrao28710", [H({"NR_PRESCRICAO_P": nr})])
        R("CorLabF3/executeFunction", [{"tipo": "String", "valor": "GET_STATUS_DESCRIPTION"}, H({"VL_DOMINIO_P": sn})], False)
        R("CorLabF3/executaProcedurePadrao33538", [H({"NR_PRESCRICAO_P": nr, "CD_PESSAO_FISICA_P": pf})])
        if cur == 10:
            R("CorLabF3/executaProcedurePadrao28842", [H({
                "NR_PRESCRICAO_P": nr, "NR_SEQ_PRESCR_P": seqs[0], "NR_SEQ_PROCED_P": lst,
                "NR_SEQ_PRESCR_PROC_MAT_P": amos, "IE_STATUS_ATEND_P": cur, "IE_CHAMADA_AMOSTRA_P": "N",
                "IE_ADM_EXAM_ADEP_P": "S", "IE_CONSISTIR_ALT_PESO_P": "N", "IE_CHAMADA_BARRAS_P": "N",
                "DS_SQL_ITEM_P": dsql, "IE_REGISTRAR_MEDIC_USO_P": "N", "DS_SQL_MATERIAL_P": "",
                "NR_SEQ_MOTIVO_ATRASO_P": ""})])
        if cur == 20:
            R("CorLabF3/executaConsultaPadraoAsHashMap690226", [H({"NR_PRESCRICAO": nr, "IE_STATUS_ATEND": cur})], False)
        if cur in (10, 20):
            R("CorLabF3/executaProcedurePadrao55029", [H({"NR_PRESCRICAO_P": nr, "DS_RESTRICAO_P": dsql, "NM_USUARIO_P": user})])
        lab = ("CorLabF3/labUpdateStageSample", [H({"NR_PRESCRICAO_P": nr, "IE_STATUS_ATEND_P": nxt if cur == 26 else sn,
                                                   "NR_SEQ_AMOSTRA_P": amos, "SQL_ITEM_P": sqlitem, "NM_USUARIO_P": user})])
        pard = ("CorLabF3/executePardiniIntegration", [{"tipo": "Integer", "valor": nr}, {"tipo": "Integer", "valor": sn}])
        if cur == 26:   # analítica: labUpdateStageSample antes do Pardini
            R(*lab); R(*pard)
        else:
            R(*pard)
            R("CorLabF3/executeProcedure", [{"tipo": "String", "valor": "UPDATE_LAST_DOSE_MEDIC"}, H({
                "NR_PRESCRICAO_P": nr, "IE_STATUS_ATUAL_P": cur, "IE_STATUS_P": sn, "DS_SQL_ITEM_P": dsql,
                "IE_UTILIZACAO_P": "D"})])
            R(*lab)
        cur = nxt
    return steps


def check_response(path, resp):
    """Bloqueia quando a tela abriria um diálogo/consistência que não sabemos tratar."""
    if not isinstance(resp, dict):
        return
    v = lambda k: (resp.get(k) or {}).get("valor") if isinstance(resp.get(k), dict) else resp.get(k)
    # QT_EXAME_SUSP_P conta itens suspensos da PRESCRIÇÃO inteira. Esses itens não aparecem na fila de
    # Exames Pendentes (só movemos linhas que a própria fila trouxe), e o navegador segue normalmente sem
    # diálogo (conferido no 809603, prescr 5808623 com QT_EXAME_SUSP_P=1). Então só avisa e continua.
    if path.endswith("28710") and str(v("QT_EXAME_SUSP_P") or "0") != "0":
        print(f"  (aviso: prescrição tem {v('QT_EXAME_SUSP_P')} exame(s) suspenso(s) fora da fila - igual ao navegador, segue)")
    if path.endswith("33538") and v("DS_EXAMES_MEST_P"):
        raise RuntimeError("33538 pediu data da menstruação (DS_EXAMES_MEST_P) - parei")
    if path.endswith("28842") and v("DS_MENSAGEM_P"):
        raise RuntimeError(f"28842 mensagem: {v('DS_MENSAGEM_P')} - parei")
    # HAR 808887 (amostra 1167258, COOD/GP-TIP): com IE_GERAR_AMOSTRA=S a tela não abre diálogo nem gera
    # amostra; segue a mesma sequência (55029, Pardini, UPDATE_LAST_DOSE_MEDIC, labUpdateStageSample).
    if path.endswith("690226") and resp.get("IE_GERAR_AMOSTRA") == "S":
        print("  (690226 IE_GERAR_AMOSTRA=S - igual ao navegador: segue sem gerar amostra)")
    if path.endswith("690226") and resp.get("IE_GERAR_AMOSTRA") not in (None, "N", "S"):
        raise RuntimeError(f"690226 IE_GERAR_AMOSTRA={resp.get('IE_GERAR_AMOSTRA')} (fluxo não mapeado) - parei")


def fmt_sample(a):
    r = a["row"]
    exs = ", ".join(f"{e.get('NR_SEQ_PRESCR')}:{e.get('CD_EXAME') or e.get('DS_PROCEDIMENTO')}[{e.get('IE_STATUS_ATEND')}]" for e in a["exames"])
    return f"  prescr {r.get('NR_PRESCRICAO')} amostra {r.get('NR_SEQ_AMOSTRA')} ({len(a['exames'])} exames): {exs}"


def cmd_fila(z, status=None, exames=False, atend_only=False):
    """Fila geral (sem número de atendimento): pendentes por etapa nos últimos 4 dias."""
    phases = [status] if status else list(PHASES)
    tot_at = set()
    for ph in phases:
        rows = z.datasource(master_body(ph, None))
        ats = {}
        for r in rows:
            ats.setdefault(r.get("NR_ATENDIMENTO"), []).append(r)
        tot_at.update(ats)
        print(f"[{PHASES[ph][3]}] status {ph} {STATUS[ph]}: {len(ats)} atendimento(s), {len(rows)} amostra(s)")
        if atend_only:
            continue
        for at, rs in ats.items():
            r = rs[0]
            print(f"  AT {at} | {r.get('NM_PESSOA_FISICA')} | {r.get('DS_SETOR_ATUAL')} | leito {str(r.get('LEITO_ATUAL') or '').strip()}")
            if exames:
                for row in rs:
                    ex = z.datasource(child_body(ph, None, row))
                    print("  " + fmt_sample({"row": row, "exames": ex}))
    print(f"Total: {len(tot_at)} atendimento(s) distintos (um atendimento pode estar em mais de uma etapa).")


def cmd_listar(z, atend):
    data = collect(z, atend)
    if data:
        r = data[0]["row"]
        print(f"Atendimento {atend}: {r.get('NM_PESSOA_FISICA')} | {r.get('DS_SETOR_ATUAL')} | leito {str(r.get('LEITO_ATUAL') or '').strip()}")
    for ph in PHASES:
        items = [a for a in data if a["fase"] == ph]
        print(f"[{PHASES[ph][3]}] status {ph} {STATUS[ph]}: {len(items)} amostra(s), {sum(len(a['exames']) for a in items)} linha(s)")
        for a in items:
            print(fmt_sample(a))
    if not data:
        print("Nenhuma linha encontrada nos últimos 4 dias.")
    return data


def cmd_digitacao(z, atend, dry, desde=None):
    data = collect(z, atend)
    todo = [a for a in data if a["fase"] < 30]
    if desde is not None:
        if not dry:
            sys.exit("--desde só pode ser usado com --dry-run")
        todo = [dict(a, fase=desde) for a in data]
        print(f"(simulação: tratando as {len(todo)} amostra(s) como se estivessem em status {desde})")
    if not todo:
        print(f"Nada a fazer: {sum(len(a['exames']) for a in data)} linha(s) já em Digitação (30)." if data else "Nenhuma linha encontrada.")
        return
    n = 0
    for a in sorted(todo, key=lambda a: a["fase"]):
        steps = plan_sample(z, a, a["fase"])
        print(f"\n== amostra {a['row']['NR_SEQ_AMOSTRA']} prescr {a['row']['NR_PRESCRICAO']} : {a['fase']} -> 30 ({len(steps)} requisições)")
        for cur, nxt, path, body, writes in steps:
            n += 1
            tag = "GRAVA" if writes else "leitura"
            if dry:
                print(f"POST {API}/service/{path}  [{cur}->{nxt}] ({tag})")
                print("     headers: Feature-Code=722 Active-Feature-Code=722 Feature-Route=corlabf3 Authorization=<oculto> crsfToken=<oculto>")
                print("     body: " + json.dumps(body, ensure_ascii=False))
                continue
            resp = z.post(path, body)
            check_response(path, resp)
            print(f"  ok {path} [{cur}->{nxt}]")
    print(f"\nTotal: {n} requisições {'(dry-run, nada enviado)' if dry else 'executadas'}")
    if not dry:
        final = collect(z, atend)
        print("\nConferência pós-analítica:")
        for a in final:
            if a["fase"] == 30: print(fmt_sample(a))


# ---------- digitação de resultados (WResultEntry) ----------
TREE_OBJ = 687486
TREE_ACTION = "CorLabF3.MontarArvoreResultadoAction"
# label da gasometria -> (opção CLI, siglas de bioquímica equivalentes)
GASO_FIELDS = [("pH", "ph", []), ("PCO2", "pco2", []), ("pO2", "po2", []), ("HCO3", "hco3", []),
               ("BE", "be", []), ("Sat O2", "so2", []), ("HB", "hb", []), ("Hct", "hct", []),
               ("NA++", "na", ["NA+", "NA"]), ("K+", "k", ["K+", "K"]), ("iCA++", "ica", ["CAI", "CAIO"]),
               ("CL-", "cl", ["CL", "CL-"]), ("Gli", "glu", ["GLI", "GLIC", "GLICO"]), ("LAC", "lac", ["LAC", "LACT", "LACTATO"])]
GASO_FIELDS += [("BIL", "bil", [])]
GASO_SIGLAS = ("GASO", "GASA", "GASV", "GAS")
# opção CLI -> slugs possíveis do nmExame do subexame da gasometria (GASV/GASA/...)
GASO_SLUGS = {"ph": ["ph"], "pco2": ["pco2"], "po2": ["po2"], "hco3": ["hco3"], "be": ["be"],
              "so2": ["sato2", "so2", "sat02"], "hb": ["hb", "hgb"], "hct": ["hct", "ht"],
              "na": ["na", "nat"], "k": ["k"], "ica": ["cai", "ica", "caionico"], "cl": ["cl"],
              "glu": ["gli", "glu", "glic", "glicose"], "lac": ["lac", "lactato"], "bil": ["bil", "bili"]}


def S(v): return {"tipo": "String", "valor": v}
def I(v): return {"tipo": "Integer", "valor": v}
def M(v): return {"tipo": "Map", "valor": v}


def norm_inst(x):
    """Converte instantes vindos do servidor para o formato que a tela envia."""
    if isinstance(x, dict):
        if x.get("@class") == "java.time.Instant" or (x.get("tipo") == "INSTANT" and ("value" in x or "dados" in x)):
            v = x.get("value", x.get("dados"))
            if v.endswith("Z") and "." not in v: v = v[:-1] + ".000Z"
            return {"@class": "java.time.Instant", "type": "INSTANT", "value": v}
        return {k: norm_inst(v) for k, v in x.items()}
    if isinstance(x, list): return [norm_inst(v) for v in x]
    return x


def parse_val(txt):
    t = str(txt).strip().replace(",", ".")
    f = float(t)
    dec = len(t.split(".")[1]) if "." in t else 0
    return f, dec, t


def fmt_br(f, dec): return f"{f:.{dec}f}".replace(".", ",")


class Resultado:
    """Uma 'tela' de digitação para uma prescrição."""
    def __init__(self, z, atend, nr_presc, write):
        self.z, self.atend, self.nr, self.write = z, atend, nr_presc, write
        self.items = []; self.nodes = {}; self.groups = []

    def filtro(self, seq_res, seq_proc):
        m = copy.deepcopy(TPL["resultado_filtro"]); ini, fim = date_range(3)
        m.update(NR_SEQUENCIA_PROC=seq_proc, NR_SEQ_RESULTADO=seq_res, NR_ATENDIMENTO=self.atend)
        f = m["DS_FILTRO_RESULTADO"]; f["DT_INICIAL"], f["DT_FINAL"] = ini, fim; f["NR_ATENDIMENTO"] = self.atend
        return m

    def ativar(self):
        d = self.z.post("CorLabF3/ativarExameLabResultItemAsHashMap", [H({"NR_PRESCRICAO": self.nr, "IE_GERAR_RESULT_PRESCR": False,
                        "IE_INTEG_CURVA_AMOSTRA": "N", "NR_SEQ_GRUPO_EXAME": 0})])
        self.items = (d or {}).get("dados", [])
        return self.items

    def tree(self, level, parent, filt):
        d = self.z.post("WJTreeNew/carregarWJTreeNew", [S(TREE_ACTION), I(TREE_OBJ), I(level), M(parent), M(filt), M({})])
        return [n["sqlProjection"] for n in (d or {}).get("dados", [])]

    def abrir(self):
        z = self.z
        z.post("WJTreeNew/obterPropriedades", [I(TREE_OBJ)])
        if self.write:   # a tela chama ao abrir a digitação (prepara laudo/resultado) - só no modo gravação
            z.post("CorLabF3/executaProcedurePadrao1173", [H({"NR_PRESCRICAO_P": self.nr, "IE_SOMENTE_AMOSTRA_P": False,
                   "IE_DIGITACAO_P": "S", "IE_GERA_LAUDO_P": "S", "IE_VINCULA_FORMATO_P": "S"})])
        self.tree(1, {}, {})
        self.ativar()
        if not self.items: return self
        it0 = self.items[0]
        self.seq_res = it0["NR_SEQ_RESULTADO"]
        self.filt = self.filtro(self.seq_res, it0.get("NR_SEQUENCIA", 1))
        z.post("WJTreeNew/obterPropriedades", [I(TREE_OBJ)])
        self.groups = self.tree(1, {}, self.filt)
        for g in self.groups:
            for n in self.tree(2, g, self.filt):
                self.nodes[n["NR_SEQ_PRESCR"]] = (g, n)
        z.post("CorLabF3/executeQuery", [S("GET_QT_SEM_DIGITACAO_PRESCR"), H({})])
        z.post("CorLabF3/executeQuery", [S("GET_IE_DUPLA_CHECAGEM_RES"), H({})])
        return self

    def build(self, seq_prescr):
        n = self.nodes[seq_prescr][1]
        person = {"IE_SEXO_P": n.get("IE_SEXO"), "DT_NASCIMENTO_P": norm_inst(n.get("DT_NASCIMENTO")),
                  "NR_SEQ_COR_PELE_P": n.get("NR_SEQ_COR_PELE"),
                  # a tela envia assim mesmo (altura<-QT_PESO, peso<-QT_ALTURA_CM)
                  "QT_ALTURA_P": n.get("QT_PESO"), "QT_PESO_P": n.get("QT_ALTURA_CM")}
        return self.z.post("WResultEntry/build", [H({"NR_PRESCRICAO_P": self.nr, "NR_SEQUENCIA_P": seq_prescr,
                           "PERSON_P": person, "ALLOW_NOT_ACCEPTABLE_P": True})])

    def clicar(self, seq_prescr, nr_seq_exame):
        z = self.z; g, n = self.nodes[seq_prescr]
        self.tree(3, n, self.filt)
        z.post("CorLabF3/executeQuery", [S("GET_QT_SEM_DIGITACAO_PRESCR"), H({"NR_SEQ_RESULTADO": self.seq_res})])
        self.ativar()
        z.post("CorLabF3/executeQuery", [S("GET_IE_DUPLA_CHECAGEM_RES"), H({"NR_SEQ_EXAME": nr_seq_exame})])
        return self.build(seq_prescr)

    def salvar(self, vo, seq_prescr, nr_seq_exame):
        z = self.z; g, n = self.nodes[seq_prescr]
        r = z.post("WResultEntry/save", [H(vo)])
        cons = z.post("CorLabF3/executeProcedure", [S("CONSISTE_APROV_FORMULA"), H({"NR_PRESCRICAO_P": self.nr, "NR_SEQ_PRESCR_P": seq_prescr})])
        b = self.build(seq_prescr)
        self.tree(2, g, self.filt)
        z.post("CorLabF3/executeQuery", [S("GET_QT_SEM_DIGITACAO_PRESCR"), H({"NR_SEQ_RESULTADO": self.seq_res})])
        self.ativar()
        z.post("CorLabF3/executeQuery", [S("GET_IE_DUPLA_CHECAGEM_RES"), H({"NR_SEQ_EXAME": nr_seq_exame})])
        return r, cons, b


def main_sub(vo):
    """subExam principal (o mesmo nrSeqExame do 'exam')."""
    ex = vo["exam"]
    for s in vo["subExams"]:
        if s["nrSeqExame"] == ex["nrSeqExame"]: return s
    return None


def cur_value(vo):
    s = main_sub(vo)
    if not s: return None
    if s.get("ieFormatoResultado") in ("V", "DV"):
        q = s.get("qtResultado")
        return None if q in (None, 0, "") else float(q)
    return s.get("dsResultado") or None


def prescricoes(z, atend):
    data = collect(z, atend, phases=(30,))
    seen = []
    for a in data:
        nr = a["row"]["NR_PRESCRICAO"]
        if nr not in seen: seen.append(nr)
    return data, seen


def abrir_telas(z, atend, write):
    data, prs = prescricoes(z, atend)
    telas = [Resultado(z, atend, nr, write).abrir() for nr in prs]
    return data, [t for t in telas if t.items]


def cmd_ler(z, atend):
    data, telas = abrir_telas(z, atend, write=False)
    if not telas:
        print("Nenhum exame em Digitação (30) para este atendimento."); return
    amos = {a["row"]["NR_PRESCRICAO"]: a["row"].get("NR_SEQ_AMOSTRA") for a in data}
    for t in telas:
        print(f"== prescrição {t.nr} (resultado {t.seq_res}, amostra {amos.get(t.nr)})")
        for it in sorted(t.items, key=lambda i: i["NR_SEQ_PRESCR"]):
            seq = it["NR_SEQ_PRESCR"]
            if seq not in t.nodes:
                print(f"  {it['CD_EXAME']:<8} seq {seq}: fora da árvore de digitação"); continue
            vo = t.build(seq)["ResultVO"]
            if str(it.get("CD_EXAME", "")).upper() == HEMO_SIGLA:
                cmd_ler_hemo(t, it, vo); continue
            s = main_sub(vo); v = cur_value(vo)
            dec = (s or {}).get("qtDecimais") or 0
            vs = "-" if v is None else ((num_txt(v).replace(".", ",") if s.get("ieFormatoResultado") == "DV" else fmt_br(v, dec)) if isinstance(v, (int, float)) else v)
            subs = [x for x in vo["subExams"] if x is not s and (x.get("qtResultado") not in (None, 0) or x.get("dsResultado"))]
            extra = "; ".join(f"{x['nmExame']}={x.get('dsResultado') or x.get('qtResultado')}" for x in subs)
            print(f"  {it['CD_EXAME']:<8} seq {seq:<3} {it['NM_EXAME'].strip():<38} = {vs} {(s or {}).get('dsUnidadeMedida','')}"
                  f"  [status {vo.get('ieStatusAtend')}]" + (f"  ({extra})" if extra else ""))


def ds_payload(vo, env):
    """Reproduz o save da tela (HAR 808861/803328): subexames V/DV vão com qtResultado em TEXTO
    ("5.01", "0") e dsResultado=None; subexames D/DL vão com qtResultado=None e dsResultado como está
    ('' quando vazio). O 'exam' espelha o subexame principal. env = {nrSeqExame: float}."""
    novo = norm_inst(copy.deepcopy(vo))
    for x in novo["subExams"]:
        if x.get("ieFormatoResultado") in ("V", "DV"):
            v = env.get(x["nrSeqExame"], None if x.get("qtResultado") in (None, "") else float(x["qtResultado"]))
            x["qtResultado"] = None if v is None else num_txt(v); x["dsResultado"] = None
        else:
            x["qtResultado"] = None
            if x["nrSeqExame"] in env: x["dsResultado"] = env[x["nrSeqExame"]]   # lista (S) / texto (D, DL)
            if x.get("dsResultado") is None: x["dsResultado"] = ""
    m = main_sub(novo)
    if m: novo["exam"]["qtResultado"], novo["exam"]["dsResultado"] = m["qtResultado"], m["dsResultado"]
    return novo


def is_num(x): return x.get("ieFormatoResultado") in ("V", "DV")


def sub_val(x):
    if not is_num(x):
        d = x.get("dsResultado"); return d if d else None
    q = x.get("qtResultado")
    return None if q in (None, "") else float(q)


def vtxt(v): return v if isinstance(v, str) else num_txt(v)


def vdiff(a, b):
    if isinstance(a, str) or isinstance(b, str): return str(a) != str(b)
    return abs(a - b) > 1e-9


import unicodedata
def _slug(t): return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if c.isalnum())


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn")


# Exames que vão para laboratório externo — NÃO digitar valor por enquanto.
# Lista editável (siglas). A trava também cobre qualquer exame cujo NOME contenha
# "Sorologia" (ignora maiúsculas/acentos). NÃO confundir com testes rápidos
# (TRTOXO, HIV, TRS, TRHCV, …), que continuam sendo digitados normalmente.
# sorologia ≠ teste rápido. Sem override (nem --forcar).
EXAMES_EXTERNOS_BLOQUEADOS = {
    "TOXG", "TOXM",           # Sorologia Toxoplasmose IgG / IgM
    "HBSAG", "HCV",           # Hepatite B Ag / Anti-HCV
    "HBCM", "HBCG", "A-HBS",  # Hepatite B Anti-HBc / anti-HBs
    "CMVG", "CMVM",           # Citomegalovírus IgG / IgM
    "RUGE", "RUME",           # Rubéola IgG / IgM
    "HIV1/2",                 # Sorologia HIV (≠ Teste Rápido HIV)
}


def exame_externo_bloqueado(it_or_cd, nm=None):
    """True se for sorologia/exame externo: recusar qualquer digitação."""
    if isinstance(it_or_cd, dict):
        cd = str(it_or_cd.get("CD_EXAME") or "").strip()
        nm = str(it_or_cd.get("NM_EXAME") or "")
    else:
        cd = str(it_or_cd or "").strip()
        nm = str(nm or "")
    if cd.upper() in {x.upper() for x in EXAMES_EXTERNOS_BLOQUEADOS}:
        return True
    if "sorologia" in _sem_acento(nm).lower():
        return True
    return False


def msg_bloqueio_externo(it):
    cd = (it.get("CD_EXAME") if isinstance(it, dict) else it) or "?"
    nm = ((it.get("NM_EXAME") if isinstance(it, dict) else "") or "").strip()
    nome = f"{cd}" + (f" ({nm})" if nm else "")
    return (f"{nome}: BLOQUEADO — sorologia/exame externo (vai para outro laboratório). "
            "Não digitar valor por enquanto. sorologia ≠ teste rápido "
            "(TRTOXO/HIV/TRS/TRHCV seguem normais). Sem override, nem com --forcar.")


# apelidos de campo -> trecho do nmExame do subexame
FIELD_ALIAS = {"abo": "tiposanguineoabo", "rh": "fatorrhd", "du": "fatordu", "ci": "coombsindireto",
               "coombsindireto": "coombsindireto", "obs": "observacao"}


def achar_sub(vo, nome):
    subs = vo["subExams"]
    seq = MULTI.get(vo["exam"].get("nrSeqExame"), {}).get(nome)
    if seq: return next((x for x in subs if x["nrSeqExame"] == seq), None)
    if str(nome).isdigit(): return next((x for x in subs if str(x["nrSeqExame"]) == nome), None)
    key = FIELD_ALIAS.get(_slug(nome), _slug(nome))
    hits = [x for x in subs if _slug(x.get("nmExame")) == key] or [x for x in subs if key in _slug(x.get("nmExame"))]
    return hits[0] if len(hits) == 1 else None


def _plus_count(txt):
    """Se txt for uma graduação em cruzes, devolve 1..4; senão None."""
    t = str(txt).strip().lower().replace(" ", "")
    if re.fullmatch(r"\+{1,4}", t):
        return len(t)
    m = re.fullmatch(r"([1-4])\+", t) or re.fullmatch(r"\+([1-4])", t)
    if m:
        return int(m.group(1))
    # "positivo+", "positivo ++", "pos +", "reagente ++"
    m = re.fullmatch(r"(?:positivo|pos|reagente)\+{1,4}", t)
    if m:
        return t.count("+")
    m = re.fullmatch(r"(?:positivo|pos|reagente)([1-4])\+", t)
    if m:
        return int(m.group(1))
    return None


def _ausente_alias(txt):
    t = str(txt).strip().lower()
    if t in ("-", "--", "---", "–", "—"):
        return True
    return _slug(t) in ("ausente", "negativo", "negativa", "neg", "nao", "naoagente", "naoreagente", "nr")


def _match_opcao(txt, ops):
    """Casa txt com uma opção da lista. Ordem: exato > alias +/- > slug > fuzzy.
    Nunca deixa '++' virar '+' (slug de '+' é vazio). Rejeita ambíguo."""
    t = str(txt).strip()
    if not t or not ops:
        return None
    # 1) texto exato (case-insensitive) — crítico para +/++/+++/++++
    ex = [o for o in ops if str(o).strip().upper() == t.upper()]
    if len(ex) == 1:
        return ex[0]
    if len(ex) > 1:
        return None
    # 2) aliases de cruzes / ausente / negativo
    nplus = _plus_count(t)
    if nplus is not None:
        target = "+" * nplus
        hit = [o for o in ops if str(o).strip() == target]
        if len(hit) == 1:
            return hit[0]
        # cilindros/cristais: "Hemáticos ++ | 4+", "Hialinos ++|4+", etc.
        hit = [o for o in ops if ("+" * nplus) in str(o) and ("+" * (nplus + 1)) not in str(o).replace("4+", "")]
        # filtrar opções cujo trecho de cruzes é exatamente nplus (antes de | ou fim)
        def _cruzes_em(o):
            m = re.search(r"(\+{1,4})", str(o))
            return len(m.group(1)) if m else None
        hit = [o for o in ops if _cruzes_em(o) == nplus]
        if len(hit) == 1:
            return hit[0]
        return None  # ambíguo ou inexistente
    if _ausente_alias(t):
        prefer = ["Ausente", "Negativo", "Negativa", "Neg."]
        for p in prefer:
            hit = [o for o in ops if str(o).strip().upper() == p.upper()]
            if len(hit) == 1:
                return hit[0]
        hit = [o for o in ops if _slug(o) in ("ausente", "negativo", "negativa")]
        if len(hit) == 1:
            return hit[0]
        return None
    # 3) slug exato (só se o slug do input não for vazio — evita '+' casar com tudo)
    st = _slug(t)
    if st:
        hit = [o for o in ops if _slug(o) == st]
        if len(hit) == 1:
            return hit[0]
        # 4) fuzzy (ligeiramente turvo -> Ligeiramento Turvo)
        scored = sorted(
            ((difflib.SequenceMatcher(None, st, _slug(o)).ratio(), o) for o in ops),
            key=lambda x: -x[0],
        )
        scored = [(r, o) for r, o in scored if r >= 0.84]
        if scored and (len(scored) == 1 or scored[0][0] >= scored[1][0] + 0.04):
            return scored[0][1]
    return None


def valor_campo(s, txt):
    """-> (valor, dec) ou str de erro. V/DV: float; S: opção da lista; D/DL: texto livre."""
    fmt = s.get("ieFormatoResultado")
    if fmt in ("V", "DV"):
        try: f, dec, _ = parse_val(txt)
        except ValueError: return f"'{txt}' não é número"
        return f, dec
    if fmt == "S":
        ops = [o.get("CD") for o in (s.get("optionalValues") or [])]
        m = _match_opcao(txt, ops)
        if m is None:
            return f"'{txt}' inválido para {s.get('nmExame')} (opções: {' / '.join(ops)})"
        return m, 0
    if fmt in ("D", "DL"): return str(txt), 0
    return f"formato {fmt} não suportado"


# ---- EAS (URN1): pares de sedimento e aliases à prova de IA ----
# Papel "13.000/mL" -> campo simples=13, campo (x1000)=13000.
# Se a IA mandar 13000 no simples, a tela/servidor multiplica e grava 13000000.
EAS_SED_PAIRS = [
    # (slug do simples, slug do x1000, rótulo p/ log)
    ("celulasepiteliais", "celulasepiteliaisx1000", "Células epiteliais"),
    ("leucocitospiocitos", "leucocitosx1000", "Leucócitos (Piócitos)"),
    ("hemacias", "hemaciasx1000", "Hemácias"),
]
# apelidos -> slug canônico do campo (simples ou x1000)
EAS_SED_ALIAS = {
    "celulas": "celulasepiteliais",
    "celula": "celulasepiteliais",
    "celulasepiteliais": "celulasepiteliais",
    "celulasepiteliaisx1000": "celulasepiteliaisx1000",
    "epiteliais": "celulasepiteliais",
    "leucocitosml": "leucocitospiocitos",
    "leucocitospiocitos": "leucocitospiocitos",
    "leucocitosx1000": "leucocitosx1000",
    "piocitos": "leucocitospiocitos",
    "piocito": "leucocitospiocitos",
    "hemacias": "hemacias",
    "hemaciasml": "hemacias",
    "hemaciasx1000": "hemaciasx1000",
    "he": "hemacias",
}


def _eas_parse_count(txt):
    """Aceita 13, 13000, 13.000, 13.000/mL, 13,000/ml."""
    s = str(txt).strip().lower()
    s = re.sub(r"\s*/\s*(ml|µl|ul)\s*$", "", s).strip()
    s = s.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        return float(s.replace(".", ""))
    if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        return float(s.replace(",", ""))
    return parse_val(s)[0]


def _eas_looks_numeric(txt):
    try:
        _eas_parse_count(txt)
        return True
    except Exception:
        return False


def _eas_pair_values(simple_txt=None, x1000_txt=None):
    """Devolve (simples, x1000, per_ml) normalizados a partir de qualquer lado do par."""
    per_ml = None
    if simple_txt is not None:
        v = _eas_parse_count(simple_txt)
        # >=1000 no simples = a IA mandou o /mL no campo errado
        per_ml = v if v >= 1000 else v * 1000
    if x1000_txt is not None:
        v = _eas_parse_count(x1000_txt)
        if per_ml is None:
            per_ml = v  # x1000 é sempre a contagem /mL
        else:
            # se os dois vieram, prefere o que parece /mL cheio
            if v >= 1000:
                per_ml = v
    if per_ml is None:
        raise ValueError("par de sedimento sem valor")
    per_ml = int(round(float(per_ml)))
    return per_ml / 1000.0, float(per_ml), per_ml


def _eas_sub_by_slug(vo):
    return {_slug(x.get("nmExame")): x for x in vo["subExams"]}


def _is_eas_vo(vo):
    slugs = {_slug(x.get("nmExame")) for x in vo["subExams"]}
    return "celulasepiteliais" in slugs and "celulasepiteliaisx1000" in slugs


def completar_eas(vo, campos):
    """Normaliza EAS/URN1: aliases, Leucócitos numérico->Piócitos, pares simples/x1000."""
    if not _is_eas_vo(vo):
        return campos
    by = _eas_sub_by_slug(vo)
    # remapeia chaves (inclui None? não) para slug canônico
    raw = {}
    for nome, txt in campos.items():
        if nome is None:
            raw[None] = txt
            continue
        key = _slug(nome)
        # Leucócitos (dipstick S) vs Leucócitos (Piócitos) DV:
        # número -> sedimento; +/Ausente -> fita.
        if key in ("leucocitos", "leucocito"):
            if _eas_looks_numeric(txt) and not (_plus_count(txt) or _ausente_alias(txt)):
                key = "leucocitospiocitos"
                print(f"  EAS: 'Leucócitos' numérico={txt} -> Leucócitos (Piócitos) (sedimento)")
            else:
                key = "leucocitos"  # dipstick
        else:
            key = EAS_SED_ALIAS.get(key, key)
        raw[key] = txt
    # normaliza cada par presente
    out = dict(raw)
    for simple_s, x1000_s, label in EAS_SED_PAIRS:
        if simple_s not in by or x1000_s not in by:
            continue
        if simple_s not in raw and x1000_s not in raw:
            continue
        try:
            simp, x1k, per_ml = _eas_pair_values(raw.get(simple_s), raw.get(x1000_s))
        except Exception as e:
            print(f"  EAS: par {label} inválido ({e}) - mantido como veio")
            continue
        # grava com o nmExame real p/ achar_sub casar 1:1
        out[by[simple_s]["nmExame"]] = num_txt(simp)
        out[by[x1000_s]["nmExame"]] = num_txt(x1k)
        out.pop(simple_s, None)
        out.pop(x1000_s, None)
        print(f"  EAS: {label}: {num_txt(simp)} | x1000: {num_txt(x1k)} (={per_ml}/mL ≈ {per_ml/1000:g}.000/mL)")
    # dipstick Leucócitos: se ficou como slug, troca p/ nmExame
    if "leucocitos" in out and "leucocitos" in by:
        out[by["leucocitos"]["nmExame"]] = out.pop("leucocitos")
    return out


def eas_print_readback(vo):
    """Imprime os pares de sedimento de forma legível p/ a IA se autocriticar."""
    if not _is_eas_vo(vo):
        return
    by = _eas_sub_by_slug(vo)
    for simple_s, x1000_s, label in EAS_SED_PAIRS:
        a, b = by.get(simple_s), by.get(x1000_s)
        if not a or not b:
            continue
        va, vb = sub_val(a), sub_val(b)
        if va is None and vb is None:
            continue
        try:
            per_ml = int(round(float(vb))) if vb is not None else int(round(float(va) * 1000))
        except Exception:
            per_ml = vb
        # 21000 -> 21.000/mL
        per_txt = f"{per_ml:,}".replace(",", ".") + "/mL" if isinstance(per_ml, int) else f"{per_ml}/mL"
        print(f"  {label}: {vtxt(va) if va is not None else '-'} | x1000: {vtxt(vb) if vb is not None else '-'} (={per_txt})")


def exame_campos(vo, campos):
    """campos: {nome_ou_None: txt}. Retorna {nrSeqExame: (nome, float, dec, sub)} ou str de erro."""
    subs = {x["nrSeqExame"]: x for x in vo["subExams"]}
    out = {}
    for nome, txt in campos.items():
        if nome is None:
            s = main_sub(vo)
            if not s or s.get("ieFormatoResultado") not in ("V", "DV", "S"):
                return f"formato {s and s.get('ieFormatoResultado')} do campo principal; use EXAME.campo=valor (campos: " + \
                    "; ".join(f"{x['nmExame']} [{x.get('ieFormatoResultado')}]" for x in vo["subExams"]) + ")"
        else:
            s = achar_sub(vo, nome)
            if s is None:
                return f"campo '{nome}' desconhecido (campos: " + "; ".join(f"{x['nmExame']} [{x.get('ieFormatoResultado')}]" for x in vo["subExams"]) + \
                    f"; apelidos: {', '.join(FIELD_ALIAS)})"
        r = valor_campo(s, txt)
        if isinstance(r, str): return r
        out[s["nrSeqExame"]] = (nome or s.get("nmExame"), r[0], r[1], s)
    return out



def _is_hiv_rapido_vo(vo):
    """Teste Rápido HIV 1/2: tem os subcampos Teste Rápido 1 e Teste Rápido 2."""
    slugs = {_slug(x.get("nmExame")) for x in vo.get("subExams") or []}
    return "testerapido1" in slugs and "testerapido2" in slugs


def _hiv_eh_nao_reagente(txt):
    if txt is None:
        return False
    s = _slug(txt)
    return s in ("naoreagente", "naoreagente", "nr", "nao", "negativo", "negativa", "neg") or s.startswith("naoreagente")


def _hiv_campo_key(campos, sub):
    """Acha a chave em campos que aponta para este subexame (nome livre ou slug)."""
    alvo = _slug(sub.get("nmExame"))
    for k in list(campos.keys()):
        if k is None:
            continue
        if _slug(k) == alvo or alvo in _slug(k) or _slug(k) in alvo:
            return k
    return None


def completar_hiv(it, vo, campos):
    """Teste Rápido HIV: se TR1 = NÃO REAGENTE, TR2 fica NÃO REALIZADO (mesmo que mandem NR).
    Se TR2 for omitido nesse caso, também preenche NÃO REALIZADO. Aviso claro na troca.
    Não altera quando TR1 é REAGENTE."""
    if not _is_hiv_rapido_vo(vo):
        return campos
    # só no exame HIV (teste rápido), nunca na sorologia HIV1/2
    cd = str((it or {}).get("CD_EXAME") or "").upper()
    nm = str((it or {}).get("NM_EXAME") or "")
    if exame_externo_bloqueado(it or {"CD_EXAME": cd, "NM_EXAME": nm}):
        return campos
    if "sorologia" in _sem_acento(nm).lower():
        return campos
    by = {_slug(x.get("nmExame")): x for x in vo["subExams"]}
    tr1, tr2 = by.get("testerapido1"), by.get("testerapido2")
    if not tr1 or not tr2:
        return campos
    out = dict(campos)
    k1 = _hiv_campo_key(out, tr1)
    k2 = _hiv_campo_key(out, tr2)
    # valor efetivo do TR1: o que vai ser gravado, ou o já salvo
    if k1 is not None:
        v1 = out[k1]
    else:
        v1 = sub_val(tr1)
    if not _hiv_eh_nao_reagente(v1):
        return out  # TR1 reagente ou vazio: não mexe no TR2
    alvo_tr2 = "NÃO REALIZADO"
    # garante chave legível
    key2 = k2 if k2 is not None else tr2.get("nmExame")
    atual2 = out.get(key2) if key2 in out else (out.get(k2) if k2 else None)
    if atual2 is None and k2 is None:
        # omitido: preencher
        out[key2] = alvo_tr2
        print(f"  HIV: Teste Rápido 1 = NÃO REAGENTE → Teste Rápido 2 omitido; "
              f"gravando '{alvo_tr2}' (TR2 só se faz se TR1 for REAGENTE)")
    else:
        # veio valor: só troca se não for já NÃO REALIZADO
        bruto = atual2 if atual2 is not None else out.get(k2)
        if _slug(bruto) != _slug(alvo_tr2):
            print(f"  HIV: Teste Rápido 1 = NÃO REAGENTE → Teste Rápido 2 "
                  f"'{bruto}' trocado por '{alvo_tr2}' "
                  f"(TR2 só se realiza quando TR1 é REAGENTE)")
            out[key2] = alvo_tr2
            if k2 is not None and k2 != key2:
                out.pop(k2, None)
        else:
            out[key2] = alvo_tr2
    return out


# exames de vários campos: nrSeqExame do exame -> {campo: nrSeqExame do subexame}
MULTI = {575: {"total": 36503, "direta": 36504, "indireta": 36505}}   # Bilirrubina Total e Frações


def completar_bili(campos):
    if "total" in campos and "direta" in campos and "indireta" not in campos:
        t, dt, _ = parse_val(campos["total"]); d, dd, _ = parse_val(campos["direta"])
        campos["indireta"] = f"{t - d:.{max(dt, dd)}f}"
        print(f"  BILI: indireta calculada = total - direta = {campos['indireta']}")
    return campos


def parse_nasc(x):
    """Data de nascimento (date local TZ) a partir do Instant do nó/VO."""
    if isinstance(x, dict):
        v = x.get("value", x.get("dados"))
    else:
        v = x
    if not v:
        return None
    s = str(v).replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(s).astimezone(TZ).date()
    except ValueError:
        return None


def idade_anos(nasc):
    if not nasc:
        return None
    today = dt.datetime.now(TZ).date()
    return today.year - nasc.year - ((today.month, today.day) < (nasc.month, nasc.day))


def achar_campo_idade_crea(vo):
    """Campo de idade do layout CREA (ex.: 'Idade (Sexo Feminino > 18 anos)')."""
    hits = [x for x in vo["subExams"]
            if _slug(x.get("nmExame", "")).startswith("idade")
            and x.get("ieFormatoResultado") in ("V", "DV")]
    return hits[0] if hits else None


def achar_campo_etfg(vo):
    hits = [x for x in vo["subExams"]
            if "etfg" in _slug(x.get("nmExame", ""))
            or "taxadefiltracaoglomerular" in _slug(x.get("nmExame", ""))]
    return hits[0] if hits else None


def etfg_mdrd(crea, idade, sexo):
    """MDRD original (186). Ex.: CREA=2,71 idade=77 sexo F -> 18,1."""
    if crea is None or idade is None or crea <= 0 or idade <= 0:
        return None
    g = 186.0 * (float(crea) ** -1.154) * (float(idade) ** -0.203)
    if str(sexo or "").upper().startswith("F"):
        g *= 0.742
    return round(g + 1e-12, 1)


def completar_crea(it, vo, campos, node):
    """CREA: se o layout tem campo de idade e o paciente tem > 12 anos, preenche a idade
    (a eTFG com ieCampoCalculo=A é recalculada; o CLI também envia o MDRD, como no hemo).
    Se o usuário já passou idade ou eTFG, respeita."""
    if str(it.get("CD_EXAME", "")).upper() != "CREA":
        return campos
    idade_sub = achar_campo_idade_crea(vo)
    if not idade_sub:
        return campos
    nasc = parse_nasc((node or {}).get("DT_NASCIMENTO")) or parse_nasc(vo.get("dtNascimento"))
    anos = idade_anos(nasc)
    if anos is None or anos <= 12:
        return campos
    campos = dict(campos)
    def _user_passou(sub):
        for nome in campos:
            if nome is None:
                continue
            s = achar_sub(vo, nome)
            if s and s["nrSeqExame"] == sub["nrSeqExame"]:
                return True
        return False
    if not _user_passou(idade_sub):
        campos["idade"] = str(int(anos))
        print(f"  CREA: idade preenchida automaticamente = {int(anos)}"
              + (f" (nasc. {nasc.strftime('%d/%m/%Y')})" if nasc else ""))
    etfg_sub = achar_campo_etfg(vo)
    if etfg_sub and etfg_sub.get("ieCampoCalculo") == "A" and not _user_passou(etfg_sub):
        # creatinina: valor que vamos gravar (campo principal) ou o já salvo
        if None in campos:
            try:
                crea_val = parse_val(campos[None])[0]
            except Exception:
                crea_val = None
        else:
            crea_val = sub_val(main_sub(vo) or {})
        try:
            idade_val = parse_val(campos["idade"])[0] if "idade" in campos else float(anos)
        except Exception:
            idade_val = float(anos)
        sexo = vo.get("sexo") or (node or {}).get("IE_SEXO")
        etfg = etfg_mdrd(crea_val, idade_val, sexo)
        if etfg is not None:
            dec = etfg_sub.get("qtDecimais") or 1
            campos["etfg"] = f"{etfg:.{dec}f}"
            print(f"  CREA: eTFG calculada (MDRD) = {campos['etfg']}")
    return campos


def achar_item_digitacao(telas, chave):
    """Prefere o item em Digitação (30) quando há a mesma sigla em várias prescrições."""
    hits = []
    for t in telas:
        for it in t.items:
            if str(it.get("CD_EXAME", "")).upper() == str(chave).upper() or str(it.get("NR_SEQ_EXAME")) == str(chave):
                hits.append((t, it))
    if not hits:
        return None
    dig = [h for h in hits if h[1].get("IE_STATUS_ATEND") == 30]
    return (dig or hits)[0]


def lancar(z, atend, pedidos, dry, forcar, telas=None, dump=None):
    """pedidos: lista de (chave, campo_ou_None, texto_valor). Só lança no que existir em Digitação."""
    if telas is None:
        data, telas = abrir_telas(z, atend, write=not dry)
    grupos = {}
    for chave, campo, txt in pedidos:
        hit = achar_item_digitacao(telas, chave)
        if not hit:
            print(f"  {chave}: não existe em Digitação neste atendimento - ignorado"); continue
        g = grupos.setdefault(id(hit[1]), [chave, hit[0], hit[1], {}])
        g[3][campo] = txt
    rel = []; dumps = []
    for chave, t, it, campos in grupos.values():
        seq, nse = it["NR_SEQ_PRESCR"], it["NR_SEQ_EXAME"]
        tag = f"{it['CD_EXAME']} (prescr {t.nr} seq {seq})"
        if exame_externo_bloqueado(it):
            print(f"  {msg_bloqueio_externo(it)}")
            rel.append((tag, "bloqueado externo")); continue
        if it.get("IE_STATUS_ATEND") != 30 or seq not in t.nodes:
            print(f"  {tag}: status {it.get('IE_STATUS_ATEND')} - não está em Digitação, ignorado"); continue
        if nse in MULTI and 575 == nse: campos = completar_bili(campos)
        vo = t.clicar(seq, nse)["ResultVO"]
        node = t.nodes[seq][1] if seq in t.nodes else {}
        campos = completar_crea(it, vo, campos, node)
        campos = completar_eas(vo, campos)
        campos = completar_hiv(it, vo, campos)
        cs = exame_campos(vo, campos)
        if isinstance(cs, str):
            print(f"  {tag}: {cs} - não lançado"); rel.append((tag, "não suportado")); continue
        bad = [n for sq, (n, f, dec, s) in cs.items() if s.get("ieFormatoResultado") == "V" and not isinstance(f, str) and dec > (s.get("qtDecimais") or 0)]
        if bad:   # V: a tela respeita qtDecimais; DV aceita casas além de qtDecimais (TGO qd=0 gravou 20,7 pela tela)
            print(f"  {tag}: casas decimais demais para {bad} - não lançado"); rel.append((tag, "casas decimais")); continue
        conf = [(n, sub_val(s), f) for sq, (n, f, dec, s) in cs.items() if sub_val(s) not in (None, 0) and vdiff(sub_val(s), f)]
        if conf and not forcar:
            print(f"  {tag}: já tem valor diferente salvo ({'; '.join(f'{n}: {vtxt(o)} ≠ {vtxt(f)}' for n, o, f in conf)}) - não sobrescrevi (use --forcar)")
            rel.append((tag, "já tinha valor")); continue
        fora = [n for sq, (n, f, dec, s) in cs.items() if s.get("visible") is False and s.get("lineNumber") is None]
        if fora:   # ex.: TAP (formato 2524): campo principal fora do layout -> o save devolve saved=True mas grava 0
            print(f"  {tag}: AVISO: {', '.join(fora)} não está no formato de digitação da tela (visible=False, sem linha); "
                  "o servidor costuma ignorar esse campo - confira a releitura")
        env = {sq: f for sq, (n, f, dec, s) in cs.items()}
        novo = ds_payload(vo, env)
        dumps.append({"exame": it["CD_EXAME"], "payload": [H(novo)]})
        desc = ", ".join(f"{n}={vtxt(f)}" + (f" (atual {vtxt(sub_val(s))})" if sub_val(s) not in (None, 0) else "") for sq, (n, f, dec, s) in cs.items())
        if dry:
            print(f"  [dry-run] {tag}: {it['NM_EXAME'].strip()}: {desc}  -> POST WResultEntry/save (não enviado)")
            if _is_eas_vo(vo):
                # simula o que ficaria nos pares a partir do env
                sim = copy.deepcopy(vo)
                for x in sim["subExams"]:
                    if x["nrSeqExame"] in env:
                        if is_num(x):
                            x["qtResultado"] = env[x["nrSeqExame"]]
                        else:
                            x["dsResultado"] = env[x["nrSeqExame"]]
                eas_print_readback(sim)
            rel.append((tag, "dry-run")); continue
        r, cons, b = t.salvar(novo, seq, nse)
        avisos = [f"{x.get('nmExame')}: {x.get('dsResultado')} fora de {x.get('dsMinima')}-{x.get('dsMaxima')}" for x in (r or {}).get("referenceValueRecords", [])]
        if not (r or {}).get("saved"):
            print(f"  {tag}: save retornou saved={r and r.get('saved')} - VERIFICAR"); rel.append((tag, "falhou")); continue
        if (cons or {}).get("DS_CONSISTENCIA_P"):
            print(f"  {tag}: consistência: {cons['DS_CONSISTENCIA_P']}")
        lidos = {x["nrSeqExame"]: sub_val(x) for x in b["ResultVO"]["subExams"]}
        erros = [(cs[sq][0], lidos.get(sq), f) for sq, f in env.items() if lidos.get(sq) is None or vdiff(lidos[sq], f)]
        st = "ok" if not erros else "DIVERGÊNCIA: " + "; ".join(f"{n} lido {o} esperado {f}" for n, o, f in erros)
        print(f"  {tag}: salvo {desc} | releitura {st}" + (f" | aviso referência: {'; '.join(avisos)}" if avisos else ""))
        if _is_eas_vo(b["ResultVO"]):
            eas_print_readback(b["ResultVO"])
        rel.append((tag, st))
    if dump:
        json.dump(dumps, open(dump, "w"), ensure_ascii=False, indent=1); print(f"  payloads salvos em {dump}")
    return rel


def cmd_resultado(z, atend, exames, dry, forcar, dump=None):
    pedidos = []
    for e in exames:
        if "=" not in e: sys.exit(f"--exame espera CODIGO=valor ou CODIGO.campo=valor (recebi {e!r})")
        k, v = e.split("=", 1); k = k.strip()
        campo = None
        if "." in k: k, campo = k.split(".", 1); campo = campo.strip().lower()
        pedidos.append((k.strip(), campo, v.strip()))
    lancar(z, atend, pedidos, dry, forcar, dump=dump)


def gaso_sub(vo, opt):
    for x in vo["subExams"]:
        if x["nrSeqExame"] == vo["exam"]["nrSeqExame"]: continue
        if _slug(x.get("nmExame")) in GASO_SLUGS[opt]: return x
    return None


def gaso_num(v):
    if v in (None, ""): return None
    try: return float(str(v).replace(",", "."))
    except ValueError: return str(v)


def gaso_payload(vo, env):
    """Reproduz o save da tela (HAR 800654 GASV): DV preenchido -> qtResultado texto ("7.458") e
    dsResultado None; D -> qtResultado None e dsResultado texto com vírgula ("5,13"); DL (obs) texto.
    Campos não informados ficam como vieram do build (DV já preenchido vai em texto)."""
    novo = norm_inst(copy.deepcopy(vo))
    for x in novo["subExams"]:
        sq, fmt = x["nrSeqExame"], x.get("ieFormatoResultado")
        if sq in env:
            v = env[sq]
            if fmt in ("V", "DV"): x["qtResultado"], x["dsResultado"] = num_txt(v[0]), None
            elif fmt == "DL": x["qtResultado"], x["dsResultado"] = None, v
            else: x["qtResultado"], x["dsResultado"] = None, v[1].replace(".", ",")
        elif fmt in ("V", "DV") and x.get("qtResultado") not in (None, ""):
            x["qtResultado"], x["dsResultado"] = num_txt(x["qtResultado"]), None
        elif fmt not in ("V", "DV"):
            x["qtResultado"] = None
            if x.get("dsResultado") is None: x["dsResultado"] = ""
    return novo


def gaso_lancar(t, it, vals, obs, dry, forcar, dump=None):
    seq, nse = it["NR_SEQ_PRESCR"], it["NR_SEQ_EXAME"]
    tag = f"{it['CD_EXAME']} (prescr {t.nr} seq {seq})"
    if exame_externo_bloqueado(it):
        print(f"  {msg_bloqueio_externo(it)}"); return
    if it.get("IE_STATUS_ATEND") != 30 or seq not in t.nodes:
        print(f"  {tag}: status {it.get('IE_STATUS_ATEND')} - não está em Digitação, ignorado"); return
    vo = t.clicar(seq, nse)["ResultVO"]
    env, nomes, falt = {}, {}, []
    for opt, txt in vals.items():
        x = gaso_sub(vo, opt)
        if not x: falt.append(opt); continue
        try: f, dec, tt = parse_val(txt)
        except ValueError: print(f"  {tag}: '{txt}' não é número ({opt}) - abortado"); return
        env[x["nrSeqExame"]] = (f, tt); nomes[x["nrSeqExame"]] = x["nmExame"]
    if obs is not None:
        x = next((x for x in vo["subExams"] if "observacao" in _slug(x.get("nmExame"))), None)
        if x: env[x["nrSeqExame"]] = obs; nomes[x["nrSeqExame"]] = "Observação"
        else: falt.append("obs")
    if falt: print(f"  {tag}: campos sem correspondente na tela: {', '.join(falt)} - ignorados")
    subs = {x["nrSeqExame"]: x for x in vo["subExams"]}
    def alvo(sq): v = env[sq]; return v if isinstance(v, str) else v[0]
    conf = [(nomes[sq], gaso_num(sub_val(subs[sq])), alvo(sq)) for sq in env
            if gaso_num(sub_val(subs[sq])) not in (None, 0) and vdiff(gaso_num(sub_val(subs[sq])), alvo(sq))]
    if conf and not forcar:
        print(f"  {tag}: já tem valor diferente salvo ({'; '.join(f'{n}: {vtxt(o)} ≠ {vtxt(f)}' for n, o, f in conf)}) - não sobrescrevi (use --forcar)")
        return
    novo = gaso_payload(vo, env)
    if dump:
        json.dump([H(novo)], open(dump, "w"), ensure_ascii=False, indent=1); print(f"  payload salvo em {dump}")
    for sq in env:
        o = gaso_num(sub_val(subs[sq]))
        print(f"     {nomes[sq]:<12} {('-' if o in (None, '') else vtxt(o)):>8} -> {vtxt(alvo(sq))}  [{subs[sq].get('ieFormatoResultado')}]")
    if dry:
        print(f"  [dry-run] {tag}: {it['NM_EXAME'].strip()}: nada gravado"); return
    r, cons, b = t.salvar(novo, seq, nse)
    if not (r or {}).get("saved"):
        print(f"  {tag}: save retornou saved={r and r.get('saved')} - VERIFICAR"); return
    if (cons or {}).get("DS_CONSISTENCIA_P"): print(f"  {tag}: consistência: {cons['DS_CONSISTENCIA_P']}")
    avisos = [f"{x.get('nmExame')}: {x.get('dsResultado')}" for x in (r or {}).get("referenceValueRecords", [])]
    lid = {x["nrSeqExame"]: gaso_num(sub_val(x)) for x in b["ResultVO"]["subExams"]}
    erros = [(nomes[sq], lid.get(sq), alvo(sq)) for sq in env if lid.get(sq) is None or vdiff(lid[sq], alvo(sq))]
    print(f"  {tag}: salvo (status {b['ResultVO'].get('ieStatusAtend')}); releitura " +
          ("ok em todos os campos" if not erros else "DIVERGÊNCIA: " + "; ".join(f"{n} lido {o} esperado {f}" for n, o, f in erros)))
    if avisos: print("     avisos de referência: " + "; ".join(avisos))


def cmd_gaso(z, atend, a, dry, forcar, dump=None):
    vals = {opt: getattr(a, opt) for _, opt, _ in GASO_FIELDS if getattr(a, opt) is not None}
    if not vals and a.obs is None: sys.exit("informe ao menos um analito")
    data, prs = prescricoes(z, atend)
    telas = [t for t in (Resultado(z, atend, nr, write=not dry).abrir() for nr in prs) if t.items]
    gasos = [(t, it) for t in telas for it in t.items if str(it.get("CD_EXAME", "")).upper().startswith(GASO_SIGLAS) or "GASOM" in str(it.get("NM_EXAME", "")).upper()]
    if gasos:
        for t, it in gasos:
            print(f"Gasometria: {it['CD_EXAME']} {it['NM_EXAME'].strip()} (prescr {t.nr} seq {it['NR_SEQ_PRESCR']})")
            gaso_lancar(t, it, vals, a.obs, dry, forcar, dump)
    else:
        print("Gasometria: nenhuma em Digitação neste atendimento.")
    siglas = {it["CD_EXAME"].upper() for t in telas for it in t.items}
    pedidos = []
    for label, opt, eq in GASO_FIELDS:
        if opt in vals:
            s = next((e for e in eq if e in siglas), None)
            if s: pedidos.append((s, None, vals[opt]))
    if not pedidos:
        print("Bioquímica: nenhum exame equivalente em Digitação."); return
    print("Bioquímica equivalente: " + ", ".join(f"{k}={v}" for k, _, v in pedidos))
    lancar(z, atend, pedidos, dry, forcar, telas)


# ---------------- Hemograma Completo (HC, 202020380) ----------------
# Descobertas no HAR do 803328: a tela envia TODOS os subexames V/DV com qtResultado em texto
# ("3.88", "0") e dsResultado=None. Plaquetas (1076, DV) é enviada em 10^9/L ("409") e o servidor
# grava x1000 (409000); reenviar 409000 grava 409000000. Leucócitos Totais e absolutos são
# recalculados pelo servidor (ieCampoCalculo=A), mas a tela também os envia; o CLI envia calculados.
HEMO_SIGLA = "HC"
HEMO_DIRETOS = [("rbc", 536, "Hemácias"), ("hgb", 1473, "Hemoglobina"), ("hct", 1472, "Hematócrito"),
                ("vcm", 540, "VCM"), ("hcm", 541, "HCM"), ("chcm", 542, "CHCM"), ("rdw", 539, "RDW"),
                ("wbc", 1489, "Leucócitos"), ("vpm", 36966, "VPM")]
HEMO_DIF = [("bast", 36601, 545, "Bastonetes"), ("neu", 1480, 546, "Segmentados"), ("lym", 36603, 549, "Linfócitos"), ("mon", 1487, 550, "Monócitos"),
            ("eos", 36602, 547, "Eosinófilos"), ("bas", 36607, 548, "Basófilos")]
HEMO_TOT, HEMO_PCT_TOT, HEMO_PLT = 36513, 36623, 1076
HEMO_FATOR_SRV = {HEMO_PLT: 1000}   # gravado = enviado * fator


def half_up(x):
    import decimal
    return int(decimal.Decimal(str(x)).quantize(decimal.Decimal("1"), rounding=decimal.ROUND_HALF_UP))


def hemo_percentuais(v, wbc_total=0):
    p = {k: half_up(float(str(v.get(k) or 0).replace(",", "."))) for k, *_ in HEMO_DIF}
    while sum(p.values()) > 100:
        if p["bas"] > 0: p["bas"] -= 1
        else:
            k = min((k for k in p if p[k] > 0), key=lambda k: p[k]); p[k] -= 1
    while sum(p.values()) < 100:
        k = max(p, key=lambda k: p[k]); p[k] += 1
    # Regra obrigatória do laboratório: Eosinófilos >= 1 sempre; se Leucócitos Totais > 10.000,
    # também Bastonetes >= 1. Os pontos acrescentados saem do maior percentual (total fica 100).
    minimos = {"eos": 1}
    if wbc_total > 10000: minimos["bast"] = 1
    for k, m in minimos.items():
        if p[k] < m:
            add = m - p[k]; p[k] = m
            maior = max((x for x in p if x not in minimos), key=lambda x: p[x])
            p[maior] -= add
            print(f"Regra mínima: {k} ajustado para {m}; {maior} reduzido em {add} (agora {p[maior]})")
    return p


def num_txt(x):
    f = float(x)
    return str(int(f)) if f == int(f) else repr(round(f, 6))


def hemo_alvo(a):
    """{nrSeqExame: valor numérico a ENVIAR}; e {nrSeqExame: valor esperado na releitura}."""
    env = {}
    for opt, seq, _ in HEMO_DIRETOS:
        env[seq] = parse_val(getattr(a, opt))[0]
    wbc = env[1489]; tot = half_up(wbc * 1000); env[HEMO_TOT] = tot
    p = hemo_percentuais({k: getattr(a, k, 0) for k, *_ in HEMO_DIF}, tot)
    for k, sp, sa, _ in HEMO_DIF:
        env[sp] = p[k]; env[sa] = half_up(p[k] / 100 * tot)
    env[HEMO_PCT_TOT] = sum(p.values())
    env[HEMO_PLT] = parse_val(a.plt)[0]
    esp = {s: v * HEMO_FATOR_SRV.get(s, 1) for s, v in env.items()}
    return env, esp, p


def hemo_nomes():
    n = {seq: nm for _, seq, nm in HEMO_DIRETOS}
    for _, sp, sa, nm in HEMO_DIF: n[sp] = nm + " %"; n[sa] = nm + " abs"
    n.update({HEMO_TOT: "Leucócitos Totais", HEMO_PCT_TOT: "Total %", HEMO_PLT: "Plaquetas"})
    return n


def hemo_lidos(vo):
    out = {}
    for s in vo["subExams"]:
        if s.get("ieFormatoResultado") in ("V", "DV"):
            q = s.get("qtResultado")
            out[s["nrSeqExame"]] = None if q in (None, "") else float(q)
    return out


def hemo_payload(vo, env):
    novo = norm_inst(copy.deepcopy(vo))
    for s in novo["subExams"]:
        if s.get("ieFormatoResultado") not in ("V", "DV"): continue
        seq = s["nrSeqExame"]
        if seq in env: v = env[seq]
        else:
            q = s.get("qtResultado")
            v = None if q in (None, "") else float(q) / HEMO_FATOR_SRV.get(seq, 1)
        s["qtResultado"] = None if v is None else num_txt(v)
        s["dsResultado"] = None
    return novo


def cmd_ler_hemo(t, it, vo):
    nomes = hemo_nomes(); lid = hemo_lidos(vo)
    print(f"  Hemograma ({it['CD_EXAME']} seq {it['NR_SEQ_PRESCR']}, status {vo.get('ieStatusAtend')}):")
    for seq, nm in nomes.items():
        v = lid.get(seq)
        print(f"     {nm:<20} [{seq}] = {'-' if v in (None, 0) else num_txt(v).replace('.', ',')}")


def cmd_hemo(z, atend, a, dry, forcar, dump=None):
    env, esp, p = hemo_alvo(a)
    nomes = hemo_nomes()
    print("Percentuais: " + ", ".join(f"{k}={p[k]}" for k in p) + f" (soma {sum(p.values())})")
    data, telas = abrir_telas(z, atend, write=not dry)
    hit = [(t, it) for t in telas for it in t.items if str(it.get("CD_EXAME", "")).upper() == HEMO_SIGLA]
    if not hit: print("Hemograma Completo: não está em Digitação neste atendimento."); return
    for t, it in hit:
        seq, nse = it["NR_SEQ_PRESCR"], it["NR_SEQ_EXAME"]
        tag = f"HC (prescr {t.nr} seq {seq})"
        if exame_externo_bloqueado(it):
            print(f"  {msg_bloqueio_externo(it)}"); continue
        if it.get("IE_STATUS_ATEND") != 30 or seq not in t.nodes:
            print(f"  {tag}: status {it.get('IE_STATUS_ATEND')} - não está em Digitação, ignorado"); continue
        vo = t.clicar(seq, nse)["ResultVO"]
        lid = hemo_lidos(vo)
        falta = [s for s in env if s not in lid]
        if falta: print(f"  {tag}: campos ausentes na tela {falta} - abortado"); continue
        dif = [(s, lid[s], esp[s]) for s in esp if lid[s] not in (None, 0) and abs(lid[s] - esp[s]) > 1e-9]
        if dif and not forcar:
            print(f"  {tag}: já tem valores diferentes salvos - não sobrescrevi (use --forcar):")
            for s, o, n in dif: print(f"     {nomes[s]}: salvo {num_txt(o)} -> novo {num_txt(n)}")
            continue
        novo = hemo_payload(vo, env)
        if dump:
            json.dump([H(novo)], open(dump, "w"), ensure_ascii=False, indent=1); print(f"  payload salvo em {dump}")
        for s in env:
            print(f"     {nomes[s]:<20} {('-' if lid[s] in (None, 0) else num_txt(lid[s])):>10} -> envia {num_txt(env[s]):>8} (grava {num_txt(esp[s])})")
        if dry:
            print(f"  [dry-run] {tag}: nada gravado"); continue
        r, cons, b = t.salvar(novo, seq, nse)
        if not (r or {}).get("saved"):
            print(f"  {tag}: save retornou saved={r and r.get('saved')} - VERIFICAR"); continue
        if (cons or {}).get("DS_CONSISTENCIA_P"): print(f"  {tag}: consistência: {cons['DS_CONSISTENCIA_P']}")
        avisos = [f"{x.get('nmExame')}: {x.get('dsResultado')}" for x in (r or {}).get("referenceValueRecords", [])]
        rl = hemo_lidos(b["ResultVO"])
        erros = [(s, rl.get(s), esp[s]) for s in esp if rl.get(s) is None or abs(rl[s] - esp[s]) > 1e-9]
        print(f"  {tag}: salvo (status {b['ResultVO'].get('ieStatusAtend')}); releitura " +
              ("ok em todos os campos" if not erros else "DIVERGÊNCIA: " + "; ".join(f"{nomes[s]} lido {o} esperado {n}" for s, o, n in erros)))
        if avisos: print("     avisos de referência: " + "; ".join(avisos))


# ---------------- Conferir exames liberados (só leitura) ----------------
# Status 40 = Exame Liberado. Nunca salva, aprova nem altera nada.
# Tabelas PLAUS_* e CRITICO_* são editáveis (limites de referência do laboratório).

def parse_dt_arg(txt, fim_do_dia=False):
    """Aceita DD/MM/AAAA, DD/MM/AAAA HH:MM ou DD/MM/AAAA HH:MM:SS (fuso America/Sao_Paulo)."""
    t = (txt or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            d = dt.datetime.strptime(t, fmt)
            break
        except ValueError:
            d = None
    if d is None:
        raise ValueError(f"data inválida: {txt!r} (use DD/MM/AAAA[ HH:MM[:SS]])")
    if fmt == "%d/%m/%Y" and fim_do_dia:
        d = d.replace(hour=23, minute=59, second=59)
    return d.replace(tzinfo=TZ)


def instant_of(dtime):
    return {"@class": "java.time.Instant", "type": "INSTANT",
            "value": dtime.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}


def liberado_master_body(ini, fim, atend=None, page=1, rpp=200):
    """Réplica do filtro Exames Pendentes > Pós-analítica > Status = Exame Liberado."""
    b = copy.deepcopy(TPL["498026_master"])
    st = LIBERADO_STATUS
    ini_i, fim_i = instant_of(ini), instant_of(fim)
    p = b["parameters"]
    p["DT_INICIAL"], p["DT_FINAL"] = copy.deepcopy(ini_i), copy.deepcopy(fim_i)
    p["IE_RESULT_STAGES"] = st
    p["IE_STATUS_ATEND"] = st
    p["NR_ATENDIMENTO"] = atend
    if "filterValues" in b:
        fv = b["filterValues"]
        fv["DT_INICIAL"], fv["DT_FINAL"] = copy.deepcopy(ini_i), copy.deepcopy(fim_i)
        fv["IE_RESULT_STAGES"] = st
        fv["NR_ATENDIMENTO"] = atend
    b["page"], b["pageBegin"], b["recordsPerPage"] = page, page, rpp
    return b


def liberado_child_body(ini, fim, row, atend=None):
    b = copy.deepcopy(TPL["691864_child"])
    st = LIBERADO_STATUS
    ini_i, fim_i = instant_of(ini), instant_of(fim)
    p = b["parameters"]
    pf = p["PARENT_FILTER_PARAMS"]
    pf["DT_INICIAL"], pf["DT_FINAL"] = copy.deepcopy(ini_i), copy.deepcopy(fim_i)
    pf["IE_RESULT_STAGES"] = st
    pf["NR_ATENDIMENTO"] = atend
    p["IE_STATUS_ATEND"] = st
    p["DT_INICIAL"], p["DT_FINAL"] = copy.deepcopy(ini_i), copy.deepcopy(fim_i)
    p["PENDING_PRESCRIPTION_VALUES"] = {k: to_request_value(v) for k, v in row.items()}
    return b


def listar_liberados(z, ini, fim, atend=None, rpp=200):
    """Lista TODAS as amostras liberadas do período (pagina até esgotar qtTotalRegistros)."""
    rows, page, total = [], 1, None
    while True:
        body = liberado_master_body(ini, fim, atend=atend, page=page, rpp=rpp)
        raw = z.post("WCPanelDataProvider/getDataSource", [body]) or {}
        dados = raw.get("dados") or {}
        chunk = dados.get("linhasResultSet") or []
        if total is None:
            total = int(dados.get("qtTotalRegistros") or 0)
        rows.extend(chunk)
        if not chunk or len(rows) >= total:
            break
        page += 1
        if page > 200:
            raise RuntimeError(f"paginação liberados excedeu 200 páginas ({len(rows)}/{total})")
    return rows, total if total is not None else len(rows)


# --- Tabelas editáveis de plausibilidade e crítico ---
# Chave = slug do nmExame / CD_EXAME. Bounds: (min_plaus, max_plaus) — fora = possível digitação.
# Unidades usuais do lab HMMCC (Hb g/dL, PLT /mm³ gravado, WBC totais /mm³, K mmol/L, ...).
PLAUS_BOUNDS = {
    # hematologia
    "hemoglobina": (2.0, 25.0), "hgb": (2.0, 25.0), "hb": (2.0, 25.0),
    "hematocrito": (5.0, 75.0), "hct": (5.0, 75.0),
    "hemacias": (0.5, 9.0), "rbc": (0.5, 9.0),  # ×10^6/µL
    "vcm": (40.0, 150.0), "hcm": (10.0, 50.0), "chcm": (20.0, 45.0), "rdw": (5.0, 40.0), "vpm": (3.0, 20.0),
    "plaquetas": (1_000.0, 2_000_000.0), "plt": (1_000.0, 2_000_000.0),
    # "Leucócitos" do HC (10³/µL) vs "Leucócitos Totais" (/mm³) vs EAS piócitos (campo simples)
    "leucocitos": (0.1, 200.0), "wbc": (0.1, 200.0),
    "leucocitostotais": (100.0, 200_000.0),
    "leucocitospiocitos": (0.0, 500.0),  # campo simples do EAS
    "leucocitosx1000": (0.0, 500_000.0),
    "celulasepiteliais": (0.0, 500.0), "celulasepiteliaisx1000": (0.0, 500_000.0),
    "hemaciasx1000": (0.0, 500_000.0),
    "hemaciasedimento": (0.0, 500.0),  # EAS simples (evita bound de RBC sanguíneo)
    "phurina": (4.5, 9.0), "ph": (6.5, 8.0),  # ph urina sobrescrito no analisador se URN1
    # bioquímica
    "potassio": (1.0, 10.0), "k": (1.0, 10.0),
    "sodio": (90.0, 180.0), "na": (90.0, 180.0),
    "calcioionico": (0.3, 2.5), "cai": (0.3, 2.5), "caio": (0.3, 2.5),
    "glicose": (10.0, 800.0), "glicemia": (10.0, 800.0),
    "creatinina": (0.05, 30.0), "crea": (0.05, 30.0),
    "ureia": (2.0, 500.0), "urea": (2.0, 500.0),
    "bilirrubinatotal": (0.01, 40.0), "bilirrubinadireta": (0.0, 30.0), "bilirrubinaindireta": (0.0, 40.0),
    "tgo": (1.0, 5000.0), "tgp": (1.0, 5000.0), "ast": (1.0, 5000.0), "alt": (1.0, 5000.0),
    "pcr": (0.0, 500.0), "pcrp": (0.0, 500.0),
    "lactato": (0.1, 30.0), "lac": (0.1, 30.0),
    # gasometria
    "ph": (6.5, 8.0), "pco2": (5.0, 150.0), "po2": (10.0, 700.0),
    "hco3": (1.0, 60.0), "be": (-40.0, 40.0), "so2": (10.0, 100.0),
    # coagulação
    "rni": (0.5, 20.0), "inr": (0.5, 20.0), "tap": (5.0, 200.0), "tempo": (5.0, 200.0),
    "atividade": (1.0, 200.0), "ttpa": (5.0, 300.0),
    # outros
    "contagemdereticulocitos": (0.0, 50.0), "reticulocitos": (0.0, 50.0),
}

# Resultado crítico (plausível, mas pânico). (min_ok, max_ok) — fora = crítico.
# None em um lado = sem limite naquela ponta.
CRITICO_BOUNDS = {
    "hemoglobina": (7.0, None), "hgb": (7.0, None), "hb": (7.0, None),
    "plaquetas": (50_000.0, 1_000_000.0), "plt": (50_000.0, 1_000_000.0),
    "leucocitostotais": (2_000.0, 30_000.0),
    "leucocitos": (2.0, 30.0), "wbc": (2.0, 30.0),  # campo HC em 10³/µL
    "potassio": (2.8, 6.2), "k": (2.8, 6.2),
    "sodio": (120.0, 160.0), "na": (120.0, 160.0),
    "calcioionico": (0.8, 1.6), "cai": (0.8, 1.6), "caio": (0.8, 1.6),
    "glicose": (50.0, 400.0), "glicemia": (50.0, 400.0),
    "creatinina": (None, 5.0), "crea": (None, 5.0),  # adulto; RN tratado à parte
    "bilirrubinatotal": (None, 15.0),  # RN: >15 crítico
    "ph": (7.20, 7.60),
    "pco2": (20.0, 70.0),
    "lactato": (None, 4.0), "lac": (None, 4.0),
    "rni": (None, 4.0), "inr": (None, 4.0),
}

# Sorologias reagentes = crítico
SOROLOGIA_REAGENTE_SLUGS = (
    "hiv", "anti hiv", "trhiv", "sifilis", "vdrl", "fta", "hbsag", "antihbs", "hcv",
    "antihcv", "toxo", "toxoplasmose", "igm",
)


def _num_or_none(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return None


def _idade_anos(dt_nasc, agora=None):
    if not dt_nasc:
        return None
    if isinstance(dt_nasc, dict):
        val = dt_nasc.get("value") or ""
        try:
            nasc = dt.datetime.fromisoformat(val.replace("Z", "+00:00")).astimezone(TZ).date()
        except ValueError:
            return None
    elif isinstance(dt_nasc, str):
        try:
            nasc = dt.datetime.fromisoformat(dt_nasc.replace("Z", "+00:00")).astimezone(TZ).date()
        except ValueError:
            return None
    else:
        return None
    hoje = (agora or dt.datetime.now(TZ)).date()
    return (hoje - nasc).days / 365.25


def _is_rn(idade_anos, ds_idade=None, nome=None):
    if idade_anos is not None and idade_anos < 28 / 365.25:
        return True
    blob = " ".join(str(x or "") for x in (ds_idade, nome)).lower()
    return blob.startswith("rn ") or "rn de " in blob or "recem" in _slug(blob) or "recém" in blob


def _campo_keys(nm, cd=None, exame_cd=None):
    """Chaves de classificação a partir do nmExame (NÃO herdar bounds do CD do exame pai)."""
    keys = []
    if nm:
        keys.append(_slug(nm))
    alias_map = {
        "k+": "potassio", "na+": "sodio", "cai": "calcioionico", "caio": "calcioionico",
        "hgb": "hemoglobina", "hb": "hemoglobina", "hct": "hematocrito",
        "plt": "plaquetas", "wbc": "leucocitos", "crea": "creatinina", "urea": "ureia",
        "pcrp": "pcr", "lact": "lactato", "lac": "lactato",
        "inr": "rni", "ast": "tgo", "alt": "tgp",
    }
    out = []
    for k in keys:
        out.append(k)
        if k in alias_map:
            out.append(alias_map[k])
    s = keys[0] if keys else ""
    # matches específicos (ordem: mais específico primeiro)
    specific = [
        ("leucocitosx1000", ("leucocitosx1000", "piocitosx1000")),
        ("leucocitospiocitos", ("leucocitospiocitos", "piocitos")),
        ("leucocitostotais", ("leucocitostotais", "leucocitototal")),
        ("celulasepiteliaisx1000", ("celulasepiteliaisx1000",)),
        ("celulasepiteliais", ("celulasepiteliais",)),
        ("hemaciasx1000", ("hemaciasx1000",)),
        ("bilirrubinatotal", ("bilirrubinatotal",)),
        ("bilirrubinadireta", ("bilirrubinadireta",)),
        ("bilirrubinaindireta", ("bilirrubinaindireta",)),
        ("calcioionico", ("calcioionico", "calcioionizado")),
        ("contagemdereticulocitos", ("contagemdereticulocitos", "reticulocitos")),
        ("plaquetas", ("plaquetas", "plt")),
        ("hemoglobina", ("hemoglobina",)),
        ("hematocrito", ("hematocrito",)),
        ("creatinina", ("creatinina",)),
        ("potassio", ("potassio",)),
        ("sodio", ("sodio",)),
        ("glicose", ("glicose", "glicemia")),
        ("ureia", ("ureia",)),
        ("lactato", ("lactato",)),
        ("pco2", ("pco2",)),
        ("po2", ("po2",)),
        ("hco3", ("hco3",)),
        ("rni", ("rni", "inr")),
    ]
    for canon, needles in specific:
        if any(n == s or s.startswith(n) or n in s for n in needles):
            if canon not in out:
                out.append(canon)
    # Leucócitos "simples" do HC (não totais, não piócitos, não x1000)
    if "leucocito" in s and "totai" not in s and "total" not in s and "piocito" not in s and "x1000" not in s:
        if "leucocitos" not in out:
            out.append("leucocitos")
    # Hemácias: sangue (RBC) vs sedimento EAS
    if s == "hemacias" or (s.startswith("hemacias") and "x1000" not in s):
        # se o exame é EAS/URN1, tratar como sedimento
        ex = _slug(exame_cd or "")
        if ex in ("urn1", "eas", "urina") or "urina" in ex:
            out = [k for k in out if k not in ("hemacias", "rbc")]
            out.append("hemaciasedimento")
        else:
            if "hemacias" not in out:
                out.append("hemacias")
    # pH urinário
    if s == "ph" or s.startswith("ph"):
        ex = _slug(exame_cd or "")
        if ex in ("urn1", "eas") or "urina" in ex:
            out = [k for k in out if k != "ph"]
            out.append("phurina")
        elif "ph" not in out:
            out.append("ph")
    # não classificar idade / eTFG / observação como creatinina etc.
    if s.startswith("idade") or "etfg" in s or "filtracaoglomerular" in s or s.startswith("observ"):
        return [s]
    return out


def _lookup_bound(table, keys):
    for k in keys:
        if k in table:
            return table[k], k
    return None, None


def _provavel_escala(v, lo, hi):
    """Sugere valor ÷10/100/1000 se cair na faixa plausível."""
    if v is None:
        return None
    for f in (10, 100, 1000, 10000):
        c = v / f
        if (lo is None or c >= lo) and (hi is None or c <= hi):
            return c
    for f in (10, 100, 1000):
        c = v * f
        if (lo is None or c >= lo) and (hi is None or c <= hi):
            return c
    return None


def _fmt_val(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        if abs(v) >= 1000 and abs(v - round(v)) < 1e-9:
            return f"{int(round(v)):,}".replace(",", ".")
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return s.replace(".", ",")
    return str(v)


def _achado(tipo, paciente, atend, presc, exame, campo, valor, motivo, provavel=None, unidade=""):
    return {
        "tipo": tipo,
        "paciente": paciente or "",
        "atendimento": atend,
        "prescricao": presc,
        "exame": exame or "",
        "campo": campo or "",
        "valor": valor,
        "unidade": unidade or "",
        "motivo": motivo,
        "valor_provavel": provavel,
    }


def _analisar_vo(vo, meta, achados):
    """Classifica campos de um ResultVO. meta: paciente, atend, presc, exame, idade, is_rn."""
    paciente, atend, presc, exame = meta["paciente"], meta["atend"], meta["presc"], meta["exame"]
    idade, is_rn = meta.get("idade"), meta.get("is_rn")
    subs = list(vo.get("subExams") or [])
    by_slug = {_slug(x.get("nmExame")): x for x in subs}
    nums = {}  # slug -> float
    campos_lidos = 0

    for x in subs:
        campos_lidos += 1
        nm = (x.get("nmExame") or "").strip()
        if not nm or nm.lower().startswith("observ"):
            continue
        slug = _slug(nm)
        fmt = x.get("ieFormatoResultado")
        unidade = x.get("dsUnidadeMedida") or ""
        keys = _campo_keys(nm, exame_cd=meta.get("cd"))
        # ignora campos administrativos
        if slug.startswith("idade") or slug.startswith("observ"):
            nums[slug] = _num_or_none(x.get("qtResultado")) if fmt in ("V", "DV") else None
            continue

        if fmt in ("V", "DV"):
            v = _num_or_none(x.get("qtResultado"))
            nums[slug] = v
            if v is None:
                continue
            pr_min = _num_or_none(x.get("prMinimo") if x.get("prMinimo") is not None else x.get("qtMinima"))
            pr_max = _num_or_none(x.get("prMaximo") if x.get("prMaximo") is not None else x.get("qtMaxima"))

            is_plt = any(k in ("plaquetas", "plt") for k in keys)
            is_etfg = "etfg" in slug or "filtracaoglomerular" in slug
            # 1) heurística 10× referência (pula quando ref e valor estão em escalas diferentes, ex. PLT)
            skip_10x = is_plt or is_etfg or (pr_max is not None and pr_max < 1000 and v >= 1000)
            if not skip_10x and pr_max is not None and v > 10 * pr_max and pr_max > 0:
                prov = _provavel_escala(v, pr_min, pr_max)
                achados.append(_achado("digitacao", paciente, atend, presc, exame, nm, v,
                    f"valor {_fmt_val(v)} > 10× limite superior de referência ({_fmt_val(pr_max)})",
                    provavel=prov, unidade=unidade))
                continue
            if not skip_10x and pr_min is not None and pr_min > 0 and v < pr_min / 10:
                prov = _provavel_escala(v, pr_min, pr_max)
                achados.append(_achado("digitacao", paciente, atend, presc, exame, nm, v,
                    f"valor {_fmt_val(v)} < referência mínima/10 ({_fmt_val(pr_min)})",
                    provavel=prov, unidade=unidade))
                continue

            # 2) bounds de plausibilidade
            bound, bk = _lookup_bound(PLAUS_BOUNDS, keys)
            if bound:
                lo, hi = bound
                if (lo is not None and v < lo) or (hi is not None and v > hi):
                    prov = _provavel_escala(v, lo, hi)
                    achados.append(_achado("digitacao", paciente, atend, presc, exame, nm, v,
                        f"fora da faixa fisiológica plausível ({_fmt_val(lo)}–{_fmt_val(hi)}) para {bk}",
                        provavel=prov, unidade=unidade))
                    continue

            # 3) crítico (só se ainda plausível; nunca aplicar bound de crea em eTFG)
            crit, ck = _lookup_bound(CRITICO_BOUNDS, keys)
            if crit and not is_etfg:
                clo, chi = crit
                aplicar = True
                if ck in ("creatinina", "crea") and is_rn:
                    aplicar = False
                if aplicar:
                    abaixo = clo is not None and v < clo
                    acima = chi is not None and v > chi
                    if abaixo or acima:
                        lado = "abaixo" if abaixo else "acima"
                        lim = clo if abaixo else chi
                        achados.append(_achado("critico", paciente, atend, presc, exame, nm, v,
                            f"resultado crítico ({lado} de {_fmt_val(lim)})", unidade=unidade))
                        continue

            # WBC (10³/µL) digitado em escala absurda (milhões) — nunca aplicar a Leucócitos Totais
            if ("leucocitos" in keys or "wbc" in keys) and "leucocitostotais" not in keys                     and "piocito" not in slug and "x1000" not in slug and "totai" not in slug:
                if v > 200:
                    prov = _provavel_escala(v, 0.1, 200)
                    achados.append(_achado("digitacao", paciente, atend, presc, exame, nm, v,
                        "leucócitos em escala incompatível (esperado ~10³/µL)",
                        provavel=prov, unidade=unidade))

        else:
            # texto / lista
            ds = (x.get("dsResultado") or "").strip()
            # sorologia reagente
            if ds and _slug(ds) in ("reagente", "positivo", "reativo", "detectado", "reag"):
                if any(any(s.replace(" ", "") in k for s in SOROLOGIA_REAGENTE_SLUGS) for k in keys) \
                   or any(s.replace(" ", "") in slug for s in SOROLOGIA_REAGENTE_SLUGS):
                    achados.append(_achado("critico", paciente, atend, presc, exame, nm, ds,
                        "sorologia/teste reagente ou positivo"))

    # ---- inconsistências internas ----
    def g(*cands):
        for c in cands:
            if c in nums and nums[c] is not None:
                return nums[c]
        for s, v in nums.items():
            if v is None:
                continue
            # match exato ou slug que É o cand / começa com cand (não "crea" ⊆ "creativa")
            for c in cands:
                if s == c or s.startswith(c) or s.endswith(c):
                    # evita creatina⊆creativa: exige fronteira mínima
                    if c == "crea" and "creatinina" not in s and s != "crea":
                        continue
                    return v
        return None

    # leucograma %
    pct_keys = [s for s, v in nums.items() if v is not None and (
        s.endswith("pct") or s in ("bastonetes", "segmentados", "neutrofilos", "linfocitos",
                                   "monocitos", "eosinofilos", "basofilos") or
        (s.endswith("") and any(x in s for x in ("bastonete", "segmentado", "neutrofilo",
                                                  "linfocito", "monocito", "eosinofilo", "basofilo"))
         and "abs" not in s and "absolut" not in s and "total" not in s))]
    # Prefer explicit percentuais do HC
    pct_vals = []
    for s, v in nums.items():
        if v is None:
            continue
        if s in ("bastonetes", "segmentados", "linfocitos", "monocitos", "eosinofilos", "basofilos"):
            pct_vals.append((s, v))
        elif s.endswith("porcentagem") or (s.endswith("") and "percent" in s):
            pct_vals.append((s, v))
    # HC: percentuais tipicamente 0–100 e somam ~100; absolutos são milhares
    pct_only = [(s, v) for s, v in pct_vals if v <= 100]
    if len(pct_only) >= 4:
        soma = sum(v for _, v in pct_only)
        if abs(soma - 100) > 1.5:
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                "Leucograma %", soma,
                f"soma dos percentuais = {_fmt_val(soma)} (esperado ≈ 100)"))

    hb = g("hemoglobina", "hgb", "hb")
    ht = g("hematocrito", "hct")
    rbc = g("hemacias", "rbc")
    vcm = g("vcm")
    chcm = g("chcm")
    if hb is not None and ht is not None and hb > 0:
        # Ht ≈ 3 × Hb (em g/dL e %)
        esperado = 3 * hb
        if esperado > 0 and abs(ht - esperado) / max(esperado, 1) > 0.25:
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                "Ht vs Hb", f"Hb={_fmt_val(hb)} Ht={_fmt_val(ht)}",
                f"Ht diverge de 3×Hb em >25% (esperado ≈ {_fmt_val(esperado)})"))
        if ht > 0:
            chcm_calc = hb / ht * 100
            if chcm is not None and abs(chcm - chcm_calc) > 2.5:
                achados.append(_achado("digitacao", paciente, atend, presc, exame,
                    "CHCM", chcm,
                    f"CHCM informado {_fmt_val(chcm)} ≠ Hb/Ht×100 ({_fmt_val(chcm_calc)})"))
    if ht is not None and rbc is not None and rbc > 0 and vcm is not None:
        vcm_calc = ht / rbc * 10
        if abs(vcm - vcm_calc) > 8:
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                "VCM", vcm,
                f"VCM informado {_fmt_val(vcm)} ≠ Ht/RBC×10 ({_fmt_val(vcm_calc)})"))

    bt = g("bilirrubinatotal")
    bd = g("bilirrubinadireta")
    bi = g("bilirrubinaindireta")
    if bt is not None and bd is not None and bd > bt + 0.05:
        achados.append(_achado("digitacao", paciente, atend, presc, exame,
            "Bilirrubina Direta", bd,
            f"BD ({_fmt_val(bd)}) > BT ({_fmt_val(bt)})"))
    if bt is not None and bd is not None and bi is not None:
        if abs(bi - (bt - bd)) > 0.15:
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                "Bilirrubina Indireta", bi,
                f"BI ({_fmt_val(bi)}) ≠ BT−BD ({_fmt_val(bt - bd)})"))

    # pH sanguíneo (gasometria); urina tem faixa própria (phurina) e não entra aqui
    ex_cd = _slug(meta.get("cd") or "")
    if ex_cd not in ("urn1", "eas") and "urina" not in ex_cd and "urin" not in _slug(exame):
        ph = g("ph")
        if ph is not None and (ph < 6.8 or ph > 7.8):
            if not any(a["campo"] and _slug(a["campo"]) == "ph" and a["tipo"] == "digitacao"
                       and a["prescricao"] == presc and a["exame"] == exame for a in achados):
                achados.append(_achado("digitacao", paciente, atend, presc, exame,
                    "pH", ph, f"pH fora de 6,8–7,8 ({_fmt_val(ph)})"))

    # EAS sedimento pares
    for simple_s, x1000_s, label in EAS_SED_PAIRS:
        a, b = by_slug.get(simple_s), by_slug.get(x1000_s)
        if not a or not b:
            continue
        va, vb = _num_or_none(a.get("qtResultado")), _num_or_none(b.get("qtResultado"))
        if va is None and vb is None:
            continue
        if vb is not None and vb >= 1_000_000:
            prov = vb / 1000 if va is None else va
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                label + " (x1000)", vb,
                f"x1000 = {_fmt_val(vb)} (≥ 1.000.000) — provável escala errada (simples×1000 no campo x1000)",
                provavel=va * 1000 if va is not None else vb / 1000))
        elif va is not None and vb is not None:
            esperado = va * 1000
            if abs(vb - esperado) > max(1.0, 0.05 * esperado):
                achados.append(_achado("digitacao", paciente, atend, presc, exame,
                    label, f"{_fmt_val(va)} / x1000={_fmt_val(vb)}",
                    f"par inconsistente: x1000 deveria ser {_fmt_val(esperado)} (simples×1000)"))

    # TAP tempo 0 com AP%/RNI preenchidos
    tempo = None
    rni = g("rni", "inr")
    ativ = None
    for s, v in nums.items():
        if v is None:
            continue
        if "tempo" in s and ("tap" in s or "protrombina" in s or s == "tempo"):
            tempo = v
        if "atividade" in s or s in ("ap", "atividadeprotrombinica"):
            ativ = v
    if tempo is not None and tempo == 0 and (rni not in (None, 0) or ativ not in (None, 0)):
        achados.append(_achado("digitacao", paciente, atend, presc, exame,
            "Tempo TAP", tempo,
            f"tempo = 0 com RNI/atividade preenchidos (RNI={_fmt_val(rni)}, atividade={_fmt_val(ativ)})"))

    # Beta HCG conclusão vs valor
    hcg_val = None
    hcg_conc = None
    for x in subs:
        slug = _slug(x.get("nmExame"))
        if "betahcg" in slug or slug in ("hcg", "bhcg") or ("hcg" in slug and "obs" not in slug):
            if x.get("ieFormatoResultado") in ("V", "DV"):
                hcg_val = _num_or_none(x.get("qtResultado"))
            else:
                ds = (x.get("dsResultado") or "").strip()
                if ds:
                    hcg_conc = ds
        if "conclus" in slug or "interpret" in slug or "resultado" == slug:
            ds = (x.get("dsResultado") or "").strip()
            if ds and hcg_conc is None and ("hcg" in _slug(exame) or "hcg" in slug):
                hcg_conc = ds
    if hcg_val is not None and hcg_conc:
        reag = _slug(hcg_conc) in ("reagente", "positivo", "reativo")
        nreag = _slug(hcg_conc) in ("naoreagente", "negativo", "naoagente", "nr")
        if hcg_val > 25 and nreag:
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                "Beta HCG", f"{_fmt_val(hcg_val)} / {hcg_conc}",
                "valor > 25 com conclusão NÃO REAGENTE"))
        if hcg_val < 5 and reag:
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                "Beta HCG", f"{_fmt_val(hcg_val)} / {hcg_conc}",
                "valor < 5 com conclusão REAGENTE"))

    # eTFG vazia com creatinina e idade >12 (só no exame CREA)
    crea = None
    for s, v in nums.items():
        if v is None:
            continue
        if s == "creatinina" or s.startswith("creatinina") or s == "dosagemdecreatinina":
            crea = v
            break
    if crea is None:
        for x in subs:
            sx = _slug(x.get("nmExame"))
            if sx == "creatinina" or (sx.startswith("creatinina") and "etfg" not in sx and "idade" not in sx):
                crea = _num_or_none(x.get("qtResultado"))
                if crea is not None:
                    break
    etfg = None
    idade_campo = None
    for s, v in nums.items():
        if v is None:
            continue
        if "etfg" in s or "filtracaoglomerular" in s or "taxadefiltracao" in s:
            etfg = v
        if s.startswith("idade"):
            idade_campo = v
    for x in subs:
        sx = _slug(x.get("nmExame"))
        if "etfg" in sx or "filtracaoglomerular" in sx:
            if etfg is None:
                etfg = _num_or_none(x.get("qtResultado")) or _num_or_none(x.get("dsResultado"))
        if sx.startswith("idade") and idade_campo is None:
            idade_campo = _num_or_none(x.get("qtResultado")) or _num_or_none(x.get("dsResultado"))
    # só faz sentido no painel de creatinina
    exame_eh_crea = _slug(meta.get("cd") or "") in ("crea", "creatinina") or "creatinina" in _slug(exame)
    idade_ref = idade_campo if idade_campo is not None else idade
    if exame_eh_crea and crea not in (None, 0) and idade_ref is not None and idade_ref > 12:
        if etfg in (None, 0):
            achados.append(_achado("digitacao", paciente, atend, presc, exame,
                "eTFG", etfg if etfg is not None else "",
                f"eTFG vazia/0 com creatinina={_fmt_val(crea)} e idade={_fmt_val(idade_ref)} (>12 anos)"))

    return campos_lidos


def cmd_conferir(z, de=None, ate=None, atend=None, as_json=False):
    """Auditoria só-leitura de TODOS os exames liberados (status 40) do período."""
    agora = dt.datetime.now(TZ)
    if de:
        ini = parse_dt_arg(de, fim_do_dia=False)
        if " " not in de.strip():
            ini = ini.replace(hour=0, minute=0, second=0)
    else:
        ini = dt.datetime.combine(agora.date(), dt.time(0, 0, 0), TZ)
    if ate:
        fim = parse_dt_arg(ate, fim_do_dia=True)
    else:
        fim = agora

    rows, total_srv = listar_liberados(z, ini, fim, atend=atend)
    # agrupa por (atendimento, prescrição)
    grupos = {}
    for r in rows:
        key = (r.get("NR_ATENDIMENTO"), r.get("NR_PRESCRICAO"))
        grupos.setdefault(key, {"row": r, "rows": []})["rows"].append(r)

    if not as_json:
        print(f"Conferência de exames liberados (status {LIBERADO_STATUS} = {STATUS[LIBERADO_STATUS]})")
        print(f"Período: {ini.strftime('%d/%m/%Y %H:%M:%S')} → {fim.strftime('%d/%m/%Y %H:%M:%S')} (America/Sao_Paulo)")
        if atend:
            print(f"Filtro atendimento: {atend}")
        print(f"Amostras na fila: {len(rows)} (servidor qtTotal={total_srv}); "
              f"prescrições distintas: {len(grupos)}")
        print("(somente leitura — nada será salvo/aprovado)\n")

    achados = []
    sem = []
    n_exames = 0
    n_campos = 0
    exames_com_achado = set()

    for (at_i, nr), g in sorted(grupos.items(), key=lambda x: (x[0][0] or 0, x[0][1] or 0)):
        row = g["row"]
        paciente = row.get("NM_PESSOA_FISICA") or ""
        ds_idade = row.get("DS_IDADE")
        idade = _idade_anos(row.get("DT_NASCIMENTO"), agora)
        is_rn = _is_rn(idade, ds_idade, paciente)
        if not as_json:
            print(f"== AT {at_i} | presc {nr} | {paciente}"
                  f" | idade {ds_idade or (str(round(idade, 1)) + 'a' if idade is not None else '?')}"
                  f" | {row.get('DS_SETOR_ATUAL') or ''}")

        # abre a tela (write=False — sem procedure 1173 de preparação)
        t = Resultado(z, at_i, nr, write=False).abrir()
        if not t.items:
            if not as_json:
                print("   (sem itens na árvore de resultado)")
            continue

        for it in sorted(t.items, key=lambda i: i.get("NR_SEQ_PRESCR") or 0):
            seq = it.get("NR_SEQ_PRESCR")
            cd = (it.get("CD_EXAME") or "").strip()
            nm_ex = (it.get("NM_EXAME") or it.get("DS_PROCEDIMENTO") or cd).strip()
            exame_label = f"{cd} — {nm_ex}" if cd else nm_ex
            n_exames += 1
            if seq not in t.nodes:
                if not as_json:
                    print(f"   {exame_label}: fora da árvore")
                sem.append({"paciente": paciente, "atendimento": at_i,
                            "prescricao": nr, "exame": exame_label})
                continue
            antes = len(achados)
            vo = t.build(seq)["ResultVO"]
            node = t.nodes[seq][1]
            idade_n = _idade_anos(node.get("DT_NASCIMENTO"), agora)
            if idade_n is not None:
                idade = idade_n
                is_rn = _is_rn(idade, ds_idade, paciente)
            meta = {"paciente": paciente, "atend": at_i, "presc": nr,
                    "exame": exame_label, "cd": cd, "idade": idade, "is_rn": is_rn}
            n_campos += _analisar_vo(vo, meta, achados)
            if len(achados) == antes:
                sem.append({"paciente": paciente, "atendimento": at_i,
                            "prescricao": nr, "exame": exame_label})
            else:
                exames_com_achado.add((at_i, nr, exame_label))
            if not as_json:
                s = main_sub(vo)
                v = cur_value(vo)
                if str(cd).upper() == HEMO_SIGLA:
                    lid = hemo_lidos(vo)
                    resumo = f"Hb={_fmt_val(lid.get(1473))} Ht={_fmt_val(lid.get(1472))} " \
                             f"PLT={_fmt_val(lid.get(HEMO_PLT))} WBC_tot={_fmt_val(lid.get(HEMO_TOT))}"
                else:
                    resumo = _fmt_val(v) if v is not None else "-"
                    if s and s.get("dsUnidadeMedida"):
                        resumo += f" {s.get('dsUnidadeMedida')}"
                print(f"   {cd:<8} seq {seq:<4} {nm_ex[:40]:<40} = {resumo}  [status {vo.get('ieStatusAtend')}]")

    erros = [a for a in achados if a["tipo"] == "digitacao"]
    crits = [a for a in achados if a["tipo"] == "critico"]
    totais = {
        "prescricoes": len(grupos),
        "amostras_fila": len(rows),
        "exames": n_exames,
        "campos": n_campos,
        "erros_digitacao": len(erros),
        "criticos": len(crits),
        "sem_achados": len(sem),
    }

    if as_json:
        out = {
            "periodo": {"de": ini.isoformat(), "ate": fim.isoformat()},
            "status": LIBERADO_STATUS,
            "totais": totais,
            "erros_digitacao": erros,
            "criticos": crits,
            "sem_achados": sem,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return out

    def _print_grupo(titulo, lista):
        print(f"\n## {titulo} ({len(lista)})")
        if not lista:
            print("  (nenhum)")
            return
        for a in lista:
            prov = f" | valor provável: {_fmt_val(a['valor_provavel'])}" if a.get("valor_provavel") is not None else ""
            uni = f" {a['unidade']}" if a.get("unidade") else ""
            print(f"  • {a['paciente']} | AT {a['atendimento']} | presc {a['prescricao']}")
            print(f"    exame: {a['exame']} | campo: {a['campo']} = {_fmt_val(a['valor'])}{uni}")
            print(f"    motivo: {a['motivo']}{prov}")

    _print_grupo("Possíveis erros de digitação", erros)
    _print_grupo("Resultados críticos", crits)
    print(f"\n## Sem achados ({len(sem)} exame(s))")
    if sem:
        for s in sem:
            print(f"  • {s['paciente']} | AT {s['atendimento']} | presc {s['prescricao']} | {s['exame']}")
    else:
        print("  (nenhum)")

    print("\n## Totais")
    print(f"  Prescrições conferidas: {totais['prescricoes']}")
    print(f"  Amostras na fila:       {totais['amostras_fila']}")
    print(f"  Exames conferidos:      {totais['exames']}")
    print(f"  Campos conferidos:      {totais['campos']}")
    print(f"  Erros de digitação:     {totais['erros_digitacao']}")
    print(f"  Resultados críticos:    {totais['criticos']}")
    print(f"  Sem achados:            {totais['sem_achados']}")
    return {"totais": totais, "erros_digitacao": erros, "criticos": crits, "sem_achados": sem}



def main():
    ap = argparse.ArgumentParser(prog="zion.py")
    ap.add_argument("--user", dest="cli_user", default=None,
                    help="usuário do Zion (senão ZION_USER / arquivo salvo / prompt)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("login", help="pede usuário/senha (ou usa env), valida e grava em ~/.config/zion-cli/")
    sp.add_parser("logout", help="apaga credenciais salvas e a sessão local")
    sp.add_parser("whoami", help="mostra só o usuário salvo (nunca a senha)")
    fl = sp.add_parser("fila", help="fila geral de pendentes por etapa, sem número de atendimento")
    fl.add_argument("--status", type=int, choices=[10, 20, 25, 26, 30], help="só esta etapa")
    fl.add_argument("--exames", action="store_true", help="lista também amostras e exames de cada atendimento")
    fl.add_argument("--resumo", action="store_true", help="só as contagens")
    l = sp.add_parser("listar"); l.add_argument("atendimento", type=int)
    d = sp.add_parser("digitacao"); d.add_argument("atendimento", type=int)
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--desde", type=int, choices=[10, 20, 25, 26], help="(só dry-run) simula a partir deste status")
    le = sp.add_parser("ler"); le.add_argument("atendimento", type=int)
    r = sp.add_parser("resultado"); r.add_argument("atendimento", type=int)
    r.add_argument("--exame", action="append", required=True, help="SIGLA=valor ou SIGLA.campo=valor, ex.: TGO=20.7, BILI.total=0.64")
    r.add_argument("--dry-run", action="store_true"); r.add_argument("--forcar", action="store_true")
    r.add_argument("--dump-payload", help="grava os payloads do save neste arquivo")
    g = sp.add_parser("gaso"); g.add_argument("atendimento", type=int)
    for _, opt, _ in GASO_FIELDS: g.add_argument("--" + opt, type=str)
    g.add_argument("--obs", type=str, help="observação da gasometria")
    g.add_argument("--dry-run", action="store_true"); g.add_argument("--forcar", action="store_true")
    g.add_argument("--dump-payload", help="grava o payload do save da gasometria neste arquivo")
    hm = sp.add_parser("hemo", help="digita e salva (sem liberar) Hemograma Completo")
    hm.add_argument("atendimento", type=int)
    for o in ("rbc", "hgb", "hct", "vcm", "hcm", "chcm", "rdw", "wbc", "neu", "lym", "mon", "eos", "bas", "plt", "vpm"):
        hm.add_argument("--" + o, type=str, required=True)
    hm.add_argument("--dry-run", action="store_true"); hm.add_argument("--forcar", action="store_true")
    hm.add_argument("--dump-payload", help="grava o payload do save neste arquivo")
    cf = sp.add_parser("conferir",
                       help="só leitura: audita TODOS os exames liberados (status 40) do período")
    cf.add_argument("--de", help="início DD/MM/AAAA[ HH:MM] (padrão: hoje 00:00:00)")
    cf.add_argument("--ate", help="fim DD/MM/AAAA[ HH:MM] (padrão: agora)")
    cf.add_argument("--at", dest="atendimento", type=int, help="filtra um atendimento")
    cf.add_argument("--json", dest="as_json", action="store_true", help="saída JSON")
    a = ap.parse_args()
    t0 = time.time()

    if a.cmd == "logout":
        path = creds_path()
        if os.path.exists(path) or os.path.exists(session_path()):
            delete_creds()
            print(f"Credenciais e sessão removidas ({path}).")
        else:
            print("Nenhuma credencial salva.")
        return

    if a.cmd == "whoami":
        saved = read_creds()
        env_u = (a.cli_user or os.environ.get("ZION_USER") or "").strip()
        if env_u:
            print(env_u + (" (via env/--user)" if not saved.get("username") else f" (env/--user; salvo: {saved.get('username')})"))
        elif saved.get("username"):
            print(saved["username"])
        else:
            print("Nenhum usuário salvo. Rode: python3 zion.py login")
            raise SystemExit(1)
        return

    z = Zion(cli_user=a.cli_user)
    if a.cmd == "login":
        z.login(force_prompt=True, save_creds=True)
    elif a.cmd == "fila":
        cmd_fila(z, a.status, a.exames, a.resumo)
    elif a.cmd == "listar":
        cmd_listar(z, a.atendimento)
    elif a.cmd == "digitacao":
        cmd_digitacao(z, a.atendimento, a.dry_run, a.desde)
    elif a.cmd == "ler":
        cmd_ler(z, a.atendimento)
    elif a.cmd == "resultado":
        cmd_resultado(z, a.atendimento, a.exame, a.dry_run, a.forcar, a.dump_payload)
    elif a.cmd == "hemo":
        cmd_hemo(z, a.atendimento, a, a.dry_run, a.forcar, a.dump_payload)
    elif a.cmd == "conferir":
        cmd_conferir(z, a.de, a.ate, a.atendimento, a.as_json)
    else:
        cmd_gaso(z, a.atendimento, a, a.dry_run, a.forcar, a.dump_payload)
    log(f"[{time.time() - t0:.1f}s, {z.ncalls} chamadas de serviço]")


if __name__ == "__main__":
    main()
