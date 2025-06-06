import pandas as pd
import psycopg2
import os
import unicodedata
from dotenv import load_dotenv
from fuzzywuzzy import process

# Carrega variáveis de ambiente
load_dotenv()
db_url = os.getenv("DATABASE_URL")

def remover_acentos(texto):
    if pd.isna(texto):
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8")

import unicodedata

def remover_acentos(texto):
    if pd.isna(texto):
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8")


try:
    # 1. Carrega a base de municípios com sigla da UF
    df_coords = pd.read_csv("Municipios.csv", dtype={"nome": str, "uf": str, "latitude": float, "longitude": float})
    df_coords["nome_normalizado"] = df_coords["nome"].apply(remover_acentos).str.upper().str.strip()
    df_coords["uf"] = df_coords["uf"].str.upper().str.strip()

    # 2. Lê a planilha da transportadora
    df = pd.read_excel("App_transportadora.xlsx")
    df["Cidade_origem_normalizada"] = df["Cidade_origem"].apply(remover_acentos).str.upper().str.strip()
    df["UF_origem"] = df["UF_origem"].str.upper().str.strip()

    # 3. Função para buscar coordenadas com fuzzy matching
    def buscar_coordenadas(cidade, uf):
        candidatos = df_coords[df_coords["uf"] == uf]
        if candidatos.empty:
            return None, None
        resultado = process.extractOne(cidade, candidatos["nome_normalizado"])
        if resultado and resultado[1] >= 80:
            cidade_match = resultado[0]
            match_row = candidatos[candidatos["nome_normalizado"] == cidade_match].iloc[0]
            return match_row["latitude"], match_row["longitude"]
        return None, None

    # 4. Aplica busca linha a linha
    latitudes, longitudes = [], []
    falhas = []

    for _, row in df.iterrows():
        lat, lon = buscar_coordenadas(row["Cidade_origem_normalizada"], row["UF_origem"])
        latitudes.append(lat)
        longitudes.append(lon)
        if lat is None or lon is None:
            falhas.append(f"{row['Cidade_origem']} / {row['UF_origem']}")

    df["Latitude"] = latitudes
    df["Longitude"] = longitudes
    df_final = df.dropna(subset=["Latitude", "Longitude"])

    # 5. Conecta ao PostgreSQL e insere dados
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM app_transportadoras")

    for _, row in df_final.iterrows():
        cursor.execute("""
            INSERT INTO app_transportadoras (
                cidade_origem, uf_origem, nome_grupo, transportadora,
                empresa, contato, ja_carregamos, temos_cadastro,
                produto, preco, latitude, longitude
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row['Cidade_origem'], row['UF_origem'], row['Nome_grupo'], row['Transportadora'],
            row['Empresa'], row['Contato'], row['Ja_carregamos'], row['Temos_cadastro'],
            row['Produto'], row['Preco'], row['Latitude'], row['Longitude']
        ))

    conn.commit()
    cursor.close()
    conn.close()

    if falhas:
        print("❌ Cidades que não foram localizadas com fuzzy matching:")
        for item in falhas:
            print(f"- {item}")
    print(f"🔢 Total de registros prontos para inserção: {len(df_final)}")
    print("✅ Dados atualizados com sucesso!")

except FileNotFoundError as e:
    print(f"❌ Erro: Arquivo não encontrado - {str(e)}")
except Exception as e:
    print(f"❌ Erro inesperado: {str(e)}")
