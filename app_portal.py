import json
import re
import os
import hashlib
from datetime import datetime, date
import pandas as pd
import streamlit as st
from weasyprint import HTML
from cryptography.fernet import Fernet
from num2words import num2words
import base64
from supabase import create_client, Client
import glob

st.set_page_config(page_title="Holerite - MedTem", page_icon="logo.png", layout="centered")

# --- CONTROLE DE SESSÃO ---
if "user_type" not in st.session_state:
    st.session_state.user_type = None
    st.session_state.dados_func = None
    st.session_state.hash_arquivo = None

# --- BANCO DE DADOS EM NUVEM (Supabase) ---
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

def salvar_resposta(cpf: str, nome: str, competencia: str, status: str, hash_arquivo: str):
    supabase.table("respostas").upsert({
        "cpf": cpf,
        "nome": nome,
        "competencia": competencia,
        "status": status,
        "hash_arquivo": hash_arquivo,
        "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }).execute()

def obter_status(cpf: str, competencia: str, hash_atual: str):
    resposta = supabase.table("respostas").select("status, hash_arquivo").eq("cpf", cpf).eq("competencia", competencia).execute()
    
    if len(resposta.data) > 0:
        banco_hash = resposta.data[0].get("hash_arquivo")
        banco_status = resposta.data[0].get("status")
        
        # Se o hash do arquivo mudou, a aprovação antiga é invalidada (retorna None)
        if banco_hash != hash_atual:
            return None
        return banco_status
        
    return None

# --- FUNÇÕES DE APOIO ---
def limpar_numeros(texto: str) -> str:
    return re.sub(r"\D", "", str(texto))

def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_hash_arquivo(caminho_arquivo: str) -> str:
    """Gera uma assinatura MD5 única para o arquivo. Se o conteúdo mudar, o hash muda."""
    hasher = hashlib.md5()
    with open(caminho_arquivo, 'rb') as afile:
        buf = afile.read()
        hasher.update(buf)
    return hasher.hexdigest()

# --- GERADOR DE PDF DINÂMICO ---
def gerar_pdf_holerite(dados_func):
    proventos_html = ""
    descontos_html = ""
    proventos_tot = 0.0
    descontos_tot = 0.0
    
    for v in dados_func["verbas"]:
        if v["tipo"] == "provento":
            proventos_html += f"<tr><td>{v['descricao']}</td><td style='text-align: right;'>{formatar_moeda(v['valor'])}</td></tr>"
            proventos_tot += v["valor"]
        elif v["tipo"] == "desconto":
            descontos_html += f"<tr><td>{v['descricao']}</td><td style='text-align: right;'>{formatar_moeda(v['valor'])}</td></tr>"
            descontos_tot += v["valor"]
            
    liquido = proventos_tot - descontos_tot

    try:
        extenso = num2words(liquido, lang='pt_BR', to='currency').upper()
    except Exception:
        extenso = ""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      @page {{ size: A4; margin: 15mm; background-color: #ffffff; }}
      body {{ font-family: Helvetica, sans-serif; font-size: 10pt; color: #111827; }}
      .header {{ width: 100%; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 15px; }}
      .info-box {{ width: 100%; margin-bottom: 20px; line-height: 1.6; font-size: 10.5pt; }}
      table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; border: 1px solid #000; }}
      th {{ background-color: #f3f4f6; color: #000; padding: 8px; font-size: 9pt; text-transform: uppercase; text-align: left; border-bottom: 1px solid #000; font-weight: bold; }}
      td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; font-size: 9.5pt; }}
      .totals-row td {{ font-weight: bold; background-color: #f9fafb; border-top: 1px solid #000; border-bottom: none; }}
      .total-prov {{ color: #065f46; }}
      .total-desc {{ color: #991b1b; }}
      .liquido-box {{ width: 100%; border: 1px solid #000; background-color: #e5e7eb; padding: 12px; box-sizing: border-box; margin-top: 10px; }}
      .liquido-header {{ font-weight: bold; font-size: 11pt; }}
      .liquido-extenso {{ font-size: 8.5pt; font-weight: normal; margin-top: 6px; text-transform: uppercase; color: #4b5563; padding-left: 2px; }}
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
        <strong>CPF:</strong> {dados_func['cpf']} <br>
        <strong>Chave PIX:</strong> {dados_func.get('pix', 'Não cadastrada')}
      </div>
      
      <table>
        <thead>
          <tr><th style="width:70%;">DESCRIÇÃO DOS PROVENTOS</th><th style="width:30%; text-align:right;">VALOR</th></tr>
        </thead>
        <tbody>
          {proventos_html}
          <tr class="totals-row">
            <td class="total-prov" style="text-align: right;">TOTAL PROVENTOS:</td>
            <td class="total-prov" style="text-align: right;">{formatar_moeda(proventos_tot)}</td>
          </tr>
        </tbody>
      </table>

      <table>
        <thead>
          <tr><th style="width:70%;">DESCRIÇÃO DOS DESCONTOS</th><th style="width:30%; text-align:right;">VALOR</th></tr>
        </thead>
        <tbody>
          {descontos_html}
          <tr class="totals-row">
            <td class="total-desc" style="text-align: right;">TOTAL DESCONTOS:</td>
            <td class="total-desc" style="text-align: right;">{formatar_moeda(descontos_tot)}</td>
          </tr>
        </tbody>
      </table>

      <div class="liquido-box">
        <div class="liquido-header">
            <span style="float: left; text-transform: uppercase;">VALOR LÍQUIDO A RECEBER:</span>
            <span style="float: right;">{formatar_moeda(liquido)}</span>
            <div style="clear: both;"></div>
        </div>
      </div>
      
      <div class="liquido-extenso">
          ({extenso})
      </div>
    </body>
    </html>
    """
    return HTML(string=html_content).write_pdf()

# =====================================================================
# INTERFACE PRINCIPAL
# =====================================================================

if st.session_state.user_type is None:
    # --- TELA 1: LOGIN ---
    try:
        with open("logo.png", "rb") as image_file:
            logo_b64 = base64.b64encode(image_file.read()).decode()
        img_html = f'<img src="data:image/png;base64,{logo_b64}" width="55">'
    except Exception:
        img_html = '📄' 

    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 25px;">
        {img_html}
        <h1 style="margin: 10px 0 5px 0; padding: 0; line-height: 1.1; font-size: 2.2rem;">Holerite - MedTem</h1>
        <p style="color: #d1d5db; margin: 0; padding: 0; font-size: 1rem; line-height: 1.4;">
            Insira seus dados para acessar o demonstrativo de pagamento.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Listas de referência para os filtros
    MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    # --- Lógica do Mês Anterior ---
    hoje = date.today()
    if hoje.month == 1:
        mes_padrao = 12
        ano_padrao = hoje.year - 1
    else:
        mes_padrao = hoje.month - 1
        ano_padrao = hoje.year
        
    # Garante que o ano não quebre caso passe do limite estabelecido
    indice_ano = ano_padrao - 2024
    if indice_ano < 0: indice_ano = 0
    if indice_ano > 6: indice_ano = 6 # (2030 - 2024 = 6)

    with st.form("login_form"):
        cpf_input = st.text_input("CPF:", help="Não precisa colocar pontos ou traços.").strip()
        dt_nasc_input = st.text_input("Data de Nascimento (DDMMAAAA):", help="Exemplo: Para 21/03/1991, digite 21031991", type="password").strip()
        
        # Caixas de seleção já iniciam no mês e ano anteriores
        col_m, col_a = st.columns(2)
        mes_input = col_m.selectbox("Mês Referência", MESES, index=mes_padrao-1)
        ano_input = col_a.selectbox("Ano Referência", range(2024, 2036), index=indice_ano)
        
        submitted = st.form_submit_button("Consultar", type="primary", use_container_width=True)

    if submitted:
        # ROTA ADMIN
        if cpf_input.lower() == "admin" and dt_nasc_input == "1234":
            st.session_state.user_type = "admin"
            st.rerun()
            
        # ROTA FUNCIONÁRIO
        cpf_limpo = limpar_numeros(cpf_input)
        
        competencia_arquivo = f"{mes_padrao:02d}{ano_input}"
        
        # O asterisco (*) ignora o prefixo da empresa na busca
        busca = glob.glob(f"arquivos/*_{cpf_limpo}_{competencia_arquivo}.enc")
        
        if not busca:
            st.error(f"❌ Documento não encontrado para a competência {mes_padrao:02d}/{ano_input}. Verifique se a data está correta.")
        else:
            arquivo_enc = busca[0] # Pega o arquivo exato que encontrou
            try:
                # Restante do código de descriptografia e hash permanece igualzinho...
                meu_hash = gerar_hash_arquivo(arquivo_enc)
                
                with open(arquivo_enc, "rb") as arquivo:
                    dados_cifrados = arquivo.read()
                
                chave_secreta = st.secrets["CHAVE_CRIPTO"]
                f = Fernet(chave_secreta)
                json_descriptografado = f.decrypt(dados_cifrados).decode('utf-8')
                func_encontrado = json.loads(json_descriptografado)
                
                dt_json_cru = str(func_encontrado.get("data_nascimento", ""))
                dt_json_somente_data = dt_json_cru[:10]
                nums_json = limpar_numeros(dt_json_somente_data)
                
                if len(nums_json) == 8 and (nums_json.startswith("19") or nums_json.startswith("20")):
                    dt_json_comparacao = nums_json[6:8] + nums_json[4:6] + nums_json[0:4]
                else:
                    dt_json_comparacao = nums_json
                    
                if dt_json_comparacao == limpar_numeros(dt_nasc_input):
                    st.session_state.user_type = "employee"
                    st.session_state.dados_func = func_encontrado
                    st.session_state.hash_arquivo = meu_hash
                    st.rerun()
                else:
                    st.error("❌ Data de Nascimento incorreta.")
                    
            except Exception as e:
                st.error(f"Erro ao processar o arquivo seguro: {repr(e)}")


elif st.session_state.user_type == "admin":
    # --- TELA 2: PAINEL ADMINISTRATIVO ---
    col_titulo, col_sair = st.columns([4, 1], vertical_alignment="center")
    col_titulo.title("🛡️ Painel Admin")
    if col_sair.button("🚪 Sair", use_container_width=True):
        st.session_state.user_type = None
        st.rerun()
        
    try:
        dic_empresas = {
            "A": "DROGARIA PRIMEIRO PASSO",
            "B": "DROGARIA TERCEIRO PASSO",
            "C": "DROGARIA QUARTO PASSO"
        }
        
        # 1. Busca todos os arquivos gerados no GitHub
        import glob
        todos_arquivos = glob.glob("arquivos/*.enc")
        
        # Extrai as competências únicas do nome dos arquivos para criar o filtro
        competencias_disponiveis = set()
        for arq in todos_arquivos:
            partes = os.path.basename(arq).replace(".enc", "").split("_")
            if len(partes) >= 3:
                competencias_disponiveis.add(partes[2])
                
        lista_comps = sorted(list(competencias_disponiveis), reverse=True)
        
        if not lista_comps:
            st.info("Nenhum arquivo de holerite encontrado na pasta 'arquivos'.")
        else:
            # Filtros na tela
            c_filt1, c_filt2 = st.columns(2)
            filtro_comp = c_filt1.selectbox("📅 Filtrar Competência", lista_comps)
            
            lista_empresas = ["TODAS"] + list(dic_empresas.values())
            filtro_empresa = c_filt2.selectbox("🏢 Filtrar Empresa", lista_empresas)
            
            # Formata a competência para cruzar com o banco (ex: 082026 -> Agosto/2026)
            MESES_NOME = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            mes_banco = MESES_NOME[int(filtro_comp[:2]) - 1]
            comp_formatada_banco = f"{mes_banco}/{filtro_comp[2:]}"
            
            # 2. Busca respostas no Supabase
            resposta_db = supabase.table("respostas").select("*").eq("competencia", comp_formatada_banco).execute()
            supa_dict = {r["cpf"]: r for r in resposta_db.data} # Transforma em dicionário rápido
            
            # 3. Monta os dados cruzando arquivos físicos com o banco
            chave_secreta = st.secrets["CHAVE_CRIPTO"]
            f_crypto = Fernet(chave_secreta)
            dados_painel = []
            
            # Filtra apenas os arquivos do mês selecionado para não sobrecarregar a memória
            arquivos_filtrados = [a for a in todos_arquivos if a.endswith(f"_{filtro_comp}.enc")]
            
            for arq in arquivos_filtrados:
                partes = os.path.basename(arq).replace(".enc", "").split("_")
                if len(partes) < 3: continue
                
                pref, cpf_arq, comp_arq = partes[0], partes[1], partes[2]
                empresa_nome = dic_empresas.get(pref, "Outra Empresa")
                
                if filtro_empresa != "TODAS" and empresa_nome != filtro_empresa:
                    continue
                    
                supa_reg = supa_dict.get(cpf_arq)
                
                if supa_reg:
                    status = supa_reg["status"]
                    nome = supa_reg["nome"]
                    data_reg = supa_reg["data_registro"]
                else:
                    # Se não tá no banco, é Pendente. Abre o arquivo para extrair o Nome.
                    status = "Pendente"
                    data_reg = "-"
                    try:
                        with open(arq, "rb") as arquivo_fisico:
                            json_desc = f_crypto.decrypt(arquivo_fisico.read()).decode('utf-8')
                            nome = json.loads(json_desc).get("nome", "Sem Nome")
                    except Exception:
                        nome = "Erro de leitura"
                        
                dados_painel.append({
                    "Empresa": empresa_nome, "Nome": nome, "CPF": cpf_arq, "Status": status, "Data": data_reg
                })
                
            df_painel = pd.DataFrame(dados_painel)
            
            # 4. Renderização das Três Listas
            if not df_painel.empty:
                df_aprov = df_painel[df_painel["Status"] == "Aprovado"].sort_values("Data", ascending=False)
                df_rev = df_painel[df_painel["Status"] == "Revisão"].sort_values("Data", ascending=False)
                df_pend = df_painel[df_painel["Status"] == "Pendente"].sort_values("Nome")
                
                c_res1, c_res2, c_res3 = st.columns(3)
                
                c_res1.success(f"✅ **Aprovados ({len(df_aprov)})**")
                if not df_aprov.empty:
                    c_res1.dataframe(df_aprov[["Nome", "Data"]], hide_index=True, use_container_width=True)
                
                c_res2.warning(f"⚠️ **Revisão ({len(df_rev)})**")
                if not df_rev.empty:
                    c_res2.dataframe(df_rev[["Nome", "Data"]], hide_index=True, use_container_width=True)
                
                c_res3.info(f"⏳ **Pendentes ({len(df_pend)})**")
                if not df_pend.empty:
                    # Mostra a empresa nos pendentes caso o filtro seja TODAS
                    colunas_pend = ["Nome", "Empresa"] if filtro_empresa == "TODAS" else ["Nome"]
                    c_res3.dataframe(df_pend[colunas_pend], hide_index=True, use_container_width=True)
            else:
                st.info("Nenhum funcionário encontrado para os filtros selecionados.")
                
    except Exception as e:
        st.error(f"🔍 **ERRO NO PAINEL ADMIN**\n`{e}`")


elif st.session_state.user_type == "employee":
    # --- TELA 3: VISUALIZAÇÃO DO HOLERITE ---
    func_dados = st.session_state.dados_func
    meu_hash = st.session_state.hash_arquivo
    
    # Valida no banco usando o hash. Se o arquivo foi substituído, isso retorna None automaticamente.
    status_atual = obter_status(func_dados["cpf"], func_dados["competencia"], meu_hash)
    
    # Reduzi levemente a proporção da coluna 1 para dar mais respiro ao botão Sair
    col_titulo, col_sair = st.columns([3, 1], vertical_alignment="center")
    
    # Renderiza o título com HTML/CSS em duas linhas para não quebrar no celular
    col_titulo.markdown(
        f"""
        <div style="line-height: 1.2; padding-top: 15px; padding-bottom: 15px;">
            <h2 style="margin: 0; padding: 0; font-size: 2rem;">Holerite</h2>
            <p style="margin: 0; padding: 0; font-size: 1.1rem; color: #6b7280;">Competência: {func_dados['competencia']}</p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    if col_sair.button("🚪 Sair", use_container_width=True):
        st.session_state.user_type = None
        st.session_state.dados_func = None
        st.session_state.hash_arquivo = None
        st.rerun()
    
    st.write(f"**Funcionário:** {func_dados['nome']}")
    st.write(f"**Cargo:** {func_dados['cargo']}")
    st.write(f"**PIX Cadastrado:** {func_dados.get('pix', 'Não cadastrada')}")
    
    proventos_list = [v for v in func_dados["verbas"] if v["tipo"] == "provento"]
    descontos_list = [v for v in func_dados["verbas"] if v["tipo"] == "desconto"]
    
    proventos = sum(v["valor"] for v in proventos_list)
    descontos = sum(v["valor"] for v in descontos_list)
    liquido = proventos - descontos

    st.markdown("<br>", unsafe_allow_html=True)
    
    # RENDERIZAÇÃO: PROVENTOS (Efeito Zebra)
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
        f"<div style='text-align: right; font-weight: bold; font-size: 1.1em; padding: 10px 12px 0 0;'>"
        f"Total Proventos: {formatar_moeda(proventos)}</div>", 
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # RENDERIZAÇÃO: DESCONTOS (Efeito Zebra)
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
        f"<div style='text-align: right; font-weight: bold; font-size: 1.1em; padding: 10px 12px 0 0;'>"
        f"Total Descontos: {formatar_moeda(descontos)}</div>", 
        unsafe_allow_html=True
    )

    st.markdown("---")
    
    # RENDERIZAÇÃO: LÍQUIDO 
    st.markdown(f"""
    <div style="text-align: center; margin: 15px 0;">
        <div style="font-size: 1rem; text-transform: uppercase; opacity: 0.8;">Valor Líquido a Receber</div>
        <div style="font-size: 2.2rem; font-weight: bold; margin-top: 5px;">{formatar_moeda(liquido)}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    # --- LÓGICA DE VALIDAÇÃO E DOWNLOAD ---
    if status_atual == "Revisão":
        st.warning("⚠️ Você solicitou a revisão deste documento. O RH entrará em contato em breve.")
        
    elif status_atual == "Aprovado":
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
                salvar_resposta(func_dados["cpf"], func_dados["nome"], func_dados["competencia"], "Aprovado", meu_hash)
                st.rerun()

        with col_revis:
            if st.button("⚠️ Solicitar Revisão", use_container_width=True):
                salvar_resposta(func_dados["cpf"], func_dados["nome"], func_dados["competencia"], "Revisão", meu_hash)
                st.rerun()
