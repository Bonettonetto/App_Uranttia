import streamlit as st
import pandas as pd
import psycopg2
import requests
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

# Cache para melhorar performance
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
    
    # Converter para radianos
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lats, lons = np.radians(lats), np.radians(lons)
    
    # Calcular diferenças
    dlat = lats - lat1
    dlon = lons - lon1
    
    # Fórmula de Haversine vetorizada
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lats) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c

# Função para geocodificar a cidade do usuário via OpenCage
def geocodificar_cidade(cidade, uf, api_key):
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q={cidade},+{uf},+Brasil&key={api_key}&language=pt&limit=1"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data['results']:
            geometry = data['results'][0]['geometry']
            return geometry['lat'], geometry['lng']
        else:
            st.warning("⚠️ Cidade não encontrada")
            return None, None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro na API de geocodificação: {str(e)}")
        return None, None

# Função para validar UF
def validar_uf(uf):
    ufs_validas = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']
    return uf.upper() in ufs_validas

# Interface principal
st.title("🚛 Localizador de Cargas por Proximidade")

# Sidebar
with st.sidebar:
    st.header("📍 Localização Atual do Caminhão")
    cidade_input = st.text_input("Cidade atual", placeholder="Ex: São Paulo")
    uf_input = st.text_input("UF", placeholder="Ex: SP", max_chars=2)
    api_key = st.text_input("Chave da API OpenCage", type="password")
    raio = st.slider("Mostrar quantas cidades mais próximas?", 1, 20, 5)
    buscar = st.button("🔎 Buscar cidade(s) mais próxima(s)")

# Executar busca
if buscar:
    if not cidade_input or not uf_input:
        st.warning("⚠️ Por favor, preencha cidade e UF")
    elif not validar_uf(uf_input):
        st.error("❌ UF inválida")
    elif not api_key:
        st.warning("⚠️ Por favor, insira a chave da API")
    else:
        with st.spinner("Carregando dados..."):
            df = carregar_dados_postgres()
            
            if df is not None:
                colunas_necessarias = [
    'cidade_origem', 'uf_origem', 'nome_grupo',
    'transportadora', 'empresa', 'contato',
    'ja_carregamos', 'temos_cadastro', 'produto',
    'preco', 'latitude', 'longitude'
]
                if not all(col in df.columns for col in colunas_necessarias):
                    st.error("❌ A tabela não possui todas as colunas necessárias")
                else:
                    lat_user, lon_user = geocodificar_cidade(cidade_input, uf_input, api_key)

                    if lat_user is not None and lon_user is not None:
                        # Remover linhas com coordenadas nulas
                        df = df.dropna(subset=['Latitude', 'Longitude'])
                        
                        # Calcular distâncias de forma vetorizada
                        df['Distancia_km'] = calcular_distancia_vetorizada(
                            lat_user, lon_user,
                            df['Latitude'].values,
                            df['Longitude'].values
                        )

                        df_mais_proximas = df.sort_values("Distancia_km").head(raio)

                        # Exibir resultados
                        st.success(f"✅ Encontradas {len(df_mais_proximas)} transportadoras próximas")
                        
                        # Criar colunas para melhor organização
                        cols = st.columns(2)
                        
                        for idx, row in df_mais_proximas.iterrows():
                            with cols[idx % 2]:
                                st.info(f"📍 {row['Cidade_origem']}/{row['UF_origem']} - {row['Distancia_km']:.2f} km")
                                st.write(f"**Grupo de WhatsApp:** {row['Nome_grupo']}")
                                st.write(f"**Transportadora:** {row['Transportadora']}")
                                st.write(f"**Contato:** {row['Contato']}")
                                st.markdown("---")

                        # Mapa
                        st.subheader("🗺️ Localizações no Mapa")
                        map_df = df_mais_proximas[['Latitude', 'Longitude']].rename(
                            columns={"Latitude": "lat", "Longitude": "lon"}
                        )
                        st.map(map_df)

