import json
import sqlite3
import re
from datetime import datetime
import streamlit as st
from weasyprint import HTML

# Configuração da página
st.set_page_config(page_title="Portal de Holerites", page_icon="📑", layout="centered")

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
    rows_html = ""
    proventos_tot = 0.0
    descontos_tot = 0.0
    
    for v in dados_func["verbas"]:
        if v["tipo"] == "provento":
            val_html = f"<td style='text-align: right; color: #065f46;'>{formatar_moeda(v['valor'])}</td><td style='text-align: right;'>-</td>"
            proventos_tot += v["valor"]
        else:
            val_html = f"<td style='text-align: right;'>-</td><td style='text-align: right; color: #991b1b;'>{formatar_moeda(v['valor'])}</td>"
            descontos_tot += v["valor"]
            
        rows_html += f"""
        <tr>
            <td>{v['descricao']}</td>
            <td style="text-align: center;">{v['ref']}</td>
            {val_html}
        </tr>
        """
    
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
      table {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; }}
      th {{ background-color: #1e3a8a; color: white; padding: 6px; font-size: 8.5pt; text-transform: uppercase; text-align: left; }}
      td {{ padding: 6px; border-bottom: 1px solid #e5e7eb; font-size: 9pt; }}
      .totals td {{ font-weight: bold; padding: 8px; border: 1px solid #cbd5e1; font-size: 10pt; }}
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
      <table>
        <thead>
          <tr>
            <th style="width:50%;">Descrição</th>
            <th style="width:10%; text-align:center;">Ref.</th>
            <th style="width:20%; text-align:right;">Proventos</th>
            <th style="width:20%; text-align:right;">Descontos</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
      <table class="totals">
        <tr>
          <td style="background:#ecfdf5; color:#065f46;">Tot. Proventos: {formatar_moeda(proventos_tot)}</td>
          <td style="background:#fef2f2; color:#991b1b;">Tot. Descontos: {formatar_moeda(descontos_tot)}</td>
          <td style="background:#eff6ff; color:#1e40af;">VALOR LÍQUIDO: {formatar_moeda(liquido)}</td>
        </tr>
      </table>
      <p style="font-size: 8pt; text-align: center; color: #64748b; margin-top: 30px;">
        Documento validado eletronicamente pelo funcionário via portal.
      </p>
    </body>
    </html>
    """
    return HTML(string=html_content).write_pdf()

# --- INTERFACE ---
st.title("📄 Portal de Holerites")
st.write("Insira seus dados para acessar o demonstrativo de pagamento.")

# Formulário de Login Duplo
with st.form("login_form"):
    cpf_input = st.text_input("CPF (Apenas números):", max_chars=14)
    dt_nasc_input = st.text_input("Data de Nascimento (DD/MM/AAAA):", max_chars=10)
    submitted = st.form_submit_button("Consultar Holerite")

if submitted:
    cpf_limpo = limpar_numeros(cpf_input)
    
    if len(cpf_limpo) != 11:
        st.error("Por favor, insira um CPF válido com 11 dígitos.")
        st.stop()

    # Carrega a base JSON gerada pelo sistema local
    try:
        with open("dados_folha.json", "r", encoding="utf-8") as f:
            base_folha = json.load(f)
    except FileNotFoundError:
        st.error("Base de dados de folha não encontrada (dados_folha.json).")
        st.stop()

    # Busca o funcionário pelo CPF e valida a Data de Nascimento
    func_dados = None
    for item in base_folha:
        if item["cpf"] == cpf_limpo:
            # Validação simples da data de nascimento (ignorando pontuações)
            if limpar_numeros(item.get("data_nascimento", "")) == limpar_numeros(dt_nasc_input):
                func_dados = item
                break

    if not func_dados:
        st.error("❌ Dados incorretos ou holerite não disponível para este CPF/Data de Nascimento.")
    else:
        st.success("✅ Autenticação realizada com sucesso.")
        
        status_atual = obter_status(func_dados["cpf"], func_dados["competencia"])

        if status_atual and status_atual[0] == "Em Revisão":
            st.error(f"⚠️ Você já solicitou a revisão deste holerite. Aguarde o contato do RH.\n\n**Motivo registrado:** {status_atual[1]}")
        else:
            st.markdown("---")
            st.subheader(f"Holerite - {func_dados['competencia']}")
            st.write(f"**Cargo:** {func_dados['cargo']}")
            
            # Cálculo para a interface
            proventos = sum(v["valor"] for v in func_dados["verbas"] if v["tipo"] == "provento")
            descontos = sum(v["valor"] for v in func_dados["verbas"] if v["tipo"] == "desconto")
            liquido = proventos - descontos

            # Renderização das Verbas
            st.markdown("### 📋 Detalhamento")
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
            st.write("### Validação")
            
            # Botões de Ação
            col_aprov, col_revis = st.columns(2)

            with col_aprov:
                pdf_bytes = gerar_pdf_holerite(func_dados)
                if st.download_button(
                    label="✅ Concordo e Baixar PDF",
                    data=pdf_bytes,
                    file_name=f"Holerite_{func_dados['competencia'].replace('/', '_')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                ):
                    salvar_resposta(func_dados["cpf"], func_dados["competencia"], "Aprovado")
                    st.toast("Holerite aprovado!")

            with col_revis:
                with st.popover("❌ Solicitar Revisão do RH", use_container_width=True):
                    motivo = st.text_area("Descreva o motivo (ex: horas extras faltando):")
                    if st.button("Enviar Pedido"):
                        if motivo.strip():
                            salvar_resposta(func_dados["cpf"], func_dados["competencia"], "Em Revisão", motivo)
                            st.rerun()
                        else:
                            st.warning("Descreva o motivo antes de enviar.")