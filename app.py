import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
import numpy as np
from math import radians, sin, cos, sqrt, atan2

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="Localizador de Transportadoras",
    layout="wide",
    page_icon="🚛"
)

# Função para carregar dados do banco PostgreSQL
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

# Função para calcular distância (Haversine) - Versão vetorizada
def calcular_distancia_vetorizada(lat1, lon1, lats, lons):
    R = 6371.0  # Raio da Terra em km
    
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lats, lons = np.radians(lats), np.radians(lons)
    
    dlat = lats - lat1
    dlon = lons - lon1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lats) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c

# Interface principal
st.title("🚛 Localizador de Cargas por Proximidade")

# Sidebar
with st.sidebar:
    st.header("📍 Localização Atual do Caminhão")
    lat_user = st.number_input("Latitude atual", format="%.6f")
    lon_user = st.number_input("Longitude atual", format="%.6f")
    raio = st.slider("Mostrar quantas cidades mais próximas?", 1, 20, 5)
    buscar = st.button("🔎 Buscar cidade(s) mais próxima(s)")

# Executar busca
if buscar:
    if lat_user == 0.0 and lon_user == 0.0:
        st.warning("⚠️ Por favor, insira uma latitude e longitude válidas")
    else:
        df = carregar_dados_postgres()

        colunas_necessarias = [
            'cidade_origem', 'uf_origem', 'nome_grupo',
            'transportadora', 'empresa', 'contato',
            'ja_carregamos', 'temos_cadastro', 'produto',
            'preco', 'latitude', 'longitude'
        ]

        if df is None:
            st.stop()

        if not all(col in df.columns for col in colunas_necessarias):
            st.error("❌ A tabela não possui todas as colunas necessárias.")
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
            map_df = df_mais_proximas[['latitude', 'longitude']].rename(
                columns={"latitude": "lat", "longitude": "lon"}
            )
            st.map(map_df)
