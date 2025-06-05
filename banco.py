import pandas as pd
import requests
import psycopg2
import os
from dotenv import load_dotenv
from time import sleep

# Carrega variáveis de ambiente
load_dotenv()
db_url = os.getenv("DATABASE_URL")
api_key = os.getenv("OPENCAGE_KEY")  # você deve definir no .env

# Função para geocodificar com OpenCage
def geocodificar(cidade, uf):
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q={cidade},+{uf},+Brasil&key={api_key}&language=pt&limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data['results']:
            coords = data['results'][0]['geometry']
            return coords['lat'], coords['lng']
    except:
        pass
    return None, None

# 1. Lê o Excel
df = pd.read_excel("App_transportadora.xlsx")

# 2. Preenche latitude e longitude
latitudes, longitudes = [], []
for _, row in df.iterrows():
    lat, lon = geocodificar(row['Cidade_origem'], row['UF_origem'])
    latitudes.append(lat)
    longitudes.append(lon)
    sleep(1.2)

df["Latitude"] = latitudes
df["Longitude"] = longitudes
df = df.dropna(subset=["Latitude", "Longitude"])

# 3. Conecta ao PostgreSQL
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

# 4. Carrega dados existentes
cursor.execute("SELECT * FROM app_transportadoras")
colunas = [desc[0] for desc in cursor.description]
dados_existentes = cursor.fetchall()
df_existente = pd.DataFrame(dados_existentes, columns=colunas)

# 5. Loop sobre novos dados
novos, atualizados = 0, 0

for _, row in df.iterrows():
    filtro = (
        (df_existente['cidade_origem'] == row['Cidade_origem']) &
        (df_existente['uf_origem'] == row['UF_origem'])
    )
    existente = df_existente[filtro]

    if existente.empty:
        # Inserir novo registro
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
        novos += 1
    else:
        # Comparar se há diferença e atualizar
        linha = existente.iloc[0]
        precisa_atualizar = False
        campos = [
            'nome_grupo', 'transportadora', 'empresa', 'contato',
            'ja_carregamos', 'temos_cadastro', 'produto', 'preco',
            'latitude', 'longitude'
        ]
        for campo in campos:
            if row[campo.capitalize()] != linha[campo]:
                precisa_atualizar = True
                break

        if precisa_atualizar:
            cursor.execute("""
                UPDATE app_transportadoras
                SET nome_grupo = %s, transportadora = %s, empresa = %s,
                    contato = %s, ja_carregamos = %s, temos_cadastro = %s,
                    produto = %s, preco = %s, latitude = %s, longitude = %s
                WHERE cidade_origem = %s AND uf_origem = %s
            """, (
                row['Nome_grupo'], row['Transportadora'], row['Empresa'], row['Contato'],
                row['Ja_carregamos'], row['Temos_cadastro'], row['Produto'], row['Preco'],
                row['Latitude'], row['Longitude'], row['Cidade_origem'], row['UF_origem']
            ))
            atualizados += 1

# 6. Finaliza
conn.commit()
cursor.close()
conn.close()

print(f"✅ Atualização concluída. {novos} inseridos, {atualizados} atualizados.")
