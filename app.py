import logging
from datetime import datetime, date
import io # Importar io para manipulação de arquivos em memória

import streamlit as st
from supabase import create_client, Client
# import pdfkit # Removido pois pdfkit é problemático em Streamlit Cloud
import pandas as pd
import base64
from fpdf import FPDF
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.pagesizes import A4
import plotly.express as px
import zipfile # Importar zipfile para a funcionalidade de relatórios em lote

st.set_page_config(page_title="Gestão Clínica", layout="wide")

# Inicialização do Supabase
SUPABASE_URL = 'https://unvvrnovucylznxzuuip.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVudnZybm92dWN5bHpueHp1dWlwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTE1OTYzNiwiZXhwIjoyMDY0NzM1NjM2fQ.hVOh3UPOsljh-NWuhnOY1Z8eoLRXV5ws1_aA_w_RCqk'
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("gestao_pacientes.log"),
        logging.StreamHandler()
    ]
)

# 📌 Função para autenticar e registrar (mantida, mas com ajustes internos)
def autenticar_utilizador():
    st.header("🔐 Login e Registro")
    tab1, tab2 = st.tabs(["📝 Registrar", "🔑 Login"])

    with tab1:
        email_reg = st.text_input("Email:", key="email_registro_tab") # Alterado key para evitar conflito
        senha_reg = st.text_input("Senha:", type="password", key="senha_registro_tab") # Alterado key

        if st.button("Registrar", key="botao_registro_tab"): # Alterado key
            try:
                response = supabase.auth.sign_up(
                    {"email": email_reg, "password": senha_reg}
                )
                if response.user:
                    st.success("✅ Registro concluído com sucesso! Verifique o email para confirmar a conta.")
                else:
                    st.error("❌ Erro no registro.")
            except Exception as e:
                st.error(f"❌ Erro inesperado no registro: {e}")

    with tab2:
        email_log = st.text_input("Email:", key="email_login_tab") # Alterado key
        senha_log = st.text_input("Senha:", type="password", key="senha_login_tab") # Alterado key

        if st.button("Login", key="botao_login_tab"): # Alterado key
            try:
                response = supabase.auth.sign_in_with_password(
                    {"email": email_log, "password": senha_log}
                )
                if response.user:
                    st.success("✅ Login bem-sucedido!")
                    st.session_state["user"] = response.user
                    # Definir a opção para "🏠 Início" e forçar um rerun
                    st.session_state["opcao_menu"] = "🏠 Início"
                    st.rerun() # Isso reinicia o script e aplica a nova opção
                else:
                    st.error("❌ Falha no login. Verifique as credenciais.")
            except Exception as e:
                # 🟢 Novo tratamento específico do erro “Email not confirmed”
                if "email not confirmed" in str(e).lower():
                    st.warning("⚠️ Seu email ainda não está confirmado. Por favor, verifique a caixa de entrada e clique no link de confirmação.")
                else:
                    st.error(f"❌ Erro inesperado no login: {e}")
                    logging.error(f"Erro inesperado no login: {e}")

# Função para registrar novo utilizador (originalmente separada, mas a lógica está em autenticar_utilizador)
# Esta função não é chamada no seu código, a lógica de registro está dentro de 'autenticar_utilizador'
# Mantida aqui apenas para cumprir a instrução de "não alterar o nome original das funções"
def registar_utilizador():
    # Esta função não é diretamente usada na sua lógica atual,
    # a funcionalidade de registro está em 'autenticar_utilizador'.
    pass

# 🔹 Carregar produtos
@st.cache_data
def carregar_produtos():
    try:
        response = supabase.table("produtos").select("*").execute()
        if response.data is not None:
            return response.data
        else:
            return []
    except Exception as e:
        logging.error(f"Erro ao carregar produtos: {e}")
        st.error("Erro ao carregar produtos. Tente novamente.")
        return []

@st.cache_data
def carregar_exames():
    """Carrega a lista de exames clínicos do Supabase."""
    try:
        # Assumimos que existe uma tabela 'exames' no seu Supabase
        response = supabase.table("exames").select("*").execute()
        if response.data is not None:
            return response.data
        else:
            return []
    except Exception as e:
        logging.error(f"Erro ao carregar exames: {e}")
        st.error("Erro ao carregar exames. Tente novamente.")
        return []

# 🔹 Obter e incrementar recibo
def obter_incrementar_recibo():
    try:
        response = supabase.table("recibos").select("ultimo_num").eq("id", 1).execute()

        if response.data and response.data[0]:
            recibo = response.data[0]
            novo_num = recibo["ultimo_num"] + 1

            supabase.table("recibos").update({
                "ultimo_num": novo_num,
                "data_emissao": datetime.now().isoformat()
            }).eq("id", 1).execute()
            return novo_num
        else:
            initial_num = 1000
            supabase.table("recibos").insert({
                "id": 1,
                "ultimo_num": initial_num,
                "recibo_numero": initial_num,
                "data_emissao": datetime.now().isoformat()
            }).execute()
            return initial_num
    except Exception as e:
        logging.error(f"Erro ao obter/incrementar recibo: {e}")
        st.error("Erro ao gerar número de recibo.")
        return None

# 🔹 Gerar PDF (Factura)
# A função original tinha um problema onde não retornava nada, apenas gerava o arquivo.
# Para permitir download no Streamlit, ela deve retornar os bytes do PDF.
def gerar_pdf(dados_cliente, carrinho, total): # Removi nome_arquivo como parâmetro, vamos retornar bytes
    buffer = io.BytesIO() # Usar BytesIO para gerar o PDF em memória
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    try:
        # Assumindo 'logo.png' está no diretório raiz do app ou em 'images/logo.png'
        # Tente carregar de 'logo.png' primeiro, se falhar, tenta de 'images/logo.png'
        logo_path = "logo.png"
        try:
            imagem_logo = Image(logo_path, width=100, height=100)
        except FileNotFoundError:
            logo_path = "images/logo.png" # Tenta o caminho alternativo
            imagem_logo = Image(logo_path, width=100, height=100)

        tabela_logo = Table([[imagem_logo]], colWidths=[100], rowHeights=[100])
        tabela_logo.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ]))
        elements.append(tabela_logo)
    except FileNotFoundError:
        st.warning("Arquivo 'logo.png' ou 'images/logo.png' não encontrado. O PDF será gerado sem o logo.")
        logging.warning("Logo file not found in 'logo.png' or 'images/logo.png'.")
    except Exception as e:
        logging.error(f"Erro ao adicionar logo ao PDF: {e}")
        st.warning("Não foi possível adicionar o logo ao PDF.")

    styles = getSampleStyleSheet()
    estilo_personalizado = ParagraphStyle(
        name="EstiloPersonalizado", parent=styles["Normal"],
        fontName="Courier", fontSize=10, leading=12
    )

    elements.append(Paragraph("<b>Factura de Medicamentos</b>", estilo_personalizado))
    elements.append(Paragraph("Eduardo Mondlane 432, Maputo", estilo_personalizado))
    elements.append(Paragraph("NUIT: 33417617", estilo_personalizado))
    elements.append(Paragraph("Contacto: +258 84 123 4567", estilo_personalizado))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Data de Emissão:</b> {dados_cliente['data_emissao']}", estilo_personalizado))
    elements.append(Paragraph(f"<b>Número do Recibo:</b> {dados_cliente['recibo_numero']}", estilo_personalizado))
    elements.append(Spacer(1, 12))

    cliente_style = ParagraphStyle(
        "ClienteStyle", parent=styles["Normal"],
        fontName="Courier-Bold", fontSize=12
    )
    elements.append(Paragraph(f"Nome do Paciente: {dados_cliente['nome_cliente']}", cliente_style))
    elements.append(Paragraph(f"NUIT do Paciente: {dados_cliente['nuit_cliente']}", cliente_style))
    elements.append(Spacer(1, 12))

    data = [["Produto", "Quantidade", "Preço Unitário", "Total"]]
    for item in carrinho:
        subtotal = item["quantidade"] * item["preco"]
        data.append([
            item["nome"], str(item["quantidade"]),
            f"{item['preco']:.2f} MZN", f"{subtotal:.2f} MZN"
        ])
    data.append(["", "", "Total Geral:", f"{total:.2f} MZN"])

    tabela = Table(data, colWidths=[150, 100, 100, 100])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue), ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Courier"), ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(tabela)

    try:
        doc.build(elements)
        buffer.seek(0) # Retorna o ponteiro para o início do buffer
        return buffer.getvalue() # Retorna os bytes do PDF
    except Exception as e:
        logging.error(f"Erro ao construir PDF de venda: {e}")
        st.error("Erro ao gerar PDF da fatura.")
        return None

# 🔹 Gerar Excel
def gerar_relatorio_excel(dados): # Removi nome_arquivo, retornaremos bytes
    if not dados:
        logging.info("Não há dados para gerar o relatório Excel.")
        return None
    try:
        df = pd.DataFrame(dados)
        cols_to_select = ["recibo_numero", "data_emissao", "nome_cliente", "nuit_cliente", "total"]
        # Verifica se todas as colunas necessárias existem no DataFrame
        if not all(col in df.columns for col in cols_to_select):
            logging.error(f"Colunas esperadas não encontradas no DataFrame: {cols_to_select}")
            st.error("Dados incompletos para gerar o relatório Excel.")
            return None

        df = df[cols_to_select]
        df.columns = ["Recibo", "Data Emissão", "Cliente", "NUIT", "Total"]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Relatório", index=False)
            workbook = writer.book
            worksheet = writer.sheets["Relatório"]
            money_fmt = workbook.add_format({"num_format": "#,##0.00 MZN"})
            worksheet.set_column("E:E", 15, money_fmt)
            worksheet.set_column("A:D", 20)
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        logging.error(f"Erro ao gerar relatório Excel: {e}")
        st.error("Erro ao gerar relatório Excel.")
        return None

# 🔹 Carregar vendas para gráficos
@st.cache_data
def carregar_vendas():
    try:
        response = supabase.table("contabilidade").select("*").execute()
        if response.data:
            return pd.DataFrame(response.data)
        else:
            return pd.DataFrame()
    except Exception as e:
        logging.error(f"Erro ao carregar vendas para gráficos: {e}")
        st.error("Erro ao carregar dados de vendas para gráficos.")
        return pd.DataFrame()

# Função gerar_pdf_cotacao (usando FPDF) - Esta foi a que você preferiu manter e ajustei o nome
def gerar_pdf_cotacao_fpdf(empresa, itens): # Renomeei para evitar conflito com a de cima
    pdf = FPDF()
    pdf.add_page()
    try:
        # Tenta carregar de "logo.png" primeiro, se falhar, tenta de "images/logo.png"
        logo_path = "logo.png"
        try:
            pdf.image(logo_path, x=10, y=8, w=33)
        except RuntimeError: # FPDF levanta RuntimeError se o arquivo não for encontrado
            logo_path = "images/logo.png"
            pdf.image(logo_path, x=10, y=8, w=33)
    except Exception as e:
        logging.warning(f"Não foi possível carregar o logo para a cotação: {e}")
        
    pdf.set_font("Courier", size=10)
    pdf.ln(30)
    pdf.cell(200, 10, f"Cotação para: {empresa['nome']}", ln=True)
    pdf.cell(200, 10, f"NUIT: {empresa['nuit']} - Endereço: {empresa['endereco']}", ln=True)
    pdf.cell(200, 10, f"Email: {empresa['email']}", ln=True)
    pdf.ln(10)

    pdf.set_font("Courier", size=10)
    pdf.cell(10, 10, "Nr", 1)
    pdf.cell(70, 10, "Descrição", 1)
    pdf.cell(20, 10, "Qtd", 1)
    pdf.cell(30, 10, "Preço Un.", 1)
    pdf.cell(30, 10, "Preço Total", 1)
    pdf.cell(20, 10, "IVA", 1)
    pdf.ln()

    total_sem_iva = 0
    for i, item in enumerate(itens, 1):
        preco_total_item = item['preco'] * item['quantidade']
        total_sem_iva += preco_total_item

        pdf.cell(10, 10, str(i), 1)
        pdf.cell(70, 10, item['nome'], 1)
        pdf.cell(20, 10, str(item['quantidade']), 1)
        pdf.cell(30, 10, f"MT {item['preco']:.2f}", 1)
        pdf.cell(30, 10, f"MT {preco_total_item:.2f}", 1)
        pdf.cell(20, 10, "16%", 1)
        pdf.ln()

    iva_total = total_sem_iva * 0.16
    total_com_iva = total_sem_iva + iva_total

    pdf.ln(5)
    pdf.cell(200, 10, f"Subtotal (sem IVA): MZN {total_sem_iva:.2f}", ln=True)
    pdf.cell(200, 10, f"IVA (16%): MZN {iva_total:.2f}", ln=True)
    pdf.cell(200, 10, f"Total Geral: MZN {total_com_iva:.2f}", ln=True)
    pdf.ln(10)
    pdf.cell(200, 10, "Esta cotação tem a validade de 05 dias", ln=True)
    pdf.ln(10)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(200, 10, "DADOS BANCÁRIOS", ln=True)
    pdf.cell(200, 10, "MPESA - Conta: 8481766589 - Pedro Mate", ln=True)
    pdf.cell(200, 10, "EMOLA - Conta: 878166583 - Pedro Mate", ln=True)

    return pdf.output(dest='S').encode('latin1')

def gerar_pdf_paciente(paciente):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Ficha do Paciente: {paciente['nome']}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Idade: {paciente.get('idade', '')}", ln=True)
    pdf.cell(0, 10, f"Género: {paciente.get('genero', '')}", ln=True)
    pdf.cell(0, 10, f"Email: {paciente.get('email', '')}", ln=True)
    pdf.cell(0, 10, f"Telefone: {paciente.get('telefone', '')}", ln=True)
    pdf.cell(0, 10, f"BI: {paciente.get('bi', '')}", ln=True)
    pdf.cell(0, 10, f"NUIT: {paciente.get('nuit', '')}", ln=True)
    pdf.cell(0, 10, f"Data de Nascimento: {paciente.get('nascimento', '')}", ln=True)
    pdf.ln(5)
    pdf.multi_cell(0, 10, f"Motivo: {paciente.get('motivo', '')}")
    pdf.multi_cell(0, 10, f"Diagnóstico: {paciente.get('diagnostico', '')}")
    pdf.multi_cell(0, 10, f"Observações: {paciente.get('observacoes', '')}")
    pdf.ln(5)
    pdf.cell(0, 10, f"Data de Registro: {paciente.get('data_registro', '')}", ln=True)
    return pdf.output(dest='S').encode('latin1')

# Funções auxiliares para upload de fotos (assumo que elas estão funcionando corretamente)
# Se houver um erro, pode ser necessário ajustar a função 'upload_foto'
def upload_foto(foto_file):
    try:
        # Extrai a extensão do arquivo
        file_extension = foto_file.name.split(".")[-1]
        # Gera um nome de arquivo único
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{file_extension}"
        
        # Faz o upload para o bucket 'paciente_fotos'
        response = supabase.storage.from_("paciente_fotos").upload(unique_filename, foto_file.getvalue())
        
        if response.status_code == 200:
            # Obtém a URL pública
            public_url_response = supabase.storage.from_("paciente_fotos").get_public_url(unique_filename)
            return public_url_response.data.get('publicUrl')
        else:
            logging.error(f"Erro no upload da foto para Supabase Storage: {response}")
            return None
    except Exception as e:
        logging.error(f"Exceção durante o upload da foto: {e}")
        return None


# ---------------------- Funções de Página ----------------------

def pagina_inicio():
    st.subheader("Bem-vindo ao Sistema Integrado de Gestão de Pacientes.")
    st.write("Use o menu à esquerda para gerir pacientes, agendar consultas e gerar relatórios.")

def pagina_adicionar_paciente():
    st.subheader("Adicionar Novo Paciente")
    nome = st.text_input("Nome Completo")
    idade = st.number_input("Idade", 0, 120, step=1)
    genero = st.selectbox("Género", ["Masculino", "Feminino", "Outro"])
    email = st.text_input("Email")
    bi = st.text_input("Número do BI")
    nuit = st.number_input("NUIT", step=1)
    nascimento = st.date_input("Data de Nascimento")
    telefone = st.text_input("Telefone")
    motivo = st.text_area("Motivo")
    diagnostico = st.text_area("Diagnóstico")
    observacoes = st.text_area("Observações")
    fotos = st.file_uploader("Fotos", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

    if st.button("Salvar Paciente"):
        if not nome:
            st.warning("Preencha o nome do paciente.")
            return

        fotos_urls = []
        if fotos:
            st.info("A carregar fotos...")
            for foto in fotos:
                url = upload_foto(foto)
                if url:
                    fotos_urls.append(url)
                else:
                    st.error(f"Falha ao carregar foto: {foto.name}")
                    # Considerar se deve parar aqui ou continuar com as fotos que funcionaram
                    # return # Descomente para parar se uma foto falhar

    data = {
        'nome': nome,
        'idade': idade,
        'genero': genero,
        'email': email,
        'bi': bi,
        'nuit': nuit,
        'nascimento': str(nascimento),
        'telefone': telefone,
        'motivo': motivo,
        'diagnostico': diagnostico,
        'observacoes': observacoes,
        'foto': fotos_urls,
        'data_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        response = supabase.table('pacientes').insert(data).execute()
        # REMOVA A VERIFICAÇÃO DE response.status_code
        # Se a linha acima não lançou uma exceção, a operação foi bem-sucedida.
        st.success("Paciente salvo com sucesso!")
        # Opcional: Você pode querer usar response.data aqui se precisar dos dados do paciente recém-inserido
        # st.write(response.data) # Exemplo

    except Exception as e:
        # Este bloco 'except' agora vai capturar todos os erros da operação de inserção,
        # incluindo aqueles que antes resultariam em "has no attribute 'status_code'"
        st.error(f"Erro inesperado ao salvar paciente: {e}")
        logging.error(f"Erro inesperado ao salvar paciente: {e}")

def pagina_listar_pacientes():
    st.subheader("Lista de Pacientes")
    try:
        pacientes_data = supabase.table('pacientes').select("*").execute()
        pacientes = pacientes_data.data if pacientes_data.data else []
        busca = st.text_input("🔍 Buscar por nome")
        if busca:
            pacientes = [p for p in pacientes if busca.lower() in p['nome'].lower()]
        
        if pacientes:
            for paciente in pacientes:
                with st.expander(paciente['nome']):
                    st.write(f"Idade: {paciente['idade']}, Género: {paciente['genero']}")
                    st.write(f"Telefone: {paciente['telefone']}, Email: {paciente.get('email', 'Não informado')}")
                    st.write(f"Diagnóstico: {paciente['diagnostico']}")
                    if paciente.get('foto'):
                        for url in paciente['foto']:
                            st.image(url, width=150)
                    
                    pdf_bytes = gerar_pdf_paciente(paciente) # Esta já retorna bytes
                    if pdf_bytes:
                        st.download_button(
                            label="⬇️ Baixar Ficha PDF",
                            data=pdf_bytes,
                            file_name=f"ficha_paciente_{paciente['nome'].replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"pdf_download_{paciente['id']}" # Chave única para o botão
                        )
                    else:
                        st.warning("Não foi possível gerar a ficha PDF para este paciente.")
        else:
            st.info("Nenhum paciente encontrado.")

    except Exception as e:
        st.error(f"Erro ao carregar ou listar pacientes: {e}")
        logging.error(f"Erro ao carregar ou listar pacientes: {e}")

def pagina_relatorios_lote():
    st.subheader("Gerar Relatórios de Todos os Pacientes")
    try:
        pacientes_data = supabase.table('pacientes').select("*").execute()
        pacientes = pacientes_data.data if pacientes_data.data else []
        if st.button("Gerar Relatórios em Lote"):
            if not pacientes:
                st.info("Nenhum paciente para gerar relatórios.")
                return

            progresso = st.progress(0)
            total = len(pacientes)
            
            # import zipfile # Já importado no topo
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for i, paciente in enumerate(pacientes):
                    pdf_bytes = gerar_pdf_paciente(paciente) # Esta já retorna bytes
                    if pdf_bytes:
                        file_name = f"ficha_paciente_{paciente['nome'].replace(' ', '_')}.pdf"
                        zip_file.writestr(file_name, pdf_bytes)
                    progresso.progress((i + 1) / total)
            
            zip_buffer.seek(0)
            st.success("Relatórios em PDF gerados com sucesso e compactados!")
            st.download_button(
                label="⬇️ Baixar Todos os Relatórios (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="relatorios_pacientes.zip",
                mime="application/zip"
            )
    except Exception as e:
        st.error(f"Erro ao gerar relatórios em lote: {e}")
        logging.error(f"Erro ao gerar relatórios em lote: {e}")

def pagina_agendamento_consultas():
    st.subheader("📅 Agendamento de Consultas")
    st.header("Agendar Nova Consulta")
    with st.form("formulario_consulta"):
        nome = st.text_input("Nome")
        email = st.text_input("Email")
        data_consulta = st.date_input("Data da Consulta", value=date.today())
        submit_button = st.form_submit_button("Agendar")

        if submit_button:
            if not nome or not email:
                st.warning("Por favor, preencha todos os campos.")
                return
            try:
                response = supabase.table("consultas").insert({
                    "nome": nome,
                    "email": email,
                    "data_consulta": data_consulta.isoformat()
                }).execute()

                if response.status_code == 201:
                    st.success("Consulta agendada com sucesso!")
                    st.info(f"📧 Notificação enviada para {email}. (simulação)")
                else:
                    st.error(f"Erro ao agendar a consulta: {response.data}")
                    logging.error(f"Erro ao agendar consulta: {response.data}")
            except Exception as e:
                st.error(f"Erro inesperado ao agendar consulta: {e}")
                logging.error(f"Erro inesperado ao agendar consulta: {e}")

    st.header("📋 Consultas Agendadas")
    try:
        consultas_data = supabase.table("consultas").select("*").execute()
        consultas = consultas_data.data if consultas_data.data else []
        if consultas:
            df_consultas = pd.DataFrame(consultas)
            df_consultas["data_consulta"] = pd.to_datetime(df_consultas["data_consulta"]).dt.date
            st.dataframe(df_consultas[["nome", "email", "data_consulta"]])

            csv = df_consultas.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="⬇️ Exportar para CSV",
                data=csv,
                file_name="consultas.csv",
                mime="text/csv",
            )
        else:
            st.write("Nenhuma consulta agendada ainda.")
    except Exception as e:
        st.error(f"Erro ao carregar consultas agendadas: {e}")
        logging.error(f"Erro ao carregar consultas agendadas: {e}")


def pagina_triagem():
    st.header("📝 Registrar Entrada de Paciente")
    nome = st.text_input("Nome do paciente:", key="triagem_nome").strip()
    observacoes = st.text_area(
        "Observações (opcional, máx. 500 caracteres):",
        "",
        key="triagem_observacoes"
    ).strip()

    if st.button("Registrar", key="botao_triagem"):
        if not nome:
            st.warning("Por favor, insira o nome do paciente.")
            return
        elif len(nome) > 100:
            st.warning("O nome do paciente deve ter no máximo 100 caracteres.")
            return
        elif len(observacoes) > 500:
            st.warning("As observações devem ter no máximo 500 caracteres.")
            return
        else:
            data_entrada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Verificar se o usuário está autenticado antes de tentar aceder o user.id
            if "user" in st.session_state and st.session_state["user"]:
                current_user_id = st.session_state["user"].id
            else:
                st.error("Erro: ID de utilizador não disponível. Faça login novamente.")
                logging.error("Triagem: user_id não disponível na session_state.")
                return

            dados = {
                "nome": nome,
                "data_entrada": data_entrada,
                "observacoes": observacoes,
                "user_id": current_user_id
            }
            try:
                resultado = supabase.table("pacientes_entrada").insert(dados).execute()
                if resultado.data:
                    st.success("✅ Entrada registrada com sucesso!")
                else:
                    st.error("❌ Erro ao registrar entrada.")
                    logging.error(f"Erro ao registrar entrada (triagem): {resultado.data}")
            except Exception as e:
                st.error(f"❌ Erro inesperado ao inserir: {e}")
                logging.error(f"Erro inesperado ao inserir (triagem): {e}")

def pagina_consultar_historico():
    st.header("🔍 Consultar Histórico de Paciente")

    nome_pesquisa = st.text_input("Nome do paciente:", key="consulta_nome").strip()

    if st.button("Consultar", key="botao_consultar"):
        if not nome_pesquisa:
            st.warning("Por favor, insira o nome do paciente.")
            return

        try:
            # Verificar se o usuário está autenticado antes de tentar aceder o user.id
            if "user" in st.session_state and st.session_state["user"]:
                current_user_id = st.session_state["user"].id
            else:
                st.error("Erro: ID de utilizador não disponível. Faça login novamente.")
                logging.error("Consulta Histórico: user_id não disponível na session_state.")
                return

            resultado = supabase.table("pacientes_entrada") \
                .select("*") \
                .eq("user_id", current_user_id) \
                .ilike("nome", f"%{nome_pesquisa}%") \
                .order("data_entrada", desc=True) \
                .execute()

            historico = resultado.data
            if historico:
                st.subheader(f"📁 Histórico encontrado para '{nome_pesquisa}':")
                for entrada in historico:
                    data = entrada['data_entrada']
                    obs = entrada.get('observacoes', 'Sem observações')
                    st.write(f"- **Data:** {data} | **Observações:** {obs}")
            else:
                st.info("Nenhum registro encontrado para este paciente.")
        except Exception as e:
            st.error(f"❌ Erro inesperado ao consultar histórico: {e}")
            logging.error(f"Erro inesperado ao consultar histórico: {e}")

def pagina_farmacia():
    st.title("Farmácia")
    st.subheader("Informações do Cliente")
    nome_cliente = st.text_input("Nome do Paciente :")
    nuit_cliente = st.text_input("NUIT do Paciente :")

    st.subheader("Selecione o Farmaco")

    # Carrega produtos uma vez e armazena na sessão
    if 'produtos_carregados' not in st.session_state:
        st.session_state.produtos_carregados = carregar_produtos()
    
    produtos_disponiveis = st.session_state.produtos_carregados

    produto_selecionado = None
    quantidade = 0

    if produtos_disponiveis:
        produto_nomes = [p["nome"] for p in produtos_disponiveis]
        produto_selecionado_nome = st.selectbox("Produto:", produto_nomes)
        produto_selecionado = next((p for p in produtos_disponiveis if p["nome"] == produto_selecionado_nome), None)
        quantidade = st.number_input("Quantidade:", min_value=1, step=1, value=1)
    else:
        st.warning("Nenhum produto disponível no momento.")
    
    if "carrinho" not in st.session_state:
        st.session_state.carrinho = []

    if st.button("Adicionar ao Carrinho"):
        if produto_selecionado and produtos_disponiveis:
            item_carrinho = {
                "id": produto_selecionado["id"],
                "nome": produto_selecionado["nome"],
                "preco": produto_selecionado["preco"],
                "quantidade": quantidade
            }
            st.session_state.carrinho.append(item_carrinho)
            st.success(f"{quantidade} x {produto_selecionado['nome']} adicionado ao carrinho!")
        else:
            st.warning("Nenhum produto selecionado ou disponível para adicionar.")

    st.subheader("Carrinho:")
    total = 0
    if st.session_state.carrinho:
        for i, item in enumerate(st.session_state.carrinho):
            subtotal = item["preco"] * item["quantidade"]
            col1, col2, col3 = st.columns([0.6, 0.3, 0.1])
            col1.write(f"{item['quantidade']} x {item['nome']} - {item['preco']:.2f} MZN")
            col2.write(f"Subtotal: {subtotal:.2f} MZN")
            if col3.button("Remover", key=f"remove_item_{i}"):
                st.session_state.carrinho.pop(i)
                st.rerun()
            total += subtotal
        st.markdown(f"---")
        st.write(f"**Total Geral: {total:.2f} MZN**")
    else:
        st.write("Carrinho vazio.")

    if st.button("Gerar PDF e Salvar Venda"):
        if not nome_cliente or not nuit_cliente:
            st.warning("Nome e NUIT do cliente são obrigatórios.")
            return
        elif not st.session_state.carrinho:
            st.warning("Carrinho vazio. Adicione produtos antes de gerar a venda.")
            return

        recibo_numero = obter_incrementar_recibo()
        if recibo_numero is None:
            return

        data_emissao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        dados_cliente = {
            "nome_cliente": nome_cliente,
            "nuit_cliente": nuit_cliente,
            "recibo_numero": recibo_numero,
            "data_emissao": data_emissao
        }

        nome_cliente_sanitizado = nome_cliente.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        pdf_bytes = gerar_pdf(dados_cliente, st.session_state.carrinho, total)
        if pdf_bytes:
            # Salvar no Supabase Storage
            try:
                pdf_filename = f"recibo_{recibo_numero}_{nome_cliente_sanitizado}.pdf"
                supabase.storage.from_("recibosvendas").upload(pdf_filename, pdf_bytes, {"ContentType": "application/pdf"})
                st.success(f"PDF da venda gerado e salvo no Supabase Storage como '{pdf_filename}'!")
                
                # Opcional: obter URL pública se precisar exibir ou baixar diretamente do Storage
                # public_url = supabase.storage.from_("recibos_vendas").get_public_url(pdf_filename)
                # st.write(f"[Ver PDF no Storage]({public_url.data['publicUrl']})")

            except Exception as e:
                st.error(f"Erro ao salvar PDF no Supabase Storage: {e}")
                logging.error(f"Erro ao salvar PDF no Supabase Storage: {e}")
                
            st.download_button(
                label="⬇️ Baixar Fatura PDF",
                data=pdf_bytes,
                file_name=f"fatura_{nome_cliente_sanitizado}_{data_emissao.split(' ')[0]}.pdf",
                mime="application/pdf"
            )

            # Salvar os dados da venda na tabela de contabilidade
            venda_data = {
                "recibo_numero": recibo_numero,
                "data_emissao": data_emissao,
                "nome_cliente": nome_cliente,
                "nuit_cliente": nuit_cliente,
                "total": total,
                "detalhes_itens": st.session_state.carrinho # Salva o carrinho como JSON
            }
            try:
                response_db = supabase.table("contabilidade").insert(venda_data).execute()
                if response_db.status_code == 201:
                    st.success("Dados da venda salvos na contabilidade com sucesso!")
                    st.session_state.carrinho = [] # Limpa o carrinho
                else:
                    st.error(f"Erro ao salvar dados da venda na contabilidade: {response_db.data}")
                    logging.error(f"Erro ao salvar dados da venda na contabilidade: {response_db.data}")
            except Exception as e:
                st.error(f"Erro inesperado ao salvar dados da venda: {e}")
                logging.error(f"Erro inesperado ao salvar dados da venda: {e}")
        else:
            st.error("Não foi possível gerar a fatura PDF.")

def pagina_cotacoes():
    st.title("📋 Cotações de Exames Clínicos") # Título atualizado
    st.subheader("Informações da Empresa Requisitante") # Subtítulo mais claro
    
    nome_empresa = st.text_input("Nome da Empresa:")
    nuit_empresa = st.text_input("NUIT da Empresa:")
    endereco_empresa = st.text_input("Endereço da Empresa:")
    email_empresa = st.text_input("Email da Empresa:")

    st.subheader("Itens da Cotação (Exames)") # Subtítulo atualizado

    # Inicializa st.session_state.itens_cotacao se não existir
    if 'itens_cotacao' not in st.session_state:
        st.session_state.itens_cotacao = []
    
    # Carrega exames disponíveis e armazena na sessão
    if 'exames_carregados' not in st.session_state:
        st.session_state.exames_carregados = carregar_exames()
    
    exames_disponiveis = st.session_state.exames_carregados

    exames_nomes = [e["nome"] for e in exames_disponiveis] if exames_disponiveis else []
    
    with st.form("add_item_cotacao_form", clear_on_submit=True):
        col1, col2 = st.columns([0.7, 0.3])
        exame_selecionado_nome = col1.selectbox("Exame:", exames_nomes, key="exame_cotacao_sel") # Nome da variável e key atualizados
        quantidade_cotacao = col2.number_input("Quantidade:", min_value=1, step=1, value=1, key="qtd_cotacao_input")
        add_item_button = st.form_submit_button("Adicionar Exame à Cotação") # Texto do botão atualizado

    if add_item_button:
        if exame_selecionado_nome:
            exame_selecionado = next((e for e in exames_disponiveis if e["nome"] == exame_selecionado_nome), None)
            if exame_selecionado:
                # Quantidade de exames é geralmente 1, mas mantive o campo para flexibilidade.
                # Se for sempre 1, pode remover 'quantidade' e usar 'preco' diretamente.
                item_cotacao = {
                    "id": exame_selecionado["id"],
                    "nome": exame_selecionado["nome"],
                    "preco": exame_selecionado["preco"],
                    "quantidade": quantidade_cotacao # Manter quantidade, pode ser para X testes para Y pessoas
                }
                st.session_state.itens_cotacao.append(item_cotacao)
                st.success(f"Item '{item_cotacao['nome']}' adicionado à cotação.")
            else:
                st.warning("Exame selecionado não encontrado.") # Mensagem atualizada
        else:
            st.warning("Por favor, selecione um exame para adicionar.") # Mensagem atualizada

    st.write("---")
    st.subheader("Itens na Cotação Atual:")
    total_cotacao = 0
    if st.session_state.itens_cotacao:
        for i, item in enumerate(st.session_state.itens_cotacao):
            subtotal_item = item["preco"] * item["quantidade"]
            st.write(f"- {item['quantidade']} x {item['nome']} ({item['preco']:.2f} MZN/un) = {subtotal_item:.2f} MZN")
            total_cotacao += subtotal_item
        st.markdown(f"**Total da Cotação: {total_cotacao:.2f} MZN**")

        if st.button("Limpar Itens da Cotação"):
            st.session_state.itens_cotacao = []
            st.rerun()
    else:
        st.info("Nenhum item adicionado à cotação ainda.")

    if st.button("Gerar PDF e Salvar Cotação"): # Texto do botão atualizado
        if not nome_empresa or not nuit_empresa or not endereco_empresa or not email_empresa:
            st.warning("Preencha todas as informações da empresa.")
            return # Adicionado return para parar a execução
        elif not st.session_state.itens_cotacao:
            st.warning("Adicione itens à cotação antes de gerar o PDF.")
            return # Adicionado return para parar a execução
        
        # Obter o ID do utilizador autenticado (assumindo que 'user' está em st.session_state)
        current_user_id = None
        if "user" in st.session_state and st.session_state["user"]:
            current_user_id = st.session_state["user"].id
        else:
            st.error("Erro: Utilizador não autenticado. Não é possível salvar a cotação.")
            logging.error("Tentativa de salvar cotação sem utilizador autenticado.")
            return

        empresa_dados = {
            "nome": nome_empresa,
            "nuit": nuit_empresa,
            "endereco": endereco_empresa,
            "email": email_empresa
        }
        
        pdf_cotacao_bytes = gerar_pdf_cotacao_fpdf(empresa_dados, st.session_state.itens_cotacao)
        
        if pdf_cotacao_bytes:
            nome_arquivo_cotacao_pdf = f"cotacao_{nome_empresa.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            try:
                # Salvar o PDF no Supabase Storage
                # Assumimos um bucket 'cotacoes_pdfs' que você precisará criar
                supabase.storage.from_("cotacoes-pdfs").upload(
                    nome_arquivo_cotacao_pdf, pdf_cotacao_bytes, {"ContentType": "application/pdf"}
                )
                public_url_pdf = supabase.storage.from_("cotacoes-pdfs").get_public_url(nome_arquivo_cotacao_pdf)
                
                # Salvar os detalhes da cotação na tabela 'cotacoes'
                cotacao_data_db = {
                    "data_cotacao": datetime.now().isoformat(),
                    "nome_empresa": nome_empresa,
                    "nuit_empresa": nuit_empresa,
                    "endereco_empresa": endereco_empresa,
                    "email_empresa": email_empresa,
                    "itens_cotacao": st.session_state.itens_cotacao, # JSONB
                    "total_cotacao": total_cotacao,
                    "pdf_url": public_url_pdf if public_url_pdf else None, # Salvar URL do PDF
                    "user_id": current_user_id # Para RLS
                }
                
                response_db = supabase.table("cotacoes").insert(cotacao_data_db).execute()
                
                # Nao verificar status_code para APIResponse
                st.success("PDF da cotação gerado e salvo no Supabase Storage e detalhes salvos na base de dados!")
                
                st.download_button(
                    label="⬇️ Baixar Cotação PDF",
                    data=pdf_cotacao_bytes,
                    file_name=nome_arquivo_cotacao_pdf,
                    mime="application/pdf"
                )
                
                st.session_state.itens_cotacao = [] # Limpar itens após salvar
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao salvar cotação ou PDF: {e}")
                logging.error(f"Erro ao salvar cotação ou PDF: {e}")
        else:
            st.error("Erro ao gerar PDF da cotação.")

def pagina_graficos_visuais():
    st.subheader("📊 Relatórios Visuais e Gráficos")
    df_vendas = carregar_vendas()
    
    # Protege contra df_vendas ser None
    if df_vendas is not None and not df_vendas.empty:
        df_vendas["data_emissao"] = pd.to_datetime(df_vendas["data_emissao"], format='ISO8601').dt.date

        st.write("### Total de Vendas por Dia")
        vendas_dia = df_vendas.groupby("data_emissao")["total"].sum().reset_index()
        fig_bar = px.bar(vendas_dia, x="data_emissao", y="total", text_auto=True,
                          labels={"data_emissao": "Data", "total": "Total (MZN)"},
                          title="Total de Vendas por Dia")
        st.plotly_chart(fig_bar, use_container_width=True)

        st.write("### Distribuição de Vendas por Cliente")
        vendas_cliente = df_vendas.groupby("nome_cliente")["total"].sum().reset_index()
        fig_pizza = px.pie(vendas_cliente, values="total", names="nome_cliente",
                           title="Vendas por Cliente")
        st.plotly_chart(fig_pizza, use_container_width=True)

        st.write("### Ranking de Clientes")
        vendas_cliente_rank = vendas_cliente.sort_values(by="total", ascending=False).head(10)
        fig_bar_rank = px.bar(vendas_cliente_rank, x="nome_cliente", y="total", text_auto=True,
                                labels={"nome_cliente": "Cliente", "total": "Total (MZN)"},
                                title="Top 10 Clientes por Vendas")
        st.plotly_chart(fig_bar_rank, use_container_width=True)
        
        # Gráfico de vendas por produto (requer desaninhamento dos detalhes_itens)
        st.write("### Vendas por Produto")
        todos_itens = []
        for index, row in df_vendas.iterrows():
            if 'detalhes_itens' in row and row['detalhes_itens']:
                for item in row['detalhes_itens']:
                    item['venda_id'] = row['id'] # Para manter o contexto da venda
                    todos_itens.append(item)
        
        if todos_itens:
            df_itens = pd.DataFrame(todos_itens)
            vendas_produto = df_itens.groupby("nome")["quantidade"].sum().reset_index()
            fig_bar_prod = px.bar(vendas_produto, x="nome", y="quantidade", text_auto=True,
                                labels={"nome": "Produto", "quantidade": "Quantidade Vendida"},
                                title="Quantidade de Produtos Vendidos")
            st.plotly_chart(fig_bar_prod, use_container_width=True)
        else:
            st.info("Nenhum dado de itens de venda para exibir gráficos de produtos.")

    else:
        st.info("Não há dados de vendas disponíveis para gerar gráficos.")

# ---------------------- Lógica Principal da Aplicação ----------------------

# Inicializa o estado da sessão para o utilizador e a opção de menu
if "user" not in st.session_state:
    st.session_state["user"] = None
if "opcao_menu" not in st.session_state:
    st.session_state["opcao_menu"] = "🔐 Login"

# Lógica condicional para exibir a página de login ou o aplicativo completo
if st.session_state["user"] is None:
    autenticar_utilizador()
    # Se o utilizador não estiver logado, para a execução do restante do script.
    # O st.rerun() dentro de autenticar_utilizador() fará com que o script seja reiniciado
    # após um login bem-sucedido.
    st.stop()
else:
    # Se o utilizador está logado, mostra o menu lateral e as páginas
    st.sidebar.image("logo.png", width=150)
    st.sidebar.title(f"Bem-vindo, {st.session_state['user'].email}!") # Assumindo que você tem um logo.png
    st.sidebar.write("### Menu")

    menu_options = {
        "🏠 Início": pagina_inicio,
        "➕ Adicionar Paciente para Plano de Saúde": pagina_adicionar_paciente,
        "👨‍👩‍👧‍👦 Lista de Pacientes com Plano de Saúde": pagina_listar_pacientes,
        "📑 Base de dados do Plano de Saúde": pagina_relatorios_lote,
        "📅 Agendamentos de Consulta": pagina_agendamento_consultas,
        "📝 Triagem": pagina_triagem,
        "🔍 Consultar Histórico do Pacicente": pagina_consultar_historico,
        "💊 Farmácia": pagina_farmacia,
        "🧾 Exames Clínicos": pagina_cotacoes,
        "📊 Contabilidade": pagina_graficos_visuais,
        "🚪 Terminar Sessão": None # Logout não é uma função de página, mas um acionador
    }

    # Use um radio button para as opções de menu
    opcao_selecionada = st.sidebar.radio(
        "Navegar",
        list(menu_options.keys()),
        index=list(menu_options.keys()).index(st.session_state["opcao_menu"])
    )

    # Atualiza a opção de menu na session_state para manter o estado
    st.session_state["opcao_menu"] = opcao_selecionada

    # Lógica para processar a opção selecionada
    if opcao_selecionada == "🚪 Logout":
        try:
            supabase.auth.sign_out()
            st.session_state["user"] = None
            st.session_state["opcao_menu"] = "🔐 Login"
            st.success("Sessão encerrada com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao fazer logout: {e}")
            logging.error(f"Erro ao fazer logout: {e}")
    else:
        # Chama a função da página correspondente
        func_pagina = menu_options.get(opcao_selecionada)
        if func_pagina:
            func_pagina()
