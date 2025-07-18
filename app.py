import logging
from datetime import datetime, date, timedelta
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
    st.image("logo.png", width=150)
    st.header("🔐 Registro e Login")
    tab1, tab2 = st.tabs(["📝 Registrar", "🔑 Login"])

    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

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

def carregar_dados_produtos():
    """Carrega todos os dados da tabela 'produtos' do Supabase."""
    try:
        response = supabase.table("produtos").select("id, custo, nome, preco").execute()
        if response.data:
            return pd.DataFrame(response.data)
        else:
            # --- CORREÇÃO AQUI: Sempre retorna um DataFrame vazio se não houver dados ---
            return pd.DataFrame(columns=['id', 'custo', 'nome', 'preco'])
    except Exception as e:
        logging.error(f"Erro ao carregar dados de produtos: {e}")
        st.error(f"Erro ao carregar dados de produtos. Detalhes: {e}")
        # --- CORREÇÃO AQUI: Sempre retorna um DataFrame vazio em caso de erro também ---
        return pd.DataFrame(columns=['id', 'custo', 'nome', 'preco'])
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

@st.cache_data(ttl=3600)
def carregar_dados_contabilidade_vendas():
    try:
        response = supabase.table("contabilidade").select("*").order("data_emissao", desc=False).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['data_emissao'] = pd.to_datetime(df['data_emissao'], format='ISO8601')
            df['data_dia'] = df['data_emissao'].dt.date
            df['detalhes_itens'] = df['detalhes_itens'].apply(lambda x: x if isinstance(x, list) else [])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        logging.error(f"Erro ao carregar dados de contabilidade: {e}")
        st.error(f"Erro ao carregar dados de contabilidade. Detalhes: {e}")
        return pd.DataFrame()

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
    elements.append(Paragraph("Boane, B.2, Q.3 Av. Namaacha, Rua 1º de Maio C. Nº 59", estilo_personalizado))
    elements.append(Paragraph("NUIT: 401937684", estilo_personalizado))
    elements.append(Paragraph("Contacto: +258  84 671 1512 / 87 791 1717", estilo_personalizado))
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
def gerar_pdf_cotacao_fpdf(empresa, itens):  # Renomeei para evitar conflito com a de cima
    """
    Gera um PDF de cotação em memória e retorna os bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []

    # Adicionar logo
    try:
        logo_path = "logo.png"
        try:
            imagem_logo = Image(logo_path, width=80, height=80)
        except FileNotFoundError:
            logo_path = "images/logo.png"
            imagem_logo = Image(logo_path, width=80, height=80)

        tabela_logo = Table([[imagem_logo]], colWidths=[100], rowHeights=[80])
        tabela_logo.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ]))
        elementos.append(tabela_logo)

    except Exception as e:
        logging.warning(f"Logo não encontrado ou erro ao carregar: {e}")

    # Estilos
    estilos = getSampleStyleSheet()
    estilo_normal = ParagraphStyle(
        name="NormalPersonalizado", parent=estilos["Normal"],
        fontName="Courier", fontSize=10, leading=12
    )
    estilo_bold = ParagraphStyle(
        name="BoldPersonalizado", parent=estilos["Normal"],
        fontName="Courier-Bold", fontSize=10, leading=12
    )

    # Dados da empresa
    elementos.append(Paragraph(f"<b>Cotação para:</b> {empresa['nome']}", estilo_bold))
    elementos.append(Paragraph(f"NUIT: {empresa['nuit']}", estilo_normal))
    elementos.append(Paragraph(f"Endereço: {empresa['endereco']}", estilo_normal))
    elementos.append(Paragraph(f"Email: {empresa['email']}", estilo_normal))
    elementos.append(Spacer(1, 12))

    # Tabela dos itens
    data = [["Nr", "Descrição", "Qtd", "Preço Unitário", "Preço Total", "IVA"]]

    total_sem_iva = 0
    for idx, item in enumerate(itens, 1):
        preco_total = item['quantidade'] * item['preco']
        total_sem_iva += preco_total

        data.append([
            str(idx),
            item['nome'],
            str(item['quantidade']),
            f"MZN {item['preco']:.2f}",
            f"MZN {preco_total:.2f}",
            "16%"
        ])

    iva = total_sem_iva * 0.16
    total_com_iva = total_sem_iva + iva

    tabela_itens = Table(data, colWidths=[30, 150, 50, 80, 80, 40])
    tabela_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elementos.append(tabela_itens)
    elementos.append(Spacer(1, 12))

    # Totais
    elementos.append(Paragraph(f"Subtotal (sem IVA): MZN {total_sem_iva:.2f}", estilo_bold))
    elementos.append(Paragraph(f"IVA (16%): MZN {iva:.2f}", estilo_bold))
    elementos.append(Paragraph(f"Total Geral: MZN {total_com_iva:.2f}", estilo_bold))
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph("Esta cotação tem a validade de 05 dias.", estilo_normal))
    elementos.append(Spacer(1, 12))

    # Dados bancários
    elementos.append(Paragraph("<b>DADOS BANCÁRIOS</b>", estilo_bold))
    elementos.append(Paragraph("MPESA - Conta: 84 671 1512 - Rogério Elabo Saide", estilo_normal))
    elementos.append(Paragraph("EMOLA - Conta: 87 191 1717  - Yaquini alojamento De Sousa", estilo_normal))

    # Gerar PDF
    try:
        doc.build(elementos)
        buffer.seek(0)
        return buffer.getvalue()  # Retorna os bytes do PDF
    except Exception as e:
        logging.error(f"Erro ao construir PDF de cotação: {e}")
        return None

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
    st.image("logo.png", width=150)
    st.subheader(f"Bem-vindo, {st.session_state['user'].email} ao Sistema Integrado de Gestão de Pacientes.!")
    st.write("Use o menu à esquerda para gerir pacientes, agendar consultas e gerar relatórios.")

    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

def pagina_adicionar_paciente():
    st.image("logo.png", width=150)
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
    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

def pagina_listar_pacientes():
    st.image("logo.png", width=150)
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
    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

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
    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

def pagina_agendamento_consultas():
    st.image("logo.png", width=150)
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
    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)


def pagina_triagem():
    st.image("logo.png", width=150)
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
    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

def pagina_consultar_historico():
    st.image("logo.png", width=150)
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
    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

def pagina_farmacia():
    st.image("logo.png", width=150)
    st.title("Farmácia")
    st.subheader("Informações do Paciênte")
    nome_cliente = st.text_input("Nome do Paciênte:")
    nuit_cliente = st.text_input("NUIT do Paciênte:")

    st.subheader("Selecione o Fármaco")

    # Carrega produtos uma vez e armazena na sessão
    if 'produtos_carregados' not in st.session_state:
        st.session_state.produtos_carregados = carregar_produtos()
    
    produtos_disponiveis = st.session_state.produtos_carregados

    produto_selecionado = None
    quantidade = 0

    if produtos_disponiveis:
        produto_nomes = [p["nome"] for p in produtos_disponiveis]
        produto_selecionado_nome = st.selectbox("Fármaco:", produto_nomes)
        produto_selecionado = next((p for p in produtos_disponiveis if p["nome"] == produto_selecionado_nome), None)
        quantidade = st.number_input("Quantidade:", min_value=1, step=1, value=1)
    else:
        st.warning("Nenhum Fármaco disponível no momento.")
    
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
            st.warning("Nenhum Farmaco selecionado ou disponível para adicionar.")

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
    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

def pagina_cotacoes():
    st.image("logo.png", width=150)
    st.title("📋 Cotações de Exames Clínicos")
    st.subheader("Informações da Empresa Requisitante")

    # Inputs com st.session_state para manter os valores após o clique
    nome_empresa = st.text_input("Nome da Empresa:", key="nome_empresa").strip()
    nuit_empresa = st.text_input("NUIT da Empresa:", key="nuit_empresa").strip()
    endereco_empresa = st.text_input("Endereço da Empresa:", key="endereco_empresa").strip()
    email_empresa = st.text_input("Email da Empresa:", key="email_empresa").strip()

    st.subheader("Itens da Cotação (Exames)")

    # Inicializa a lista de itens da cotação na sessão
    if 'itens_cotacao' not in st.session_state:
        st.session_state.itens_cotacao = []

    # Carrega exames disponíveis uma vez
    if 'exames_carregados' not in st.session_state:
        st.session_state.exames_carregados = carregar_exames()

    exames_disponiveis = st.session_state.exames_carregados
    exames_nomes = [e["nome"] for e in exames_disponiveis] if exames_disponiveis else []

    # Formulário para adicionar itens
    with st.form("add_item_cotacao_form", clear_on_submit=True):
        col1, col2 = st.columns([0.7, 0.3])
        exame_selecionado_nome = col1.selectbox("Exame:", exames_nomes, key="exame_cotacao_sel")
        quantidade_cotacao = col2.number_input("Quantidade:", min_value=1, step=1, value=1, key="qtd_cotacao_input")
        add_item_button = st.form_submit_button("Adicionar Exame à Cotação")

    if add_item_button:
        if exame_selecionado_nome:
            exame_selecionado = next((e for e in exames_disponiveis if e["nome"] == exame_selecionado_nome), None)
            if exame_selecionado:
                item_cotacao = {
                    "id": exame_selecionado["id"],
                    "nome": exame_selecionado["nome"],
                    "preco": exame_selecionado["preco"],
                    "quantidade": quantidade_cotacao
                }
                st.session_state.itens_cotacao.append(item_cotacao)
                st.success(f"Item '{item_cotacao['nome']}' adicionado à cotação.")
            else:
                st.warning("Exame selecionado não encontrado.")
        else:
            st.warning("Por favor, selecione um exame para adicionar.")

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
    else:
        st.info("Nenhum item adicionado à cotação ainda.")

    # Botão para gerar PDF e salvar cotação
    if st.button("Gerar PDF e Salvar Cotação"):

        # Validação robusta dos campos da empresa
        campos_obrigatorios = [
            st.session_state.nome_empresa.strip(),
            st.session_state.nuit_empresa.strip(),
            st.session_state.endereco_empresa.strip(),
            st.session_state.email_empresa.strip()
        ]

        if any(campo == "" for campo in campos_obrigatorios):
            st.warning("Preencha todas as informações da empresa.")
            return

        if not st.session_state.itens_cotacao:
            st.warning("Adicione itens à cotação antes de gerar o PDF.")
            return

        # Verifica se o utilizador está autenticado
        current_user_id = None
        if "user" in st.session_state and st.session_state["user"]:
            current_user_id = st.session_state["user"].id
        else:
            st.error("Erro: Utilizador não autenticado. Não é possível salvar a cotação.")
            logging.error("Tentativa de salvar cotação sem utilizador autenticado.")
            return

        empresa_dados = {
            "nome": st.session_state.nome_empresa.strip(),
            "nuit": st.session_state.nuit_empresa.strip(),
            "endereco": st.session_state.endereco_empresa.strip(),
            "email": st.session_state.email_empresa.strip()
        }

        # Gerar PDF
        pdf_cotacao_bytes = gerar_pdf_cotacao_fpdf(empresa_dados, st.session_state.itens_cotacao)

        if pdf_cotacao_bytes:
            nome_arquivo_cotacao_pdf = f"cotacao_{st.session_state.nome_empresa.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

            try:
                # Salvar o PDF no Supabase Storage
                supabase.storage.from_("cotacoes-pdfs").upload(
                    nome_arquivo_cotacao_pdf, pdf_cotacao_bytes, {"ContentType": "application/pdf"}
                )

                # Obter URL pública do PDF
                public_url_pdf = supabase.storage.from_("cotacoes-pdfs").get_public_url(nome_arquivo_cotacao_pdf)

                # Salvar os detalhes da cotação na tabela 'cotacoes'
                cotacao_data_db = {
                    "data_cotacao": datetime.now().isoformat(),
                    "nome_empresa": st.session_state.nome_empresa.strip(),
                    "nuit_empresa": st.session_state.nuit_empresa.strip(),
                    "endereco_empresa": st.session_state.endereco_empresa.strip(),
                    "email_empresa": st.session_state.email_empresa.strip(),
                    "itens_cotacao": st.session_state.itens_cotacao,
                    "total_cotacao": total_cotacao,
                    "pdf_url": public_url_pdf if public_url_pdf else None,
                    "user_id": current_user_id
                }

                response_db = supabase.table("cotacoes").insert(cotacao_data_db).execute()

                st.success("PDF da cotação gerado e salvo no Supabase Storage e detalhes salvos na base de dados!")

                # Botão de download direto
                if st.download_button(
                    label="⬇️ Baixar Cotação PDF",
                    data=pdf_cotacao_bytes,
                    file_name=nome_arquivo_cotacao_pdf,
                    mime="application/pdf"
                ):
                    # Limpar dados apenas após o download
                    st.session_state.itens_cotacao = []
                    st.session_state.nome_empresa = ""
                    st.session_state.nuit_empresa = ""
                    st.session_state.endereco_empresa = ""
                    st.session_state.email_empresa = ""

            except Exception as e:
                st.error(f"Erro ao salvar cotação ou PDF: {e}")
                logging.error(f"Erro ao salvar cotação ou PDF: {e}")
        else:
            st.error("Erro ao gerar PDF da cotação.")

    st.divider()
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)



def calcular_custo_produtos_vendidos(vendas_df, produtos_df):
    if vendas_df.empty or produtos_df.empty:
        return 0
    total_cpv = 0
    custo_por_id = produtos_df.set_index('id')['custo'].to_dict()
    for _, venda in vendas_df.iterrows():
        itens = venda['detalhes_itens']
        for item in itens:
            produto_id = item.get('id')
            quantidade = item.get('quantidade', 0)
            custo_unitario = custo_por_id.get(produto_id, item.get('custo', 0))
            if custo_unitario == 0 and 'custo' not in produtos_df.columns:
                logging.warning(f"Custo para o produto ID {produto_id} não encontrado na tabela 'produtos' ou 'detalhes_itens'. Considerado 0 para CPV.")
            total_cpv += custo_unitario * quantidade
    return total_cpv

def analisar_rentabilidade(vendas, custos_produtos_vendidos, despesas_fixas, despesas_variaveis, impostos):
    margem_contribuicao_total = vendas - custos_produtos_vendidos - despesas_variaveis
    margem_contribuicao_percentual = (margem_contribuicao_total / vendas) if vendas > 0 else 0
    lucro_operacional = margem_contribuicao_total - despesas_fixas
    resultado_liquido_final = lucro_operacional - impostos
    ponto_equilibrio_mzn = despesas_fixas / margem_contribuicao_percentual if margem_contribuicao_percentual > 0 else float('inf')
    return {
        "margem_contribuicao_total": margem_contribuicao_total,
        "margem_contribuicao_percentual": margem_contribuicao_percentual,
        "lucro_operacional": lucro_operacional,
        "resultado_liquido_final": resultado_liquido_final,
        "ponto_equilibrio_mzn": ponto_equilibrio_mzn
    }


def pagina_graficos_visuais():
    st.image("logo.png", width=150)
    st.subheader("📊 Relatórios Contabilísticos e Gráficos Visuais")
    st.markdown("""
    Este relatório apresenta uma visão consolidada das operações financeiras da farmácia, combinando um balancete simplificado com gráficos e visualizações interativas abrangentes.
    """)

    # 1. Seleção de Período para o Relatório Completo
    st.header("1. Seleção de Período")
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data de Início", datetime.now().date().replace(day=1) - timedelta(days=90), key="rel_data_inicio")
    with col2:
        data_fim = st.date_input("Data de Fim", datetime.now().date(), key="rel_data_fim")

    # Carregar todos os dados de vendas e produtos
    df_vendas_raw = carregar_dados_contabilidade_vendas()
    df_produtos = carregar_dados_produtos()

    if df_vendas_raw.empty:
        st.info("Não há dados de vendas disponíveis no Supabase para gerar o relatório.")
        return

    # Filtrar vendas pelo período selecionado para todo o relatório
    df_vendas_filtrado = df_vendas_raw[
        (df_vendas_raw['data_dia'] >= data_inicio) &
        (df_vendas_raw['data_dia'] <= data_fim)
    ].copy()

    if df_vendas_filtrado.empty:
        st.info(f"Não há vendas registradas entre {data_inicio.strftime('%d/%m/%Y')} e {data_fim.strftime('%d/%m/%Y')} para este relatório.")
        return

    # --- Cálculos Financeiros para o Balancete e Resumo ---
    total_vendas = df_vendas_filtrado['total'].sum()
    custos_produtos_vendidos_reais = calcular_custo_produtos_vendidos(df_vendas_filtrado, df_produtos)

    st.markdown("---")
    st.header("2. Configuração de Despesas")
    #st.info(" podes importar ajs tabelas dentro do Supabase sendo as tabelas específicas (despesas_fixas, despesas_variaveis, impostos_pagos).")
    despesas_fixas_input = st.number_input("Despesas Fixas Totais (MZN)", value=25000.0, min_value=0.0, key="despesas_fixas")
    despesas_variaveis_input = st.number_input("Outras Despesas Variáveis (MZN)", value=48000.0, min_value=0.0, key="despesas_variaveis")
    impostos_input = st.number_input("Impostos Pagos (MZN)", value=9200.0, min_value=0.0, key="impostos_pagos")

    analise = analisar_rentabilidade(
        vendas=total_vendas,
        custos_produtos_vendidos=custos_produtos_vendidos_reais,
        despesas_fixas=despesas_fixas_input,
        despesas_variaveis=despesas_variaveis_input,
        impostos=impostos_input
    )

    st.markdown("---")
    st.header("3. Balancete Simplificado")
    balancete_df = pd.DataFrame({
        "Categoria": [
            "Vendas Brutas",
            "Custo dos Produtos Vendidos (CPV)",
            "Outras Despesas Variáveis",
            "Margem de Contribuição",
            "Despesas Fixas",
            "Lucro Operacional",
            "Impostos Pagos",
            "Resultado Líquido Final"
        ],
        "Valor (MZN)": [
            total_vendas,
            custos_produtos_vendidos_reais,
            despesas_variaveis_input,
            analise["margem_contribuicao_total"],
            despesas_fixas_input,
            analise["lucro_operacional"],
            impostos_input,
            analise["resultado_liquido_final"]
        ]
    })
    st.dataframe(balancete_df.set_index("Categoria"), use_container_width=True)

    st.markdown("---")
    st.header("4. Resumo Financeiro e Análise de Rentabilidade")
    col_metric1, col_metric2, col_metric3 = st.columns(3)
    col_metric1.metric("📈 **Vendas Totais (MZN)**", f"{total_vendas:,.2f} MZN")
    col_metric2.metric("💲 **Margem de Contribuição (MZN)**", f"{analise['margem_contribuicao_total']:,.2f} MZN")
    col_metric3.metric("💰 **Lucro Operacional (MZN)**", f"{analise['lucro_operacional']:,.2f} MZN")
    
    col_metric4, col_metric5 = st.columns(2)
    col_metric4.metric("💵 **Resultado Líquido Final (MZN)**", f"{analise['resultado_liquido_final']:,.2f} MZN")
    col_metric5.metric("🎯 **Ponto de Equilíbrio (MZN)**", f"{analise['ponto_equilibrio_mzn']:,.2f} MZN")

    st.markdown(f"""
    - **Margem de Contribuição Percentual**: **{analise['margem_contribuicao_percentual']:.2%}**
    """)

    # Exemplo de comparação com período anterior (simulado - ajuste para dados reais se houver)
    vendas_periodo_anterior_simulado = 110000
    if vendas_periodo_anterior_simulado > 0:
        comparacao_percentual_simulado = ((total_vendas - vendas_periodo_anterior_simulado) / vendas_periodo_anterior_simulado) * 100
        if comparacao_percentual_simulado >= 0:
            st.success(f"**Crescimento de Vendas em relação ao período anterior**: **+{comparacao_percentual_simulado:.2f}%**")
        else:
            st.error(f"**Redução de Vendas em relação ao período anterior**: **{comparacao_percentual_simulado:.2f}%**")

    st.header("5. Visualizações de Dados")

    # Gráfico de Vendas ao Longo do Tempo
    st.write("### 📈 Tendência de Vendas Diárias")
    vendas_por_dia = df_vendas_filtrado.groupby('data_dia')['total'].sum().reset_index()
    vendas_por_dia.columns = ['Data', 'Vendas (MZN)']
    fig_line = px.line(vendas_por_dia, x='Data', y='Vendas (MZN)', 
                       title='Vendas Totais por Dia no Período')
    fig_line.update_layout(xaxis_title="Data", yaxis_title="Vendas (MZN)")
    st.plotly_chart(fig_line, use_container_width=True)

    # Gráfico de Distribuição de Vendas por Cliente
    st.write("### 👥 Distribuição Percentual de Vendas por Cliente")
    vendas_cliente = df_vendas_filtrado.groupby("nome_cliente")["total"].sum().reset_index()
    if not vendas_cliente.empty:
        fig_pizza = px.pie(vendas_cliente, values="total", names="nome_cliente",
                           title="Vendas por Cliente",
                           hole=0.3)
        fig_pizza.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pizza, use_container_width=True)
    else:
        st.info("Nenhum dado de vendas por cliente para exibir.")

    # Gráfico de Ranking de Clientes
    st.write("### 🏅 Top 10 Clientes por Vendas")
    vendas_cliente_rank = vendas_cliente.sort_values(by="total", ascending=False).head(10)
    if not vendas_cliente_rank.empty:
        fig_bar_rank = px.bar(vendas_cliente_rank, x="nome_cliente", y="total", text_auto=True,
                              labels={"nome_cliente": "Cliente", "total": "Total (MZN)"},
                              title="Top 10 Clientes por Vendas")
        fig_bar_rank.update_layout(xaxis_title="Cliente", yaxis_title="Total de Vendas (MZN)")
        st.plotly_chart(fig_bar_rank, use_container_width=True)
    else:
        st.info("Nenhum dado de ranking de clientes para exibir.")

    # Gráficos de Vendas por Produto (Quantidade e Valor)
    st.write("### 💊 Análise de Vendas por Produto")
    todos_itens = []
    for index, row in df_vendas_filtrado.iterrows():
        if 'detalhes_itens' in row and isinstance(row['detalhes_itens'], list) and row['detalhes_itens']:
            for item in row['detalhes_itens']:
                todos_itens.append({
                    'nome': item.get('nome'),
                    'quantidade': item.get('quantidade', 0),
                    'preco_unitario': item.get('preco', 0)
                })
            
    if todos_itens:
        df_itens = pd.DataFrame(todos_itens)
        
        # Gráfico de Quantidade Vendida por Produto
        st.write("#### Quantidade Total de Produtos Vendidos")
        vendas_produto_quantidade = df_itens.groupby("nome")["quantidade"].sum().reset_index()
        fig_bar_prod_qty = px.bar(vendas_produto_quantidade, x="nome", y="quantidade", text_auto=True,
                                labels={"nome": "Produto", "quantidade": "Quantidade Vendida"},
                                title="Quantidade Total de Produtos Vendidos")
        fig_bar_prod_qty.update_layout(xaxis_title="Produto", yaxis_title="Quantidade Vendida")
        st.plotly_chart(fig_bar_prod_qty, use_container_width=True)

        # Gráfico de Valor Total de Vendas por Produto
        st.write("#### Valor Total de Vendas por Produto")
        df_itens['valor_total_item'] = df_itens['quantidade'] * df_itens['preco_unitario']
        vendas_produto_valor = df_itens.groupby("nome")["valor_total_item"].sum().reset_index()
        fig_bar_prod_val = px.bar(vendas_produto_valor, x="nome", y="valor_total_item", text_auto=True,
                                 labels={"nome": "Produto", "valor_total_item": "Valor Total (MZN)"},
                                 title="Valor Total de Vendas por Produto")
        fig_bar_prod_val.update_layout(xaxis_title="Produto", yaxis_title="Valor Total (MZN)")
        st.plotly_chart(fig_bar_prod_val, use_container_width=True)

    else:
        st.info("Nenhum dado detalhado de itens de venda para exibir gráficos de produtos.")

    st.header("6. Conclusão e Recomendações")

    if analise['resultado_liquido_final'] > 0:
        st.success(f"""
        A farmácia registrou um **resultado líquido positivo de {analise['resultado_liquido_final']:,.2f} MZN** neste período, indicando lucratividade.
        O volume de vendas de {total_vendas:,.2f} MZN superou o ponto de equilíbrio de {analise['ponto_equilibrio_mzn']:,.2f} MZN, o que é um indicador forte de saúde financeira.
        """)
    else:
        st.error(f"""
        A farmácia registrou um **resultado líquido negativo de {analise['resultado_liquido_final']:,.2f} MZN**, indicando um prejuízo neste período.
        As vendas de {total_vendas:,.2f} MZN ficaram **abaixo do ponto de equilíbrio** de {analise['ponto_equilibrio_mzn']:,.2f} MZN, o que significa que as receitas não foram suficientes para cobrir todos os custos e despesas.
        """)

    st.markdown("""
    **Recomendações:**
    - **Análise Detalhada de Custos:** Revisar os custos dos produtos vendidos e as despesas variáveis para identificar áreas de otimização.
    - **Estratégias de Vendas e Marketing:** Implementar ou intensificar campanhas para aumentar o volume de vendas e a receita total, visando consistentemente operar acima do ponto de equilíbrio.
    - **Gestão de Stock:** Monitorar o giro de stock e evitar excessos ou faltas, o que pode impactar o capital de giro e as vendas.
    """)

    st.divider() # Linha divisória opcional para separar o conteúdo do rodapé
    st.markdown("""
    © 2025 Centro Médico Cuidados de Confiança | Todos os direitos reservados.  
    Versão: 1.0  
    Desenvolvedor: Salomão Paulino Machaieie
    """)

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
