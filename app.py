import streamlit as st
import pandas as pd
import psycopg2
import requests
from math import radians, sin, cos, sqrt, atan2
import os
from dotenv import load_dotenv
import numpy as np
import json
from pathlib import Path

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="Localizador de Transportadoras",
    layout="wide",
    page_icon="🚛"
)

# Cache para geocodificação
CACHE_FILE = "geocoding_cache.json"

def carregar_cache_geocodificacao():
    if Path(CACHE_FILE).exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def salvar_cache_geocodificacao(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

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

        # Padronizar nomes de colunas para evitar erros com maiúsculas
        df.columns = [col.lower() for col in df.columns]
        return df
    except Exception as e:
        st.error(f"❌ Erro ao conectar ao banco de dados: {str(e)}")
        return None

# Cálculo vetorizado de distância
def calcular_distancia_vetorizada(lat1, lon1, lats, lons):
    R = 6371.0
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lats, lons = np.radians(lats), np.radians(lons)
    dlat = lats - lat1
    dlon = lons - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lats) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c

# Geocodificação via OpenCage com cache
def geocodificar_cidade(cidade, uf, api_key=None):
    # Carregar cache
    cache = carregar_cache_geocodificacao()
    
    # Criar chave única para a cidade/UF
    cache_key = f"{cidade.lower()}_{uf.lower()}"
    
    # Verificar se já temos no cache
    if cache_key in cache:
        return cache[cache_key]['lat'], cache[cache_key]['lon']
    
    # Se não temos no cache, usar API
    try:
        # Usar API key do ambiente se não fornecida
        api_key = api_key or os.getenv('OPENCAGE_API_KEY')
        if not api_key:
            st.error("❌ Chave da API OpenCage não configurada")
            return None, None
            
        url = f"https://api.opencagedata.com/geocode/v1/json?q={cidade},+{uf},+Brasil&key={api_key}&language=pt&limit=1"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data['results']:
            geometry = data['results'][0]['geometry']
            lat, lon = geometry['lat'], geometry['lng']
            
            # Salvar no cache
            cache[cache_key] = {'lat': lat, 'lon': lon}
            salvar_cache_geocodificacao(cache)
            
            return lat, lon
        else:
            st.warning("⚠️ Cidade não encontrada")
            return None, None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro na API de geocodificação: {str(e)}")
        return None, None

# Validar UF
def validar_uf(uf):
    ufs_validas = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']
    return uf.upper() in ufs_validas

# Interface
st.title("🚛 Localizador de Cargas por Proximidade")

# Sidebar
with st.sidebar:
    st.header("📍 Localização Atual do Caminhão")
    cidade_input = st.text_input("Cidade atual", placeholder="Ex: São Paulo")
    uf_input = st.text_input("UF", placeholder="Ex: SP", max_chars=2)
    
    # Mostrar campo de API key apenas se não estiver configurada no ambiente
    if not os.getenv('OPENCAGE_API_KEY'):
        api_key = st.text_input("Chave da API OpenCage", type="password")
    else:
        api_key = None
        
    raio = st.slider("Mostrar quantas cidades mais próximas?", 1, 20, 5)
    buscar = st.button("🔎 Buscar cidade(s) mais próxima(s)")

# Executar busca
if buscar:
    if not cidade_input or not uf_input:
        st.warning("⚠️ Por favor, preencha cidade e UF")
    elif not validar_uf(uf_input):
        st.error("❌ UF inválida")
    elif not api_key and not os.getenv('OPENCAGE_API_KEY'):
        st.warning("⚠️ Por favor, insira a chave da API")
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

        st.write("Colunas carregadas do banco:")
        st.write(df.columns.tolist())

        if not all(col in df.columns for col in colunas_necessarias):
            st.error("❌ A tabela não possui todas as colunas necessárias.")
            st.stop()

        # Geocodificação
        lat_user, lon_user = geocodificar_cidade(cidade_input, uf_input, api_key)
        st.write("Localização atual:", lat_user, lon_user)

        if lat_user is None or lon_user is None:
            st.stop()

        df = df.dropna(subset=['latitude', 'longitude'])
        st.write("Exemplo de coordenadas do banco:")
        st.write(df[['cidade_origem', 'latitude', 'longitude']].head())

        if df.empty:
            st.warning("⚠️ Nenhum dado com coordenadas encontrado no banco.")
            st.stop()

        # Calcular distância
        df['distancia_km'] = calcular_distancia_vetorizada(
            lat_user, lon_user,
            df['latitude'].values,
            df['longitude'].values
        )

        df_mais_proximas = df.sort_values("distancia_km").head(raio)

        st.success(f"✅ Encontradas {len(df_mais_proximas)} transportadoras próximas")

        # Exibir resultados
        cols = st.columns(2)
        for idx, row in df_mais_proximas.iterrows():
            with cols[idx % 2]:
                st.info(f"📍 {row['cidade_origem']}/{row['uf_origem']} - {row['distancia_km']:.2f} km")
                st.write(f"**Grupo de WhatsApp:** {row['nome_grupo']}")
                st.write(f"**Transportadora:** {row['transportadora']}")
                st.write(f"**Contato:** {row['contato']}")
                st.markdown("---")

        # Mapa (se houver dados)
        st.subheader("🗺️ Localizações no Mapa")
        if not df_mais_proximas.empty:
            map_df = df_mais_proximas[['latitude', 'longitude']].rename(
                columns={'latitude': 'lat', 'longitude': 'lon'}
            )
            st.map(map_df)
        else:
            st.warning("⚠️ Nenhuma localização para exibir no mapa.")
