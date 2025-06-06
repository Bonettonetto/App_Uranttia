import streamlit as st
import pandas as pd
import psycopg2
from math import radians, sin, cos, sqrt, atan2
import os
from dotenv import load_dotenv
import numpy as np

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="Localizador de Transportadoras",
    layout="wide",
    page_icon="🚛"
)
""
# Carrega a base de municípios
@st.cache_data(ttl=86400)
def carregar_municipios():
    df = pd.read_csv("municipios.csv")
    df["nome"] = df["nome"].str.lower().str.strip()
    return df

# Cache para dados do PostgreSQL
@st.cache_data(ttl=3600)
def carregar_dados_postgres():
    try:
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            st.error("❌ URL do banco de dados não configurada")
            return None
        conn = psycopg2.connect(db_url)
        query = "SELECT * FROM app_transportadoras"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"❌ Erro ao conectar ao banco de dados: {str(e)}")
        return None
    

# Distância Haversine vetorizada
def calcular_distancia_vetorizada(lat1, lon1, lats, lons):
    R = 6371.0
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lats, lons = np.radians(lats), np.radians(lons)
    dlat = lats - lat1
    dlon = lons - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lats) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c

# Retorna coordenadas a partir da cidade + UF
def buscar_coordenadas_local(cidade, uf, resultado):
    df_uf = resultado[resultado["uf"] == uf.upper()]
    cidade_normalizada = remover_acentos(cidade).upper().strip()
    correspondencias = df_uf["municipio"].apply(lambda x: fuzz.ratio(remover_acentos(x).upper().strip(), cidade_normalizada))
    melhor_idx = correspondencias.idxmax()
    if correspondencias[melhor_idx] >= 80:
        return df_uf.loc[melhor_idx, "latitude"], df_uf.loc[melhor_idx, "longitude"]
    return None, None


def uf_para_codigo(uf):
    mapa = {
        'RO': 11, 'AC': 12, 'AM': 13, 'RR': 14, 'PA': 15, 'AP': 16, 'TO': 17,
        'MA': 21, 'PI': 22, 'CE': 23, 'RN': 24, 'PB': 25, 'PE': 26, 'AL': 27,
        'SE': 28, 'BA': 29, 'MG': 31, 'ES': 32, 'RJ': 33, 'SP': 35, 'PR': 41,
        'SC': 42, 'RS': 43, 'MS': 50, 'MT': 51, 'GO': 52, 'DF': 53
    }
    return mapa.get(uf)

# Validação
def validar_uf(uf):
    return uf.upper() in ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']

# Interface
st.title("🚛 Localizador de Cargas por Proximidade")

# Carrega dados do banco
df = carregar_dados_postgres()
if df is None:
    st.error("❌ Não foi possível carregar os dados do banco de dados")
    st.stop()

# Exibe a tabela com filtros
st.subheader("📋 Base de Dados de Transportadoras")

# Adiciona filtros
col1, col2 = st.columns(2)
with col1:
    uf_filtro = st.selectbox(
        "Filtrar por UF",
        ["Todas"] + sorted(df["uf_origem"].unique().tolist())
    )
with col2:
    termo_busca = st.text_input("🔍 Buscar por nome da transportadora ou cidade", "")

# Aplica filtros
df_filtrado = df.copy()
if uf_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado["uf_origem"] == uf_filtro]
if termo_busca:
    termo_busca = termo_busca.lower()
    df_filtrado = df_filtrado[
        df_filtrado["transportadora"].str.lower().str.contains(termo_busca) |
        df_filtrado["cidade_origem"].str.lower().str.contains(termo_busca)
    ]

# Exibe a tabela com paginação
st.dataframe(
    df_filtrado[[
        "cidade_origem", "uf_origem", "transportadora",
        "nome_grupo", "contato", "produto", "preco"
    ]].rename(columns={
        "cidade_origem": "Cidade",
        "uf_origem": "UF",
        "transportadora": "Transportadora",
        "nome_grupo": "Grupo WhatsApp",
        "contato": "Contato",
        "produto": "Produto",
        "preco": "Preço"
    }),
    use_container_width=True,
    hide_index=True
)

# Exibe estatísticas
st.caption(f"Total de registros: {len(df_filtrado)}")

with st.sidebar:
    st.header("📍 Localização Atual do Caminhão")
    cidade_input = st.text_input("Cidade atual", placeholder="Ex: São Paulo")
    uf_input = st.text_input("UF", placeholder="Ex: SP", max_chars=2)
    raio = st.slider("Mostrar quantas cidades mais próximas?", 1, 20, 5)
    buscar = st.button("🔎 Buscar cidade(s) mais próxima(s)")

if buscar:
    if not cidade_input or not uf_input:
        st.warning("⚠️ Por favor, preencha cidade e UF")
    elif not validar_uf(uf_input):
        st.error("❌ UF inválida")
    else:
        municipios_df = carregar_municipios()
        lat_user, lon_user = buscar_coordenadas_local(cidade_input, uf_input, municipios_df)

        if lat_user is None:
            st.warning("⚠️ Coordenadas não encontradas para esta cidade/UF.")
        else:
            df = df.dropna(subset=['latitude', 'longitude'])

            df['Distancia_km'] = calcular_distancia_vetorizada(
                lat_user, lon_user,
                df['latitude'].values,
                df['longitude'].values
            )

            df_mais_proximas = df.sort_values("Distancia_km").head(raio)

            st.success(f"✅ Encontradas {len(df_mais_proximas)} transportadoras próximas")
            
            cols = st.columns(2)
            for idx, row in df_mais_proximas.iterrows():
                with cols[idx % 2]:
                    st.info(f"📍 {row['cidade_origem']}/{row['uf_origem']} - {row['Distancia_km']:.2f} km")
                    st.write(f"**Grupo de WhatsApp:** {row['nome_grupo']}")
                    st.write(f"**Transportadora:** {row['transportadora']}")
                    st.write(f"**Contato:** {row['contato']}")
                    st.markdown("---")

            st.subheader("🗺️ Localizações no Mapa")
            map_df = df_mais_proximas[['latitude', 'longitude']].rename(columns={"latitude": "lat", "longitude": "lon"})
            st.map(map_df)
