import json
import sqlite3
import re
from datetime import datetime
import streamlit as st
from weasyprint import HTML
from cryptography.fernet import Fernet

st.set_page_config(page_title="Portal de Holerites", page_icon="📑", layout="centered")

# --- CONTROLE DE SESSÃO (LOGIN) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.dados_func = None

# --- BANCO DE DADOS LOCAL (SQLite) ---
def init_db():
    conn = sqlite3.connect("status_holerites.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS respostas (
            cpf TEXT,
            competencia TEXT,
            status TEXT,
            motivo_contestacao TEXT,
            data_registro TEXT,
            PRIMARY KEY (cpf, competencia)
        )
    """)
    conn.commit()
    conn.close()

def salvar_resposta(cpf: str, competencia: str, status: str, motivo: str = ""):
    conn = sqlite3.connect("status_holerites.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO respostas (cpf, competencia, status, motivo_contestacao, data_registro)
        VALUES (?, ?, ?, ?, ?)
    """, (cpf, competencia, status, motivo, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def obter_status(cpf: str, competencia: str):
    conn = sqlite3.connect("status_holerites.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, motivo_contestacao FROM respostas WHERE cpf = ? AND competencia = ?", (cpf, competencia))
    res = cursor.fetchone()
    conn.close()
    return res

init_db()

# --- FUNÇÕES DE APOIO ---
def limpar_numeros(texto: str) -> str:
    return re.sub(r"\D", "", str(texto))

def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- GERADOR DE PDF DINÂMICO ---
def gerar_pdf_holerite(dados_func):
    proventos_html = ""
    descontos_html = ""
    proventos_tot = 0.0
    descontos_tot = 0.0
    
    for v in dados_func["verbas"]:
        if v["tipo"] == "provento":
            proventos_html += f"""
            <tr>
                <td>{v['descricao']}</td>
                <td style='text-align: right; color: #065f46;'>{formatar_moeda(v['valor'])}</td>
            </tr>
            """
            proventos_tot += v["valor"]
        elif v["tipo"] == "desconto":
            descontos_html += f"""
            <tr>
                <td>{v['descricao']}</td>
                <td style='text-align: right; color: #991b1b;'>{formatar_moeda(v['valor'])}</td>
            </tr>
            """
            descontos_tot += v["valor"]
            
    liquido = proventos_tot - descontos_tot

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      @page {{ size: A4; margin: 15mm; background-color: #ffffff; }}
      body {{ font-family: Helvetica, sans-serif; font-size: 10pt; color: #111827; }}
      .header {{ width: 100%; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 15px; }}
      .info-box {{ width: 100%; margin-bottom: 15px; }}
      table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; border: 1px solid #000; }}
      th {{ background-color: #f3f4f6; color: #000; padding: 8px; font-size: 9pt; text-transform: uppercase; text-align: left; border-bottom: 1px solid #000; font-weight: bold; }}
      td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; font-size: 9.5pt; }}
      .totals-row td {{ font-weight: bold; background-color: #f9fafb; border-top: 1px solid #000; border-bottom: none; }}
      .liquido-box {{ width: 100%; border: 1px solid #000; background-color: #e5e7eb; padding: 12px 8px; font-weight: bold; font-size: 11pt; margin-top: 10px; }}
      .liquido-table {{ width: 100%; border: none; margin: 0; }}
      .liquido-table td {{ border: none; padding: 0; font-size: 12pt; }}
    </style>
    </head>
    <body>
      <div class="header">
        <h2 style="margin:0;">{dados_func['empresa']}</h2>
        <p style="margin:2px 0 0 0;">RECIBO DE PAGAMENTO - Competência: {dados_func['competencia']}</p>
      </div>
      
      <div class="info-box">
        <strong>Funcionário:</strong> {dados_func['nome']} <br>
        <strong>Cargo:</strong> {dados_func['cargo']} <br>
        <strong>CPF:</strong> {dados_func['cpf']} | <strong>Chave PIX:</strong> {dados_func.get('pix', 'Não cadastrada')}
      </div>
      
      <!-- TABELA PROVENTOS -->
      <table>
        <thead>
          <tr>
            <th style="width:70%;">DESCRIÇÃO DOS PROVENTOS</th>
            <th style="width:30%; text-align:right;">VALOR</th>
          </tr>
        </thead>
        <tbody>
          {proventos_html}
          <tr class="totals-row">
            <td style="text-align: right;">TOTAL PROVENTOS:</td>
            <td style="text-align: right;">{formatar_moeda(proventos_tot)}</td>
          </tr>
        </tbody>
      </table>

      <!-- TABELA DESCONTOS -->
      <table>
        <thead>
          <tr>
            <th style="width:70%;">DESCRIÇÃO DOS DESCONTOS</th>
            <th style="width:30%; text-align:right;">VALOR</th>
          </tr>
        </thead>
        <tbody>
          {descontos_html}
          <tr class="totals-row">
            <td style="text-align: right;">TOTAL DESCONTOS:</td>
            <td style="text-align: right;">{formatar_moeda(descontos_tot)}</td>
          </tr>
        </tbody>
      </table>

      <!-- VALOR LÍQUIDO -->
      <div class="liquido-box">
        <table class="liquido-table">
            <tr>
                <td style="text-align: left; text-transform: uppercase;">VALOR LÍQUIDO A RECEBER:</td>
                <td style="text-align: right;">{formatar_moeda(liquido)}</td>
            </tr>
        </table>
      </div>
      
      <div style="text-align: center; margin-top: 20px;">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=100x100&data={dados_func.get('pix', '')}" alt="QR Code PIX">
        <p style="font-size: 8pt; font-weight: bold;">CHAVE PIX: {dados_func.get('pix', '')}</p>
      </div>
    </body>
    </html>
    """
    return HTML(string=html_content).write_pdf()


# =====================================================================
# INTERFACE PRINCIPAL
# =====================================================================

if not st.session_state.autenticado:
    # --- TELA 1: LOGIN ---
    st.title("📄 Portal de Holerites")
    st.write("Insira seus dados para acessar o demonstrativo de pagamento.")

    with st.form("login_form"):
        cpf_input = st.text_input("CPF:", max_chars=11, placeholder="Digite apenas os 11 números", help="Não precisa colocar pontos ou traços.")
        dt_nasc_input = st.text_input("Data de Nascimento:", max_chars=8, placeholder="DDMMAAAA (Apenas números)", help="Exemplo: Para 21/03/1991, digite 21031991")
        submitted = st.form_submit_button("Consultar Holerite", use_container_width=True)

    if submitted:
        cpf_limpo = limpar_numeros(cpf_input)
        if len(cpf_limpo) != 11:
            st.error("Por favor, insira um CPF válido com 11 dígitos.")
            st.stop()

        try:
            # Lê o arquivo criptografado
            with open("dados_folha.enc", "rb") as arquivo:
                dados_cifrados = arquivo.read()
            
            # Puxa a chave mestra dos "Secrets" do painel do Streamlit Cloud
            chave_secreta = st.secrets["CHAVE_CRIPTO"]
            f = Fernet(chave_secreta)
            
            # Descriptografa e carrega o JSON em memória
            json_descriptografado = f.decrypt(dados_cifrados).decode('utf-8')
            base_folha = json.loads(json_descriptografado)
            
        except Exception as e:
            st.error("Falha de segurança ou arquivo de dados não encontrado (dados_folha.enc).")
            st.stop()

        func_encontrado = None
        for item in base_folha:
            if item["cpf"] == cpf_limpo:
                dt_json = item.get("data_nascimento", "")
                if "-" in dt_json and len(dt_json) >= 10:
                    partes = dt_json[:10].split("-")
                    dt_json_comparacao = partes[2] + partes[1] + partes[0] if len(partes) == 3 else limpar_numeros(dt_json)
                else:
                    dt_json_comparacao = limpar_numeros(dt_json)
                    
                if dt_json_comparacao == limpar_numeros(dt_nasc_input):
                    func_encontrado = item
                    break

        if not func_encontrado:
            st.error("❌ Dados incorretos ou holerite não disponível para este CPF/Data de Nascimento.")
        else:
            st.session_state.autenticado = True
            st.session_state.dados_func = func_encontrado
            st.rerun()

else:
    # --- TELA 2: VISUALIZAÇÃO DO HOLERITE ---
    func_dados = st.session_state.dados_func
    status_atual = obter_status(func_dados["cpf"], func_dados["competencia"])
    
    col_titulo, col_sair = st.columns([4, 1], vertical_alignment="center")
    col_titulo.title(f"Holerite - {func_dados['competencia']}")
    if col_sair.button("🚪 Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.dados_func = None
        st.rerun()
    
    st.write(f"**Funcionário:** {func_dados['nome']}")
    st.write(f"**Cargo:** {func_dados['cargo']}")
    st.write(f"**PIX Cadastrado:** {func_dados.get('pix', 'Não cadastrada')}")
    
    # Processamento e segregação das verbas
    proventos_list = [v for v in func_dados["verbas"] if v["tipo"] == "provento"]
    descontos_list = [v for v in func_dados["verbas"] if v["tipo"] == "desconto"]
    
    proventos = sum(v["valor"] for v in proventos_list)
    descontos = sum(v["valor"] for v in descontos_list)
    liquido = proventos - descontos

    st.markdown("<br>", unsafe_allow_html=True)
    
    # RENDERIZAÇÃO: PROVENTOS (Efeito Zebra e Cabeçalho Verde)
    st.markdown("### <span style='color: #2ecc71;'>Proventos</span>", unsafe_allow_html=True)
    for i, v in enumerate(proventos_list):
        bg_color = "rgba(128, 128, 128, 0.08)" if i % 2 == 0 else "transparent"
        st.markdown(
            f"<div style='background-color: {bg_color}; padding: 10px 12px; border-radius: 4px; display: flex; justify-content: space-between;'>"
            f"<span>{v['descricao']}</span>"
            f"<span>{formatar_moeda(v['valor'])}</span>"
            f"</div>", 
            unsafe_allow_html=True
        )
    st.markdown(
        f"<div style='text-align: right; font-weight: bold; font-size: 1.15em; padding: 12px 12px 0 0;'>"
        f"Total Proventos: {formatar_moeda(proventos)}</div>", 
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # RENDERIZAÇÃO: DESCONTOS (Efeito Zebra e Cabeçalho Vermelho)
    st.markdown("### <span style='color: #e74c3c;'>Descontos</span>", unsafe_allow_html=True)
    for i, v in enumerate(descontos_list):
        bg_color = "rgba(128, 128, 128, 0.08)" if i % 2 == 0 else "transparent"
        st.markdown(
            f"<div style='background-color: {bg_color}; padding: 10px 12px; border-radius: 4px; display: flex; justify-content: space-between;'>"
            f"<span>{v['descricao']}</span>"
            f"<span>{formatar_moeda(v['valor'])}</span>"
            f"</div>", 
            unsafe_allow_html=True
        )
    st.markdown(
        f"<div style='text-align: right; font-weight: bold; font-size: 1.15em; padding: 12px 12px 0 0;'>"
        f"Total Descontos: {formatar_moeda(descontos)}</div>", 
        unsafe_allow_html=True
    )

    st.markdown("---")
    
    # RENDERIZAÇÃO: LÍQUIDO EM DESTAQUE LIMPO
    st.markdown(f"""
    <div style="text-align: center; margin: 15px 0;">
        <div style="font-size: 1rem; text-transform: uppercase; opacity: 0.8;">Valor Líquido a Receber</div>
        <div style="font-size: 2.3rem; font-weight: bold; margin-top: 5px;">{formatar_moeda(liquido)}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    # --- LÓGICA DE VALIDAÇÃO E DOWNLOAD ---
    if status_atual and status_atual[0] == "Em Revisão":
        st.error(f"⚠️ **Pedido de Revisão Registrado**\n\nMotivo: {status_atual[1]}\n\nAguarde o retorno do RH.")
        
    elif status_atual and status_atual[0] == "Aprovado":
        st.success("✅ Recibo validado eletronicamente.")
        pdf_bytes = gerar_pdf_holerite(func_dados)
        st.download_button(
            label="📥 Baixar PDF do Holerite",
            data=pdf_bytes,
            file_name=f"Holerite_{func_dados['competencia'].replace('/', '_')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
        
    else:
        st.info("Valide os valores acima para liberar o download do seu holerite.")
        col_aprov, col_revis = st.columns(2)

        with col_aprov:
            if st.button("✅ Confirmar Valores", use_container_width=True, type="primary"):
                salvar_resposta(func_dados["cpf"], func_dados["competencia"], "Aprovado")
                st.rerun()

        with col_revis:
            with st.popover("❌ Solicitar Revisão", use_container_width=True):
                motivo = st.text_area("Descreva a divergência encontrada:")
                if st.button("Enviar"):
                    if motivo.strip():
                        salvar_resposta(func_dados["cpf"], func_dados["competencia"], "Em Revisão", motivo)
                        st.rerun()
                    else:
                        st.warning("Descreva o motivo antes de enviar.")
