import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import io

# --- Configuração da Página ---
# Define o título da página, o ícone e o layout
st.set_page_config(
    page_title="Dashboard de Panetones Bauducco",
    page_icon="🎄",
    layout="wide"
)

# --- Carregamento dos Dados ---
# Usamos @st.cache_data para que os dados sejam carregados apenas uma vez,
# melhorando a performance do app.
@st.cache_data
def gerar_dados_panetone():
    """Função para gerar dados de exemplo de vendas de panetone."""
    meses = ['2023-10', '2023-11', '2023-12', '2024-01']
    produtos = ['Panettone Original', 'Chocottone', 'Pandoro', 'Panettone de Frutas Especiais']
    
    dados = []
    for mes in meses:
        for produto in produtos:
            # Simula o aumento das vendas perto do Natal
            if mes in ['2023-11', '2023-12']:
                vendas = np.random.randint(5000, 15000)
            else:
                vendas = np.random.randint(1000, 4000)
            dados.append({'MesAno': mes, 'Produto': produto, 'Vendas': vendas})
            
    df = pd.DataFrame(dados)
    df = df.sort_values(by="MesAno")
    return df

def criar_banco_de_dados_exemplo():
    """Cria um banco de dados SQLite de exemplo se ele não existir."""
    db_file = 'vendas.db'
    if not os.path.exists(db_file):
        st.toast(f"Criando banco de dados de exemplo '{db_file}'...")
        import sqlite3
        conn = sqlite3.connect(db_file)
        df_exemplo = gerar_dados_panetone()
        df_exemplo.to_sql('vendas', conn, if_exists='replace', index=False)
        conn.close()

# --- Lógica Principal do App ---

# Cria o BD de exemplo na primeira execução, se necessário.
criar_banco_de_dados_exemplo()

st.title("📊 Dashboard de Análise de Vendas")

# --- Barra Lateral para Carregar Dados e Filtros ---
st.sidebar.header("Fonte dos Dados")
source = st.sidebar.radio(
    "Escolha a fonte dos seus dados",
    ("Usar dados de exemplo (Bauducco)", "Carregar minha planilha (.xlsx)", "Conectar a um Banco de Dados")
)

df = None
produto_col, vendas_col, mes_col, categoria_col = 'Produto', 'Vendas', 'MesAno', None

if source == "Carregar minha planilha (.xlsx)":
    # Usamos uma chave para ter mais controle sobre o estado do uploader
    uploaded_file = st.sidebar.file_uploader("Arraste ou selecione seu arquivo Excel", type="xlsx", key="file_uploader")

    @st.cache_data
    def carregar_planilha(file):
        """Lê o arquivo Excel e remove colunas vazias."""
        df = pd.read_excel(file, engine='openpyxl')
        df = df.dropna(axis='columns', how='all')
        return df

    if uploaded_file is not None:
        try:
            df_uploaded = carregar_planilha(uploaded_file)
            with st.spinner("Analisando sua planilha..."):
                st.sidebar.success("Planilha carregada!")
                
                available_cols = df_uploaded.columns.tolist()
                cols_com_opcional = ["[Nenhuma]"] + available_cols

                with st.sidebar.expander("⚙️ Ajustar Mapeamento de Colunas", expanded=True):
                    # Seletores para o usuário mapear as colunas
                    produto_col = st.selectbox("Coluna de 'Produto'", available_cols, index=0)
                    vendas_col = st.selectbox("Coluna de 'Vendas'", available_cols, index=min(1, len(available_cols)-1))
                    mes_col = st.selectbox("Coluna de 'Mês/Ano'", available_cols, index=min(2, len(available_cols)-1))
                    categoria_col = st.selectbox("Coluna de 'Categoria' (Opcional)", cols_com_opcional, index=0)

                # Define o DataFrame principal como a planilha carregada
                df = df_uploaded

        except Exception as e:
            st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
            st.stop()
elif source == "Conectar a um Banco de Dados":
    st.sidebar.info("Carregue um arquivo de banco de dados SQLite (.db, .sqlite) para análise.")
    db_file = st.sidebar.file_uploader("Selecione seu arquivo de banco de dados", type=['db', 'sqlite', 'sqlite3'])

    if db_file is not None:
        # Salva o arquivo carregado temporariamente para que o SQLAlchemy possa acessá-lo
        temp_db_path = f"./{db_file.name}"
        with open(temp_db_path, "wb") as f:
            f.write(db_file.getvalue())
        
        query_padrao = "SELECT * FROM vendas;" # Sugere uma consulta genérica
        query = st.sidebar.text_area("Sua consulta SQL:", query_padrao, height=150)

        if st.sidebar.button("Executar Consulta"):
            try:
                # Conecta ao banco de dados que o usuário carregou
                conn_url = f'sqlite:///{temp_db_path}'
                conn = st.connection(f'db_{db_file.name}', type='sql', url=conn_url, ttl=1) # ttl=1 para forçar a releitura
                # Salva o DataFrame no estado da sessão para persistir entre as interações
                st.session_state.df_db = conn.query(query)
                st.sidebar.success("Consulta executada!")
            except Exception as e:
                st.error(f"Erro ao executar a consulta: {e}")
                st.stop()
    if 'df_db' in st.session_state:
        df = st.session_state.df_db # Usa o DataFrame salvo na sessão
    else:
        st.info("Aguardando o carregamento de um arquivo de banco de dados na barra lateral.")
else:
    df = gerar_dados_panetone()

if df is not None:
    # Validação dos Dados
    if vendas_col not in df.columns or not pd.api.types.is_numeric_dtype(df[vendas_col]):
        st.error(f"A coluna '{vendas_col}' selecionada para 'Vendas' não é numérica. Por favor, corrija o mapeamento.")
        st.stop()

    # Ordena os dados pela coluna de mês
    if mes_col in df.columns:
        df = df.sort_values(by=mes_col)

    st.sidebar.header("Filtros do Dashboard")
    st.sidebar.markdown("---")
    
    # Filtro de produtos (agora funciona para qualquer dado)
    df_filtrado = df.copy()
    if produto_col in df_filtrado.columns:
        lista_produtos = df_filtrado[produto_col].unique()
        produtos_selecionados = st.sidebar.multiselect(f"Filtrar por '{produto_col}'", options=lista_produtos, default=lista_produtos)
        df_filtrado = df_filtrado[df_filtrado[produto_col].isin(produtos_selecionados)]

    st.sidebar.markdown("---")
    st.sidebar.header("Tipo de Gráfico")
    chart_type = st.sidebar.selectbox(
        "Escolha a visualização",
        ("Gráfico de Barras Animado", "Gráfico de Linhas (Evolução)", "Gráfico de Pizza (Participação)", "Gráfico de Treemap (Hierarquia)", "Gráfico de Área (Volume)")
    )

    if not df_filtrado.empty:
        # --- Métricas (KPIs) ---
        total_vendas = int(df_filtrado[vendas_col].sum())
        produto_mais_vendido = df_filtrado.groupby(produto_col)[vendas_col].sum().idxmax()
        total_produto_mais_vendido = int(df_filtrado.groupby(produto_col)[vendas_col].sum().max())

        st.markdown("##")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="💰 Total de Vendas", value=f"{total_vendas:,}".replace(",", "."))
        with col2:
            st.metric(label="🏆 Produto Destaque", value=str(produto_mais_vendido))
        with col3:
            st.metric(label="📈 Vendas do Destaque", value=f"{total_produto_mais_vendido:,}".replace(",", "."))

        st.markdown("---")

        # --- Criação do Gráfico ---
        st.header("Análise Visual das Vendas")

        if chart_type == "Gráfico de Barras Animado":
            # Adiciona o facet_col se uma categoria for selecionada
            facet_col_arg = categoria_col if categoria_col and categoria_col != "[Nenhuma]" else None
            fig = px.bar(
                df_filtrado,
                x=produto_col,
                y=vendas_col,
                color=produto_col,
                animation_frame=mes_col,
                animation_group=produto_col,
                range_y=[0, df_filtrado[vendas_col].max() * 1.15],
                labels={vendas_col: "Vendas", produto_col: "Produto", mes_col: "Mês"},
                text=vendas_col,
                facet_col=facet_col_arg # Divide o gráfico por categoria
            )
            fig.update_traces(
                texttemplate='%{text:,.0f}', 
                textposition='outside',
                marker_line_color='rgb(8,48,107)',
                marker_line_width=1.5, 
                opacity=0.8
            )
            fig.update_layout(
                title="Performance de Vendas por Produto ao Longo do Tempo",
                xaxis_title="Produto",
                yaxis_title="Unidades Vendidas",
                font=dict(size=14),
                plot_bgcolor='rgba(0,0,0,0)'
            )
        
        elif chart_type == "Gráfico de Linhas (Evolução)":
            fig = px.line(
                df_filtrado,
                x=mes_col,
                y=vendas_col,
                color=produto_col,
                title="Evolução das Vendas ao Longo do Tempo",
                labels={vendas_col: "Vendas", mes_col: "Mês", produto_col: "Produto"},
                markers=True # Adiciona marcadores para cada ponto de dado
            )
            fig.update_layout(
                xaxis_title="Tempo",
                yaxis_title="Vendas",
                font=dict(size=14),
                plot_bgcolor='rgba(0,0,0,0)'
            )

        elif chart_type == "Gráfico de Pizza (Participação)":
            df_pizza = df_filtrado.groupby(produto_col)[vendas_col].sum().reset_index()
            fig = px.pie(
                df_pizza,
                names=produto_col,
                values=vendas_col,
                title=f"Participação de Vendas por {produto_col}",
                hole=.4, # Cria um gráfico de "donut" que é visualmente mais moderno
                color_discrete_sequence=px.colors.sequential.RdBu
            )
            fig.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05] * len(df_pizza))
            fig.update_layout(
                font=dict(size=16),
            )

        elif chart_type == "Gráfico de Treemap (Hierarquia)":
            # Se uma categoria for selecionada, o treemap será hierárquico
            path = [categoria_col, produto_col] if categoria_col and categoria_col != "[Nenhuma]" else [produto_col]
            fig = px.treemap(
                df_filtrado,
                path=path,
                values=vendas_col,
                title=f"Hierarquia de Vendas",
                color=produto_col,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_traces(textinfo="label+value+percent root")
            fig.update_layout(
                font=dict(size=16),
            )

        elif chart_type == "Gráfico de Área (Volume)":
            fig = px.area(
                df_filtrado,
                x=mes_col,
                y=vendas_col,
                color=produto_col,
                title="Volume de Vendas ao Longo do Tempo",
                labels={vendas_col: "Vendas", mes_col: "Mês", produto_col: "Produto"},
                markers=True
            )
            fig.update_layout(
                xaxis_title="Tempo",
                yaxis_title="Vendas",
                font=dict(size=14),
                plot_bgcolor='rgba(0,0,0,0)'
            )


        st.plotly_chart(fig, use_container_width=True)

        # --- Rodapé ---
        st.markdown("---")
        st.write("Dashboard interativo para análise de vendas sazonais.")

        # --- Funcionalidade de Exportação ---
        st.sidebar.markdown("---")
        st.sidebar.header("Exportar Dados Filtrados")

        # Função para converter o DataFrame para Excel em memória
        @st.cache_data
        def to_excel(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Dados')
            return output.getvalue()

        excel_data = to_excel(df_filtrado)
        st.sidebar.download_button(
            label="📥 Baixar como Excel (.xlsx)",
            data=excel_data,
            file_name='dados_filtrados.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        st.warning("Por favor, selecione pelo menos um produto no filtro para visualizar os dados.")
else:
    st.info("Aguardando carregamento de dados. Use as opções na barra lateral.")
