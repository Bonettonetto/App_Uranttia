import streamlit as st
import pandas as pd
import psycopg2
import requests
from math import radians, sin, cos, sqrt, atan2

# Configuração da página
st.set_page_config(page_title="Localizador de Transportadoras", layout="wide")
st.title("🚛 Localizador de Cargas por Proximidade")



# Função para calcular distância (Haversine)
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0  # Raio da Terra em km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# Função para geocodificar a cidade do usuário via OpenCage
def geocodificar_cidade(cidade, uf, api_key):
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q={cidade},+{uf},+Brasil&key={api_key}&language=pt&limit=1"
        response = requests.get(url)
        data = response.json()
        if data['results']:
            geometry = data['results'][0]['geometry']
            return geometry['lat'], geometry['lng']
    except:
        return None, None

# Sidebar
with st.sidebar:
    st.header("📍 Localização Atual do Caminhão")
    cidade_input = st.text_input("Cidade atual")
    uf_input = st.text_input("UF")
    api_key = st.text_input("Chave da API OpenCage", type="password")
    raio = st.slider("Mostrar quantas cidades mais próximas?", 1, 20, 5)
    buscar = st.button("🔎 Buscar cidade(s) mais próxima(s)")

# Função para carregar dados do PostgreSQL
def carregar_dados_postgres():
    db_url = "postgresql://postgres:fbeJaAvEeoblqbNwqDhkXWIIKHLfUYZL@hopper.proxy.rlwy.net:25906/railway"
    conn = psycopg2.connect(db_url)
    query = "SELECT * FROM app_transportadoras"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Executar busca
if buscar and cidade_input and uf_input and api_key:
    df = carregar_dados_postgres()

    colunas_necessarias = ['Cidade_origem', 'UF_origem', 'Nome_grupo', 'Transportadora', 'Contato', 'Latitude', 'Longitude']
    if not all(col in df.columns for col in colunas_necessarias):
        st.error("❌ A tabela não possui todas as colunas necessárias.")
    else:
        lat_user, lon_user = geocodificar_cidade(cidade_input, uf_input, api_key)

        if lat_user is None or lon_user is None:
            st.error("Não foi possível localizar a cidade informada.")
        else:
            df = df.dropna(subset=['Latitude', 'Longitude'])
            df['Distancia_km'] = df.apply(lambda row: calcular_distancia(
                lat_user, lon_user, row['Latitude'], row['Longitude']), axis=1)

            df_mais_proximas = df.sort_values("Distancia_km").head(raio)

            for _, row in df_mais_proximas.iterrows():
                st.success(f"📍 {row['Cidade_origem']}/{row['UF_origem']} - {row['Distancia_km']:.2f} km")
                st.write(f"**Grupo de WhatsApp:** {row['Nome_grupo']}")
                st.write(f"**Transportadora:** {row['Transportadora']}")
                st.write(f"**Contato:** {row['Contato']}")
                st.markdown("---")

            # Mapa
            st.subheader("🗺️ Localizações no Mapa")
            map_df = df_mais_proximas[['Latitude', 'Longitude']].rename(columns={"Latitude": "lat", "Longitude": "lon"})
            st.map(map_df)

