import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Monitoreo Puno 2026")

@st.cache_data(ttl=60)
def cargar_datos():
    # 1. Intentar cargar desde los Secrets de Streamlit (Nube)
    if "gcp" in st.secrets:
        creds_dict = json.loads(st.secrets["gcp"]["json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, 
            ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
    else:
        # 2. Fallback: Cargar desde archivo local (Tu PC)
        archivo_json = os.path.join(os.path.dirname(__file__), 'credenciales.json')
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            archivo_json, 
            ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
    
    client = gspread.authorize(creds)
    sheet = client.open("datos").sheet1
    data = sheet.get_all_values()
    
    # Crear DataFrame
    df = pd.DataFrame(data[1:], columns=[c.strip().upper() for c in data[0]])
    
    # Procesamiento robusto de coordenadas (Universal: maneja coma y punto)
    for col in ['LATITUD', 'LONGITUD']:
        if col in df.columns:
            df[col + '_MAPA'] = pd.to_numeric(
                df[col].astype(str).str.strip().str.replace(',', '.'), 
                errors='coerce'
            )
    return df

# --- UI PRINCIPAL ---
df_procesado = cargar_datos().dropna(subset=['LATITUD_MAPA', 'LONGITUD_MAPA'])
vandalizados_df = df_procesado[df_procesado['¿SITIO VANDALIZADO ?'].str.strip().str.upper() == 'SI']
no_autorizados_df = df_procesado[df_procesado['EQUIPOS NO AUTORIZADOS'].str.strip().str.upper() == 'SI']

st.title("Monitoreo de Nodos - Puno 2026")

# --- SIDEBAR ---
st.sidebar.header("Filtros y Detalle")
lista_nodos = ["TODOS"] + df_procesado['CODIGO IDENTIFICADOR'].astype(str).tolist()
seleccion = st.sidebar.selectbox("**Seleccionar el Código Identificador**", lista_nodos)

with st.sidebar.expander("Ver lista de sitios afectados", expanded=True):
    if not vandalizados_df.empty:
        st.markdown("<h6 style='color:red;'>⚠️ Vandalizados:</h6>", unsafe_allow_html=True)
        for sitio in vandalizados_df['CODIGO IDENTIFICADOR']:
            st.markdown(f"<div style='background:#fff0f0; border-left:4px solid red; padding:5px; margin-bottom:3px; font-size:11px;'>{sitio}</div>", unsafe_allow_html=True)
    
    if not no_autorizados_df.empty:
        st.markdown("<h6 style='color:purple; margin-top:10px;'>🚫 No Autorizados:</h6>", unsafe_allow_html=True)
        for sitio in no_autorizados_df['CODIGO IDENTIFICADOR']:
            st.markdown(f"<div style='background:#f9f0ff; border-left:4px solid purple; padding:5px; margin-bottom:3px; font-size:11px;'>{sitio}</div>", unsafe_allow_html=True)

# --- MAPA ---
df_mostrar = df_procesado if seleccion == "TODOS" else df_procesado[df_procesado['CODIGO IDENTIFICADOR'].astype(str) == seleccion]
lat_m = df_mostrar['LATITUD_MAPA'].mean()
lon_m = df_mostrar['LONGITUD_MAPA'].mean()
mapa = folium.Map(location=[lat_m, lon_m], zoom_start=8 if seleccion == "TODOS" else 15)
marker_cluster = MarkerCluster().add_to(mapa)

for _, fila in df_mostrar.iterrows():
    folium.Marker([fila['LATITUD_MAPA'], fila['LONGITUD_MAPA']], popup=fila['CODIGO IDENTIFICADOR']).add_to(marker_cluster)

st_folium(mapa, width=1000, height=500)
