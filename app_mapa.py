import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import io

# Configuración inicial
st.set_page_config(layout="wide")
st.title("Monitoreo de Nodos - Puno 2026")

# URL directa al CSV publicado
URL = "https://docs.google.com/spreadsheets/d/12bZadLem9EeH5ts0y9Cvyidu1rZWjtBmWjhMEQCuMlA/pub?output=csv"

@st.cache_data(ttl=60)
def cargar_y_limpiar_datos():
    # 1. Descargar datos de forma robusta
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers=headers)
    
    # 2. Leer el CSV
    df = pd.read_csv(io.StringIO(response.text))
    
    # 3. Limpiar nombres de columnas (quitar espacios laterales)
    df.columns = df.columns.str.strip()
    
    # 4. Convertir LATITUD y LONGITUD a formato numérico (punto decimal)
    # Primero convertimos a string, reemplazamos coma por punto, y luego a float
    for col in ['LATITUD', 'LONGITUD']:
        df[col] = df[col].astype(str).str.replace(',', '.')
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    return df

try:
    df = cargar_y_limpiar_datos()
    
    # Filtrar solo filas donde las coordenadas sean válidas
    df_mapa = df.dropna(subset=['LATITUD', 'LONGITUD'])
    
    st.write(f"Total de nodos encontrados: {len(df_mapa)}")
    
    # Crear el mapa centrado en Puno
    mapa = folium.Map(location=[-15.84, -70.02], zoom_start=8)
    
    # Agregar marcadores
    for _, fila in df_mapa.iterrows():
        folium.Marker(
            location=[fila['LATITUD'], fila['LONGITUD']],
            popup=f"<b>ID:</b> {fila['CODIGO IDENTIFICADOR']}<br><b>Site:</b> {fila['NOMBRE DE SITE']}",
            tooltip=fila['CODIGO IDENTIFICADOR']
        ).add_to(mapa)
    
    # Mostrar el mapa en Streamlit
    st_folium(mapa, width=1200, height=600)

except Exception as e:
    st.error(f"Error al procesar los datos: {e}")