import json
import sqlite3
import re
from datetime import datetime
import streamlit as st
from weasyprint import HTML

# Configuração da página
st.set_page_config(page_title="Portal de Holerites", page_icon="📑", layout="centered")

# --- CONTROLE DE SESSÃO (LOGIN) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.dados_func = None

# --- BANCO DE DADOS LOCAL (SQLite) PARA RESPOSTAS ---
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
    """Remove caracteres não numéricos."""
    return re.sub(r"\D", "", str(texto))

def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- GERADOR DE PDF DINÂMICO ---
def gerar_pdf_holerite(dados_func):
    proventos_html = ""
    descontos_html = ""
    proventos_tot = 0.0
    descontos_tot = 0.0
    
    # Separação das verbas
    for v in dados_func["verbas"]:
        if v["tipo"] == "provento":
            proventos_html += f"""
            <tr>
                <td>{v['descricao']}</td>
                <td style='text-align: right; color: #065f46;'>{formatar_moeda(v['valor'])}</td>
            </tr>
            """
            proventos_tot += v["valor"]
        else:
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
      .header {{ width: 100%; border-bottom: 2px solid #1e3a8a; padding-bottom: 8px; margin-bottom: 12px; }}
      .info-box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; margin-bottom: 14px; border-radius: 4px; }}
      table {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; border: 1px solid #000; }}
      th {{ background-color: #f3f4f6; color: #000; padding: 6px; font-size: 9pt; text-transform: uppercase; text-align: left; border-bottom: 1px solid #000; font-weight: bold; }}
      td {{ padding: 6px; border-bottom: 1px solid #e5e7eb; font-size: 9pt; }}
      .totals-row td {{ font-weight: bold; background-color: #f9fafb; border-top: 1px solid #000; }}
      .liquido-box {{ width: 100%; border: 1px solid #000; background-color: #e5e7eb; padding: 10px; font-weight: bold; font-size: 11pt; margin-top: 10px; }}
      .liquido-table {{ width: 100%; border: none; margin: 0; }}
      .liquido-table td {{ border: none; padding: 0; font-size: 12pt; }}
    </style>
    </head>
    <body>
      <div class="header">
        <h2 style="margin:0; color:#1e3a8a;">{dados_func['empresa']}</h2>
        <p style="margin:2px 0 0 0; color:#4b5563;">RECIBO DE PAGAMENTO - Competência: {dados_func['competencia']}</p>
      </div>
      <div class="info-box">
        <strong>Funcionário:</strong> {dados_func['nome']} | <strong>CPF:</strong> {dados_func['cpf']}<br>
        <strong>Cargo:</strong> {dados_func['cargo']} <br>
        <strong>Chave PIX:</strong> {dados_func.get('pix', 'Não cadastrada')} ({dados_func.get('tipo_pix', '')})
      </div>
      
      <!-- TABELA DE PROVENTOS -->
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

      <!-- TABELA DE DESCONTOS -->
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
                <td style="text-align: left;">VALOR LÍQUIDO A RECEBER:</td>
                <td style="text-align: right;">{formatar_moeda(liquido)}</td>
            </tr>
        </table>
      </div>

      <p style="font-size: 8pt; text-align: center; color: #64748b; margin-top: 30px;">
        Documento validado eletronicamente pelo funcionário via portal.
      </p>
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
            with open("dados_folha.json", "r", encoding="utf-8") as f:
                base_folha = json.load(f)
        except FileNotFoundError:
            st.error("Base de dados de folha não encontrada (dados_folha.json).")
            st.stop()

        # Busca e validação
        func_encontrado = None
        for item in base_folha:
            if item["cpf"] == cpf_limpo:
                dt_json = item.get("data_nascimento", "")
                
                if "-" in dt_json and len(dt_json) >= 10:
                    partes = dt_json[:10].split("-")
                    if len(partes) == 3:
                        dt_json_comparacao = partes[2] + partes[1] + partes[0]
                    else:
                        dt_json_comparacao = limpar_numeros(dt_json)
                else:
                    dt_json_comparacao = limpar_numeros(dt_json)
                    
                if dt_json_comparacao == limpar_numeros(dt_nasc_input):
                    func_encontrado = item
                    break

        if not func_encontrado:
            st.error("❌ Dados incorretos ou holerite não disponível para este CPF/Data de Nascimento.")
        else:
            # Login com sucesso! Altera o state e reinicia a tela
            st.session_state.autenticado = True
            st.session_state.dados_func = func_encontrado
            st.rerun()

else:
    # --- TELA 2: VISUALIZAÇÃO DO HOLERITE ---
    func_dados = st.session_state.dados_func
    
    col_titulo, col_sair = st.columns([4, 1], vertical_alignment="center")
    col_titulo.title(f"Holerite - {func_dados['competencia']}")
    if col_sair.button("🚪 Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.dados_func = None
        st.rerun()
    
    # Verifica o status no banco local
    status_atual = obter_status(func_dados["cpf"], func_dados["competencia"])

    st.write(f"**Funcionário:** {func_dados['nome']}")
    st.write(f"**Cargo:** {func_dados['cargo']}")
    st.write(f"**PIX Cadastrado:** {func_dados.get('pix', 'Não cadastrada')} ({func_dados.get('tipo_pix', '')})")
    
    proventos = sum(v["valor"] for v in func_dados["verbas"] if v["tipo"] == "provento")
    descontos = sum(v["valor"] for v in func_dados["verbas"] if v["tipo"] == "desconto")
    liquido = proventos - descontos

    # Renderização das Verbas na Interface
    st.markdown("---")
    st.markdown("### 📋 Detalhamento das Verbas")
    
    for v in func_dados["verbas"]:
        c1, c2, c3 = st.columns([4, 2, 3])
        c1.write(v['descricao'])
        c2.write(f"_{v['ref']}_")
        if v["tipo"] == "provento":
            c3.markdown(f"<span style='color:green;'>+ {formatar_moeda(v['valor'])}</span>", unsafe_allow_html=True)
        else:
            c3.markdown(f"<span style='color:red;'>- {formatar_moeda(v['valor'])}</span>", unsafe_allow_html=True)

    st.markdown("---")
    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Proventos", formatar_moeda(proventos))
    col_t2.metric("Descontos", formatar_moeda(descontos))
    col_t3.metric("A RECEBER", formatar_moeda(liquido))
    st.markdown("---")

    # Lógica Condicional de Validação e Download
    if status_atual and status_atual[0] == "Em Revisão":
        st.error(f"⚠️ Você solicitou a revisão deste holerite. Aguarde o contato do RH.\n\n**Motivo registrado:** {status_atual[1]}")
    
    elif status_atual and status_atual[0] == "Aprovado":
        st.success("✅ Documento validado eletronicamente!")
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
        st.write("### Validação Pendente")
        st.info("Por favor, confirme se os valores acima estão corretos para liberar o PDF do seu holerite.")
        
        col_aprov, col_revis = st.columns(2)

        with col_aprov:
            if st.button("✅ Validar e Aprovar", use_container_width=True, type="primary"):
                salvar_resposta(func_dados["cpf"], func_dados["competencia"], "Aprovado")
                st.rerun()

        with col_revis:
            with st.popover("❌ Solicitar Revisão do RH", use_container_width=True):
                motivo = st.text_area("Descreva o motivo (ex: horas extras faltando):")
                if st.button("Enviar Pedido"):
                    if motivo.strip():
                        salvar_resposta(func_dados["cpf"], func_dados["competencia"], "Em Revisão", motivo)
                        st.rerun()
                    else:
                        st.warning("Descreva o motivo antes de enviar.")
