import io
from datetime import datetime, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Monitoramento Amazon",
    page_icon="🕒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DB_URL = st.secrets["connections"]["supabase_db"]["url"]


# ============================================================
# CONEXÃO COM SUPABASE / POSTGRESQL
# ============================================================
def conectar():
    """
    Abre uma conexão com o PostgreSQL do Supabase.

    A URL é desmontada manualmente porque senhas de banco podem
    conter caracteres codificados, como %40 para @. Isso evita o
    erro do psycopg2 do tipo "missing = after ...".
    """
    from urllib.parse import urlparse, unquote

    url = urlparse(str(DB_URL).strip())

    if url.scheme not in ("postgresql", "postgres"):
        raise ValueError(
            "A URL do Supabase precisa começar com "
            "'postgresql://' ou 'postgres://'."
        )

    host = url.hostname
    port = url.port or 5432
    database = url.path.lstrip("/") or "postgres"
    user = unquote(url.username or "")
    password = unquote(url.password or "")

    if not host or not user or not password:
        raise ValueError(
            "A connection string do Supabase está incompleta. "
            "Confira usuário, senha e host nos Secrets."
        )

    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        connect_timeout=10,
        sslmode="require",
    )


def executar(query, params=None, fetch=False, fetchone=False):
    """
    Executa uma operação no banco com commit/rollback seguro.
    Cada alteração fica persistida no Supabase, não em arquivo local.
    """
    conn = None
    try:
        conn = conectar()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            resultado = None
            if fetchone:
                resultado = cur.fetchone()
            elif fetch:
                resultado = cur.fetchall()
        conn.commit()
        return resultado
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# ============================================================
# BANCO - CRIAÇÃO AUTOMÁTICA DAS TABELAS
# ============================================================
def criar_banco():
    executar("""
        CREATE TABLE IF NOT EXISTS operadores (
            id BIGSERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            funcao TEXT NOT NULL,
            turno TEXT NOT NULL CHECK (turno IN ('T1', 'T2', 'T3')),
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    executar("""
        CREATE TABLE IF NOT EXISTS escala (
            id BIGSERIAL PRIMARY KEY,
            operador_id BIGINT NOT NULL REFERENCES operadores(id),
            semana_id DATE NOT NULL,
            sexta TEXT NOT NULL,
            sabado TEXT NOT NULL,
            domingo TEXT NOT NULL,
            segunda TEXT NOT NULL,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_escala_operador_semana
                UNIQUE (operador_id, semana_id)
        );
    """)

    executar("""
        CREATE TABLE IF NOT EXISTS historico (
            id BIGSERIAL PRIMARY KEY,
            data_hora TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            operador_id BIGINT,
            operador_nome TEXT NOT NULL,
            semana_id DATE NOT NULL,
            dia TEXT NOT NULL,
            de_status TEXT NOT NULL,
            para_status TEXT NOT NULL
        );
    """)

    executar("""
        CREATE INDEX IF NOT EXISTS idx_escala_semana
        ON escala (semana_id);
    """)

    executar("""
        CREATE INDEX IF NOT EXISTS idx_historico_semana
        ON historico (semana_id);
    """)


# ============================================================
# DADOS PADRÃO
# ============================================================
FUNCIONARIOS_OFICIAIS = [
    ("ALAN ARAÚJO", "ANALISTA", "T1"),
    ("MARGARIDA", "PICKUP", "T1"),
    ("JOSÉ BRUNO PALHANO", "PICKUP", "T1"),
    ("CRISTOVÃO MIKELLYS", "DEPART", "T1"),
    ("PEDRO LUCAS", "DROPOFF", "T1"),
    ("FELIPE ALLAN", "DROPOFF", "T1"),
    ("BRUNA BLENDA", "DROPOFF", "T1"),
    ("CONCEIÇÃO DAIANE", "SEGURANÇA (ONISYS)", "T1"),
    ("MATHEUS LUSTOSA", "SEGURANÇA/ELOG", "T1"),
    ("MANUELA PINHEIRO", "LÍDER", "T2"),
    ("ISABEL", "LÍDER/SEGURANÇA", "T2"),
    ("ANDREZA OLIVEIRA", "PICKUP", "T2"),
    ("ROZIANE DA SILVA", "PICKUP", "T2"),
    ("DAIANE", "SEGURANÇA", "T2"),
    ("EMANUEL ROBERTO", "DEPART", "T2"),
    ("TAMMYRIS DA SILVA", "DROPOFF", "T2"),
    ("RAPHAEL DO NASCIMENTO", "DROPOFF", "T2"),
    ("LUDMILLA RODRIGUES", "DROPOFF", "T2"),
    ("MARIA NATHALIA", "SEGURANÇA", "T2"),
    ("CINAMOR", "ELOG", "T2"),
    ("WESLEY", "LÍDER", "T3"),
    ("JOÃO", "LÍDER/SEGURANÇA", "T3"),
    ("RILDOMAR", "PICKUP", "T3"),
    ("LUCIANA", "PICKUP", "T3"),
    ("GLAYLDSON", "SEGURANÇA", "T3"),
    ("TAYANARA", "DEPART", "T3"),
    ("RUAN", "DROPOFF", "T3"),
    ("BÁRBARA", "DROPOFF", "T3"),
]

HORARIOS = {
    "T1": "07:00 às 15:00",
    "T2": "15:00 às 23:00",
    "T3": "23:00 às 07:00",
}

NOMES_TURNOS = {
    "T1": "Turno 1",
    "T2": "Turno 2",
    "T3": "Turno 3",
}

DIAS = [
    ("Sexta", "sexta"),
    ("Sábado", "sabado"),
    ("Domingo", "domingo"),
    ("Segunda", "segunda"),
]

ORDEM_FUNCOES = [
    ("LÍDER", 0),
    ("ANALISTA", 1),
    ("PICKUP", 2),
    ("DEPART", 3),
    ("DROPOFF", 4),
    ("SEGURANÇA/ELOG", 6),
    ("SEGURANÇA", 5),
]


# ============================================================
# ESTILO
# ============================================================
st.markdown("""
<style>
header[data-testid="stHeader"],
.stAppDeployButton,
div[data-testid="stViewerBadge"],
footer,
#MainMenu,
.stDecoration {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
}

[data-testid="stSidebar"] { display: none; }
[data-testid="stAppViewContainer"] { background-color: #101A2C; }
.stApp { background-color: #101A2C; color: #E7ECF3; }

.titulo {
    color: #FFFFFF;
    font-family: 'Segoe UI', sans-serif;
    font-size: 32px;
    font-weight: 800;
}
.subtitulo-tag {
    color: #FF9900;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.6px;
}
.subtitulo {
    color: #8794A6;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 20px;
}

div[data-baseweb="select"] > div {
    border: 1px solid #33415F !important;
    border-radius: 8px !important;
    background-color: #182238 !important;
    color: #E7ECF3 !important;
}
div[data-baseweb="input"] input {
    color: #E7ECF3 !important;
    background-color: #182238 !important;
}
[data-testid="stTextInput"] input {
    background-color: #182238 !important;
    color: #E7ECF3 !important;
    border: 1px solid #33415F !important;
}
label, .stMarkdown, p { color: #C7D0DD; }

.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #2A3855; }
.stTabs [data-baseweb="tab"] { color: #8794A6; font-weight: 700; }
.stTabs [aria-selected="true"] { color: #FF9900 !important; border-bottom-color: #FF9900 !important; }

.turno-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 15px;
    margin-bottom: 22px;
    padding: 12px 16px;
    background-color: #182238;
    border-left: 5px solid #FF9900;
    border-bottom: 1px solid #2A3855;
    border-radius: 9px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
.turno-titulo { font-size: 21px; font-weight: 800; color: #FFFFFF; }
.turno-horario {
    background-color: #243553;
    color: #FF9900;
    border: 1px solid #3E4F73;
    padding: 4px 11px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 800;
}

.header-col {
    text-align: center;
    font-weight: 800;
    font-size: 11px;
    color: #8794A6;
    margin-bottom: 8px;
    letter-spacing: 0.4px;
}
.header-esquerda { text-align: left; }
.nome-operador { padding-top: 9px; font-size: 13px; color: #FFFFFF; }
.funcao-operador { padding-top: 9px; font-size: 11px; color: #4EA8E0; font-weight: 700; }

.card-trabalho {
    background-color: #8CD790;
    color: #111111;
    padding: 8px 5px;
    border-radius: 9px;
    text-align: center;
    font-weight: 800;
    font-size: 12px;
    border-left: 4px solid #4CAF50;
    margin-bottom: 4px;
    min-height: 48px;
    width: 100%;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.22);
}
.card-folga {
    background-color: #D9A227;
    color: #1B2438;
    padding: 8px 5px;
    border-radius: 9px;
    text-align: center;
    font-weight: 800;
    font-size: 12px;
    border-left: 4px solid #A67818;
    margin-bottom: 4px;
    min-height: 48px;
    width: 100%;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.22);
}

.separador { border: 0; border-top: 1px solid #2A3855; margin-top: 2px; margin-bottom: 15px; }

.metric-card {
    background-color: #182238;
    border: 1px solid #2A3855;
    border-top: 4px solid #FF9900;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.metric-numero { font-size: 22px; font-weight: 800; color: #FFFFFF; }
.metric-label { font-size: 11px; color: #8794A6; font-weight: 700; }

[data-testid="stForm"] {
    background-color: #182238;
    border: 1px solid #2A3855;
    padding: 16px;
    border-radius: 10px;
}
.stButton > button {
    border-radius: 7px;
    font-weight: 700;
    border: 1px solid #33415F;
    background-color: #1E2A42;
    color: #E7ECF3;
}
.stButton > button:hover { border-color: #FF9900; color: #FF9900; }

div[data-testid="stDownloadButton"] > button {
    background-color: transparent !important;
    border: 1px solid #2A3855 !important;
    color: #5B6779 !important;
    font-size: 12px !important;
    padding: 6px 0 !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    border-color: #4EA8E0 !important;
    color: #4EA8E0 !important;
}

div[data-testid="column"] .stButton > button { color: #C7D0DD; }
.stMainBlockContainer { padding-top: 25px !important; padding-bottom: 30px !important; }
.stCaption { color: #5B6779 !important; }

div[data-testid="stPopover"] button {
    background-color: #FF9900 !important;
    color: #1A1A1A !important;
    border: 1px solid #FF9900 !important;
    font-weight: 800 !important;
    border-radius: 8px !important;
}
div[data-testid="stPopover"] button p { color: #1A1A1A !important; }
div[data-testid="stPopover"] button:hover {
    background-color: #E68A00 !important;
    border-color: #E68A00 !important;
    color: #0B3C5D !important;
}
div[data-testid="stPopover"] button:hover p { color: #0B3C5D !important; }

div[data-testid="stPopoverBody"],
div[data-baseweb="popover"] div[role="tooltip"] {
    background-color: #182238 !important;
    border: 1px solid #2A3855 !important;
    border-radius: 12px !important;
}
div[data-testid="stPopoverBody"] * ,
div[data-baseweb="popover"] div[role="tooltip"] * { color: #E7ECF3; }

div[data-testid="stPopoverBody"] input,
div[data-baseweb="popover"] div[role="tooltip"] input {
    background-color: #101A2C !important;
    color: #E7ECF3 !important;
    border: 1px solid #33415F !important;
}

ul[data-baseweb="menu"] {
    background-color: #182238 !important;
    border: 1px solid #2A3855 !important;
}
ul[data-baseweb="menu"] li {
    background-color: #182238 !important;
    color: #E7ECF3 !important;
}
ul[data-baseweb="menu"] li:hover {
    background-color: #243553 !important;
    color: #FF9900 !important;
}

[data-testid="stExpander"] {
    background-color: #182238;
    border: 1px solid #2A3855;
    border-radius: 8px;
}

input[placeholder="Nome do operador..."] {
    background-color: #FFFFFF !important;
    color: #101A2C !important;
    border: 1px solid #FF9900 !important;
    font-weight: 600 !important;
}
input[placeholder="Nome do operador..."]::placeholder {
    color: #8794A6 !important;
}

@media (max-width: 800px) {
    .titulo { font-size: 24px; }
    .turno-titulo { font-size: 18px; }
    .turno-horario { font-size: 10px; }
    .metric-numero { font-size: 18px; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# FUNÇÕES DE DADOS
# ============================================================
def contar_operadores():
    row = executar(
        "SELECT COUNT(*) AS total FROM operadores WHERE ativo = TRUE",
        fetchone=True,
    )
    return int(row["total"])


def sem_operadores():
    return contar_operadores() == 0


def carregar_dados_iniciais():
    """Só cria os operadores padrão se o Supabase estiver vazio."""
    if not sem_operadores():
        return

    for nome, funcao, turno in FUNCIONARIOS_OFICIAIS:
        executar(
            """
            INSERT INTO operadores (nome, funcao, turno)
            VALUES (%s, %s, %s)
            """,
            (nome, funcao, turno),
        )


def buscar_operadores():
    rows = executar(
        """
        SELECT id, nome, funcao, turno
        FROM operadores
        WHERE ativo = TRUE
        ORDER BY turno, nome
        """,
        fetch=True,
    )
    return [
        (int(r["id"]), r["nome"], r["funcao"], r["turno"])
        for r in rows
    ]


def cadastrar_operador(nome, funcao, turno):
    executar(
        """
        INSERT INTO operadores (nome, funcao, turno)
        VALUES (%s, %s, %s)
        """,
        (nome, funcao, turno),
    )


def editar_operador(operador_id, nome, funcao, turno):
    executar(
        """
        UPDATE operadores
        SET nome = %s, funcao = %s, turno = %s, atualizado_em = NOW()
        WHERE id = %s
        """,
        (nome, funcao, turno, operador_id),
    )


def remover_operador(operador_id):
    # Remoção lógica: os registros históricos e escalas permanecem.
    executar(
        """
        UPDATE operadores
        SET ativo = FALSE, atualizado_em = NOW()
        WHERE id = %s
        """,
        (operador_id,),
    )


def buscar_status(operador_id, semana_id):
    row = executar(
        """
        SELECT sexta, sabado, domingo, segunda
        FROM escala
        WHERE operador_id = %s AND semana_id = %s
        """,
        (operador_id, semana_id),
        fetchone=True,
    )

    if row is None:
        return None

    return (
        row["sexta"],
        row["sabado"],
        row["domingo"],
        row["segunda"],
    )


def salvar_status(operador_id, semana_id, sexta, sabado, domingo, segunda):
    executar(
        """
        INSERT INTO escala (
            operador_id, semana_id,
            sexta, sabado, domingo, segunda,
            atualizado_em
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (operador_id, semana_id)
        DO UPDATE SET
            sexta = EXCLUDED.sexta,
            sabado = EXCLUDED.sabado,
            domingo = EXCLUDED.domingo,
            segunda = EXCLUDED.segunda,
            atualizado_em = NOW()
        """,
        (
            operador_id,
            semana_id,
            sexta,
            sabado,
            domingo,
            segunda,
        ),
    )


def registrar_historico(
    operador_id,
    operador_nome,
    semana_id,
    dia,
    de_status,
    para_status,
):
    executar(
        """
        INSERT INTO historico (
            operador_id,
            operador_nome,
            semana_id,
            dia,
            de_status,
            para_status
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            operador_id,
            operador_nome,
            semana_id,
            dia,
            de_status,
            para_status,
        ),
    )


def buscar_historico(limite=50):
    rows = executar(
        """
        SELECT
            data_hora,
            operador_nome,
            semana_id,
            dia,
            de_status,
            para_status
        FROM historico
        ORDER BY id DESC
        LIMIT %s
        """,
        (limite,),
        fetch=True,
    )
    return [
        (
            r["data_hora"].strftime("%d/%m/%Y %H:%M")
            if hasattr(r["data_hora"], "strftime")
            else str(r["data_hora"]),
            r["operador_nome"],
            str(r["semana_id"]),
            r["dia"],
            r["de_status"],
            r["para_status"],
        )
        for r in rows
    ]


# ============================================================
# DATAS
# ============================================================
def obter_semana(deslocamento=0):
    hoje = datetime.now()
    dias_para_sexta = (hoje.weekday() - 4) % 7
    sexta = (
        hoje
        - timedelta(days=dias_para_sexta)
        + timedelta(weeks=deslocamento)
    )
    sabado = sexta + timedelta(days=1)
    domingo = sexta + timedelta(days=2)
    segunda = sexta + timedelta(days=3)

    return {
        "id": sexta.strftime("%Y-%m-%d"),
        "nome": f"{sexta.strftime('%d/%m')} até {segunda.strftime('%d/%m')}",
        "Sexta": sexta.strftime("%d/%m"),
        "Sábado": sabado.strftime("%d/%m"),
        "Domingo": domingo.strftime("%d/%m"),
        "Segunda": segunda.strftime("%d/%m"),
    }


def prioridade_funcao(funcao):
    funcao_upper = funcao.upper()
    for palavra_chave, prioridade in ORDEM_FUNCOES:
        if palavra_chave in funcao_upper:
            return prioridade
    return 99


def ordenar_por_funcao(lista_operadores):
    return sorted(
        lista_operadores,
        key=lambda x: (prioridade_funcao(x[2]), x[1]),
    )


# ============================================================
# EXPORTAÇÃO
# ============================================================
def gerar_excel(operadores, semana):
    linhas = []

    for operador_id, nome, funcao, turno in operadores:
        status = buscar_status(operador_id, semana["id"])

        if status is None:
            horario = HORARIOS[turno]
            status = (horario, horario, horario, horario)

        linhas.append({
            "Turno": NOMES_TURNOS[turno],
            "Operador": nome,
            "Função": funcao,
            f"Sexta ({semana['Sexta']})":
                "FOLGA" if status[0] == "FOLGA" else "TRABALHO",
            f"Sábado ({semana['Sábado']})":
                "FOLGA" if status[1] == "FOLGA" else "TRABALHO",
            f"Domingo ({semana['Domingo']})":
                "FOLGA" if status[2] == "FOLGA" else "TRABALHO",
            f"Segunda ({semana['Segunda']})":
                "FOLGA" if status[3] == "FOLGA" else "TRABALHO",
        })

    df = pd.DataFrame(linhas)
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Escala")

    buffer.seek(0)
    return buffer


# ============================================================
# INICIALIZAÇÃO SEGURA
# ============================================================
try:
    criar_banco()
    carregar_dados_iniciais()
except Exception as e:
    st.error("Não foi possível conectar ao banco do Supabase.")
    st.code(str(e))
    st.stop()


# ============================================================
# SESSÃO
# ============================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "deslocamento_semana" not in st.session_state:
    st.session_state.deslocamento_semana = 0


# ============================================================
# TOP BAR
# ============================================================
semana = obter_semana(st.session_state.deslocamento_semana)
semana_id = semana["id"]

col_tit, col_log = st.columns([4, 1], vertical_alignment="center")

with col_tit:
    st.markdown(
        "<div class='subtitulo-tag'>ESCALA OPERACIONAL</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='titulo'>Monitoramento - amazon</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='subtitulo'>Selecione o período da escala</div>",
        unsafe_allow_html=True,
    )

with col_log:
    if not st.session_state.autenticado:
        with st.popover("👤 Gestor", use_container_width=True):
            with st.form("login_form", clear_on_submit=True):
                usuario = st.text_input("Usuário")
                senha = st.text_input("Senha", type="password")
                entrar = st.form_submit_button(
                    "Entrar",
                    use_container_width=True,
                )

                if entrar:
                    usuario_ok = st.secrets["auth"]["usuario"]
                    senha_ok = st.secrets["auth"]["senha"]

                    if (
                        usuario.lower().strip() == usuario_ok.lower().strip()
                        and senha == senha_ok
                    ):
                        st.session_state.autenticado = True
                        st.rerun()
                    else:
                        st.error("Dados incorretos.")
    else:
        with st.popover("⚙️ Painel de Gestão", use_container_width=True):
            st.markdown("**Gestão de Escala**")
            st.divider()

            menu_admin = st.selectbox(
                "O que deseja fazer?",
                [
                    "Adicionar Operador",
                    "Editar Operador",
                    "Remover Operador",
                    "Histórico de Alterações",
                ],
            )

            if menu_admin == "Adicionar Operador":
                novo_nome = st.text_input("Nome").strip().upper()
                nova_funcao = st.text_input("Função").strip().upper()
                novo_turno = st.selectbox(
                    "Turno",
                    ["T1", "T2", "T3"],
                    format_func=lambda x:
                        f"{NOMES_TURNOS[x]} — {HORARIOS[x]}",
                )

                if st.button(
                    "Confirmar Cadastro",
                    use_container_width=True,
                ):
                    if novo_nome and nova_funcao:
                        cadastrar_operador(
                            novo_nome,
                            nova_funcao,
                            novo_turno,
                        )
                        st.success("Operador cadastrado no Supabase!")
                        st.rerun()
                    else:
                        st.warning("Preencha todos os campos.")

            elif menu_admin == "Editar Operador":
                operadores_lista = buscar_operadores()

                if operadores_lista:
                    opcoes_edicao = {
                        f"{x[1]} — {x[2]}": x
                        for x in operadores_lista
                    }

                    selecionado = st.selectbox(
                        "Selecione o operador",
                        list(opcoes_edicao.keys()),
                    )

                    op_sel = opcoes_edicao[selecionado]

                    nome_edit = st.text_input(
                        "Nome",
                        value=op_sel[1],
                    ).strip().upper()

                    funcao_edit = st.text_input(
                        "Função",
                        value=op_sel[2],
                    ).strip().upper()

                    turno_edit = st.selectbox(
                        "Turno",
                        ["T1", "T2", "T3"],
                        index=["T1", "T2", "T3"].index(op_sel[3]),
                        format_func=lambda x:
                            f"{NOMES_TURNOS[x]} — {HORARIOS[x]}",
                    )

                    if st.button(
                        "Salvar Alterações",
                        use_container_width=True,
                    ):
                        editar_operador(
                            op_sel[0],
                            nome_edit,
                            funcao_edit,
                            turno_edit,
                        )
                        st.success("Operador atualizado no Supabase!")
                        st.rerun()
                else:
                    st.info("Nenhum operador cadastrado.")

            elif menu_admin == "Remover Operador":
                operadores_lista = buscar_operadores()

                if operadores_lista:
                    opcoes_remocao = {
                        f"{x[1]} — {x[2]}": x[0]
                        for x in operadores_lista
                    }

                    selecionado = st.selectbox(
                        "Selecione o operador",
                        list(opcoes_remocao.keys()),
                    )

                    if st.button(
                        "Confirmar Remoção",
                        use_container_width=True,
                    ):
                        remover_operador(
                            opcoes_remocao[selecionado]
                        )
                        st.success(
                            "Operador removido da escala ativa. "
                            "Histórico preservado."
                        )
                        st.rerun()
                else:
                    st.info("Nenhum operador cadastrado.")

            elif menu_admin == "Histórico de Alterações":
                hist = buscar_historico(30)

                if hist:
                    for (
                        data_hora,
                        nome,
                        sem_id,
                        dia,
                        de,
                        para,
                    ) in hist:
                        st.caption(
                            f"**{data_hora}** — {nome} · {dia} "
                            f"({sem_id}): {de} → {para}"
                        )
                else:
                    st.info("Nenhuma alteração registrada ainda.")

            st.divider()

            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.autenticado = False
                st.rerun()


# ============================================================
# NAVEGAÇÃO + BUSCA + EXPORTAÇÃO
# ============================================================
col_prev, col_periodo, col_next, col_busca, col_export = st.columns(
    [0.5, 2, 0.5, 2.3, 0.45],
    gap="small",
)

with col_prev:
    if st.button("◀", use_container_width=True):
        st.session_state.deslocamento_semana -= 1
        st.rerun()

with col_periodo:
    st.markdown(
        f"""
        <div style='background-color:#182238;
        border:1px solid #2A3855;border-radius:8px;
        padding:9px 14px;color:#E7ECF3;
        font-weight:700;text-align:center;'>
        📅 {semana['nome']}
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_next:
    if st.button("▶", use_container_width=True):
        st.session_state.deslocamento_semana += 1
        st.rerun()

with col_busca:
    termo_busca = st.text_input(
        "🔎 Buscar operador",
        placeholder="Nome do operador...",
        label_visibility="collapsed",
    )

operadores = buscar_operadores()

if termo_busca:
    operadores = [
        x for x in operadores
        if termo_busca.strip().upper() in x[1].upper()
    ]

with col_export:
    excel_buffer = gerar_excel(operadores, semana)

    st.download_button(
        label="⬇️",
        data=excel_buffer,
        file_name=f"escala_amazon_{semana_id}.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True,
        help="Exportar escala para Excel",
    )


# ============================================================
# MÉTRICAS
# ============================================================
total = len(operadores)
t1 = len([x for x in operadores if x[3] == "T1"])
t2 = len([x for x in operadores if x[3] == "T2"])
t3 = len([x for x in operadores if x[3] == "T3"])

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-numero'>{total}</div>
            <div class='metric-label'>OPERADORES TOTAL</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m2:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-numero'>{t1}</div>
            <div class='metric-label'>T1 • 07h às 15h</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m3:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-numero'>{t2}</div>
            <div class='metric-label'>T2 • 15h às 23h</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m4:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-numero'>{t3}</div>
            <div class='metric-label'>T3 • 23h às 07h</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# GRID DE TURNOS
# ============================================================
st.write("")

aba_t1, aba_t2, aba_t3 = st.tabs(
    ["Turno 1", "Turno 2", "Turno 3"]
)

abas_mapeamento = {
    "T1": aba_t1,
    "T2": aba_t2,
    "T3": aba_t3,
}

for turno in ["T1", "T2", "T3"]:
    with abas_mapeamento[turno]:
        operadores_turno = ordenar_por_funcao(
            [x for x in operadores if x[3] == turno]
        )

        if not operadores_turno:
            st.info(
                f"Nenhum operador encontrado no "
                f"{NOMES_TURNOS[turno]} para este filtro/período."
            )
            continue

        st.markdown(
            f"""
            <div class='turno-header'>
                <div class='turno-titulo'>
                    🕒 {NOMES_TURNOS[turno]}
                </div>
                <div class='turno-horario'>
                    {HORARIOS[turno]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        headers = st.columns(
            [2.5, 2, 1.8, 1.8, 1.8, 1.8]
        )

        headers[0].markdown(
            "<div class='header-col header-esquerda'>"
            "OPERADOR</div>",
            unsafe_allow_html=True,
        )

        headers[1].markdown(
            "<div class='header-col header-esquerda'>"
            "FUNÇÃO</div>",
            unsafe_allow_html=True,
        )

        for i, (dia, _) in enumerate(DIAS, 2):
            headers[i].markdown(
                f"<div class='header-col'>"
                f"{dia.upper()} ({semana[dia]})</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            "<div class='separador'></div>",
            unsafe_allow_html=True,
        )

        for operador in operadores_turno:
            operador_id = operador[0]
            nome = operador[1]
            funcao = operador[2]

            status = buscar_status(
                operador_id,
                semana_id,
            )

            # Primeira abertura da semana:
            # cria somente o registro daquela escala no Supabase.
            if status is None:
                horario = HORARIOS[turno]
                status = (
                    horario,
                    horario,
                    horario,
                    horario,
                )
                salvar_status(
                    operador_id,
                    semana_id,
                    *status,
                )

            linha = st.columns(
                [2.5, 2, 1.8, 1.8, 1.8, 1.8]
            )

            linha[0].markdown(
                f"<div class='nome-operador'>"
                f"<b>{nome}</b></div>",
                unsafe_allow_html=True,
            )

            linha[1].markdown(
                f"<div class='funcao-operador'>"
                f"{funcao}</div>",
                unsafe_allow_html=True,
            )

            status_lista = list(status)

            for i, (dia, _) in enumerate(DIAS, 2):
                valor = status_lista[i - 2]

                if valor != "FOLGA":
                    linha[i].markdown(
                        f"""
                        <div class='card-trabalho'>
                            {HORARIOS[turno]}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    linha[i].markdown(
                        """
                        <div class='card-folga'>
                            Folga descanso
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if st.session_state.autenticado:
                    novo_valor = (
                        HORARIOS[turno]
                        if valor == "FOLGA"
                        else "FOLGA"
                    )

                    if linha[i].button(
                        "↔ Alterar",
                        key=(
                            f"{operador_id}_"
                            f"{semana_id}_"
                            f"{dia}_"
                            f"{turno}"
                        ),
                        use_container_width=True,
                    ):
                        registrar_historico(
                            operador_id,
                            nome,
                            semana_id,
                            dia,
                            valor,
                            novo_valor,
                        )

                        status_lista[i - 2] = novo_valor

                        salvar_status(
                            operador_id,
                            semana_id,
                            *status_lista,
                        )

                        st.rerun()


# ============================================================
# RODAPÉ
# ============================================================
st.divider()
st.caption(
    "Escala Amazon • Dados persistidos no Supabase/PostgreSQL"
)
