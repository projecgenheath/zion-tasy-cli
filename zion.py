#!/usr/bin/env python3
"""zion.py - CLI para o Zion/Tasy 5.04 sem navegador.

Uso:
  python3 zion.py login                       # testa login + perfil
  python3 zion.py fila [--status N] [--exames] [--resumo]  # fila geral, sem atendimento
  python3 zion.py listar ATENDIMENTO          # linhas/status por fase
  python3 zion.py digitacao ATENDIMENTO [--dry-run] [--desde STATUS]
  python3 zion.py ler ATENDIMENTO              # valores salvos dos exames em Digitação
  python3 zion.py resultado AT --exame NA+=134.9 [--exame ...] [--dry-run] [--forcar]
  python3 zion.py gaso AT --na 134.9 --k 4.37 --ica 1.08 --cl 105.7 [--glu --lac --ph ...] [--dry-run] [--forcar]
  (nunca libera; após salvar relê via build e compara)

Senha: variável de ambiente ZION_PASSWORD (nunca é impressa).
Sessão: .session.json (chmod 600) ao lado deste arquivo; renova/reloga sozinho.
"""
import argparse, copy, json, os, sys, time, datetime as dt
import requests

def _load_env():
    """Carrega .env.example (URL/usuário/perfil já preenchidos) e depois .env (senha). Variáveis já definidas têm prioridade."""
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

_load_env()

HOST = os.environ.get("ZION_URL", "").rstrip("/")
API = HOST + "/TasyAppServer/resources"
USER = os.environ.get("ZION_USER", "")
SCOPE = "WTASY"
PERFIL_NOME = os.environ.get("ZION_PROFILE", "")
SETOR_NOME = os.environ.get("ZION_SETOR", "")
HERE = os.path.dirname(os.path.abspath(__file__))
if not (HOST and USER and PERFIL_NOME) and __name__ == "__main__":
    sys.exit("Configuração não encontrada: o arquivo .env.example deve estar na mesma pasta do zion.py.")
SESSION_FILE = os.path.join(HERE, ".session.json")
TPL = json.load(open(os.path.join(HERE, "templates.json"), encoding="utf-8"))
TZ = dt.timezone(dt.timedelta(hours=-3))
STATUS = {10: "Prescrições / Pendente coleta", 20: "Material Coletado", 25: "Em Análise",
          26: "Interfaceamento/Fase Analítica", 30: "Digitação do Resultado"}
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
    def __init__(self, verbose=False):
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
        fd = os.open(SESSION_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.sess, f)
        os.chmod(SESSION_FILE, 0o600)

    def _apply(self):
        self.s.headers["Authorization"] = "Bearer " + self.sess["access_token"]
        if self.sess.get("xsrf"):
            self.s.headers["crsfToken"] = self.sess["xsrf"]
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

    def login(self):
        pw = os.environ.get("ZION_PASSWORD")
        if not pw and sys.stdin.isatty():
            import getpass
            pw = getpass.getpass(f"Senha do Zion para {USER}: ")
        if not pw:
            sys.exit("Falta só a senha: crie o arquivo .env com ZION_PASSWORD=sua_senha (ou exporte ZION_PASSWORD). URL, usuário e perfil já vêm do .env.example.")
        self.s.cookies.clear(); self.s.headers.pop("Authorization", None); self.s.headers.pop("crsfToken", None)
        self.sess = {}
        body = {"username": USER, "password": pw, "computerName": None, "osUsername": None, "scope": SCOPE,
                "timezone": "America/Sao_Paulo", "ipMachine": None, "sessionUnlock": False}
        r = self.s.post(API + "/public/security/oauth", json=body, timeout=30)
        if r.status_code != 200:
            try: msg = r.json().get("message")
            except Exception: msg = r.text[:200]
            sys.exit(f"Login falhou (HTTP {r.status_code}): {msg}")
        self._store_tokens(r)
        u = self.s.get(API + "/user/data", timeout=30).json()
        perfil = next((p for p in u.get("profiles", []) if p.get("nmPerfil") == PERFIL_NOME), None)
        if not perfil:
            sys.exit("Perfil não encontrado: " + PERFIL_NOME)
        if u.get("cdPerfil") != perfil["cdPerfil"]:
            r = self.s.post(API + "/user/profile", json={"profile": perfil["cdPerfil"], "changingProfile": True}, timeout=30)
            r.raise_for_status()
            u = r.json() if r.content else self.s.get(API + "/user/data", timeout=30).json()
        setor = next((s for c in u.get("classificationSectors", []) for s in c.get("sectors", []) if s.get("nmSetor") == SETOR_NOME), None)
        self.sess.update({"cdPerfil": u.get("cdPerfil"), "cdSetor": u.get("cdSetorAtendimento"),
                          "nmUsuario": u.get("nmUsuario"), "cdEstab": u.get("cdEstabelecimento"),
                          "setor_esperado": setor and setor["cdSetor"]})
        if u.get("cdPerfil") != perfil["cdPerfil"]:
            sys.exit(f"Não consegui trocar para o perfil {PERFIL_NOME} (atual {u.get('cdPerfil')})")
        if setor and u.get("cdSetorAtendimento") != setor["cdSetor"]:
            log(f"AVISO: setor atual {u.get('cdSetorAtendimento')} != {SETOR_NOME} ({setor['cdSetor']})")
        self.sess["cookies"] = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in self.s.cookies]
        self._save()
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
    if path.endswith("28710") and str(v("QT_EXAME_SUSP_P") or "0") != "0":
        raise RuntimeError(f"28710: QT_EXAME_SUSP_P={v('QT_EXAME_SUSP_P')} (exame suspenso) - parei")
    if path.endswith("33538") and v("DS_EXAMES_MEST_P"):
        raise RuntimeError("33538 pediu data da menstruação (DS_EXAMES_MEST_P) - parei")
    if path.endswith("28842") and v("DS_MENSAGEM_P"):
        raise RuntimeError(f"28842 mensagem: {v('DS_MENSAGEM_P')} - parei")
    # HAR <n> (amostra <n>, COOD/GP-TIP): com IE_GERAR_AMOSTRA=S a tela não abre diálogo nem gera
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
    """Reproduz o save da tela (HAR <n>/<n>): subexames V/DV vão com qtResultado em TEXTO
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


def valor_campo(s, txt):
    """-> (valor, dec) ou str de erro. V/DV: float; S: opção da lista; D/DL: texto livre."""
    fmt = s.get("ieFormatoResultado")
    if fmt in ("V", "DV"):
        try: f, dec, _ = parse_val(txt)
        except ValueError: return f"'{txt}' não é número"
        return f, dec
    if fmt == "S":
        ops = [o.get("CD") for o in (s.get("optionalValues") or [])]
        m = [o for o in ops if _slug(o) == _slug(txt)] or [o for o in ops if str(o).strip().upper() == str(txt).strip().upper()]
        if not m: return f"'{txt}' inválido para {s.get('nmExame')} (opções: {' / '.join(ops)})"
        return m[0], 0
    if fmt in ("D", "DL"): return str(txt), 0
    return f"formato {fmt} não suportado"


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


# exames de vários campos: nrSeqExame do exame -> {campo: nrSeqExame do subexame}
MULTI = {575: {"total": 36503, "direta": 36504, "indireta": 36505}}   # Bilirrubina Total e Frações


def completar_bili(campos):
    if "total" in campos and "direta" in campos and "indireta" not in campos:
        t, dt, _ = parse_val(campos["total"]); d, dd, _ = parse_val(campos["direta"])
        campos["indireta"] = f"{t - d:.{max(dt, dd)}f}"
        print(f"  BILI: indireta calculada = total - direta = {campos['indireta']}")
    return campos


def lancar(z, atend, pedidos, dry, forcar, telas=None, dump=None):
    """pedidos: lista de (chave, campo_ou_None, texto_valor). Só lança no que existir em Digitação."""
    if telas is None:
        data, telas = abrir_telas(z, atend, write=not dry)
    grupos = {}
    for chave, campo, txt in pedidos:
        hit = None
        for t in telas:
            for it in t.items:
                if str(it.get("CD_EXAME", "")).upper() == str(chave).upper() or str(it.get("NR_SEQ_EXAME")) == str(chave):
                    hit = (t, it); break
            if hit: break
        if not hit:
            print(f"  {chave}: não existe em Digitação neste atendimento - ignorado"); continue
        g = grupos.setdefault(id(hit[1]), [chave, hit[0], hit[1], {}])
        g[3][campo] = txt
    rel = []; dumps = []
    for chave, t, it, campos in grupos.values():
        seq, nse = it["NR_SEQ_PRESCR"], it["NR_SEQ_EXAME"]
        tag = f"{it['CD_EXAME']} (prescr {t.nr} seq {seq})"
        if it.get("IE_STATUS_ATEND") != 30 or seq not in t.nodes:
            print(f"  {tag}: status {it.get('IE_STATUS_ATEND')} - não está em Digitação, ignorado"); continue
        if nse in MULTI and 575 == nse: campos = completar_bili(campos)
        vo = t.clicar(seq, nse)["ResultVO"]
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
        env = {sq: f for sq, (n, f, dec, s) in cs.items()}
        novo = ds_payload(vo, env)
        dumps.append({"exame": it["CD_EXAME"], "payload": [H(novo)]})
        desc = ", ".join(f"{n}={vtxt(f)}" + (f" (atual {vtxt(sub_val(s))})" if sub_val(s) not in (None, 0) else "") for sq, (n, f, dec, s) in cs.items())
        if dry:
            print(f"  [dry-run] {tag}: {it['NM_EXAME'].strip()}: {desc}  -> POST WResultEntry/save (não enviado)")
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
    """Reproduz o save da tela (HAR <n> GASV): DV preenchido -> qtResultado texto ("7.458") e
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
    print("Bioquímica equivalente: " + ", ".join(f"{k}={v}" for k, v in pedidos))
    lancar(z, atend, pedidos, dry, forcar, telas)


# ---------------- Hemograma Completo (HC, 202020380) ----------------
# Descobertas no HAR do <n>: a tela envia TODOS os subexames V/DV com qtResultado em texto
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


def main():
    ap = argparse.ArgumentParser(prog="zion.py")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("login")
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
    a = ap.parse_args()
    t0 = time.time(); z = Zion()
    if a.cmd == "login":
        z.login()
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
    else:
        cmd_gaso(z, a.atendimento, a, a.dry_run, a.forcar, a.dump_payload)
    log(f"[{time.time() - t0:.1f}s, {z.ncalls} chamadas de serviço]")


if __name__ == "__main__":
    main()
