import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()
db_url = os.getenv("DATABASE_URL")

# 1. Carrega a base de coordenadas das cidades
df_coords = pd.read_csv("municipios.csv")
df_coords["nome"] = df_coords["nome"].str.upper()
df_coords["uf"] = df_coords["uf"].str.upper()

# 2. Lê a planilha com os dados da transportadora
df = pd.read_excel("App_transportadora.xlsx")

# 3. Padroniza nomes para merge
df["Cidade_origem"] = df["Cidade_origem"].str.upper()
df["UF_origem"] = df["UF_origem"].str.upper()

# 4. Faz merge para incluir Latitude e Longitude
df_merge = pd.merge(
    df,
    df_coords[["nome", "uf", "latitude", "longitude"]],
    left_on=["Cidade_origem", "UF_origem"],
    right_on=["nome", "uf"],
    how="left"
)

# 5. Remove colunas extras e renomeia
df_merge = df_merge.drop(columns=["nome", "uf"])
df_merge = df_merge.rename(columns={"latitude": "Latitude", "longitude": "Longitude"})

# 6. Remove linhas sem coordenadas
df_merge = df_merge.dropna(subset=["Latitude", "Longitude"])

# 7. Conecta ao PostgreSQL
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

# 8. Limpa a tabela
cursor.execute("DELETE FROM app_transportadoras")

# 9. Insere os dados atualizados
for _, row in df_merge.iterrows():
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

print("✅ Dados atualizados com base local (sem API).")
