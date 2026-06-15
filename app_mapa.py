import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Monitoreo Puno 2026")

def get_drive_service():
    # En la nube, usamos variables de entorno o el archivo en la raíz
    archivo_json = os.path.join(os.path.dirname(__file__), 'credenciales.json')
    scope = ['https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(archivo_json, scope)
    return build('drive', 'v3', credentials=creds)

@st.cache_data(ttl=60)
def buscar_fotos_drive(codigo_sitio):
    try:
        service = get_drive_service()
        q_nodo = f"name = '{codigo_sitio}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_nodo = service.files().list(q=q_nodo, fields='files(id)').execute()
        files = res_nodo.get('files', [])
        if not files: return []
        id_nodo = files[0]['id']
        q_fotos = f"'{id_nodo}' in parents and name = '1.FOTOS' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_fotos = service.files().list(q=q_fotos, fields='files(id)').execute()
        files_fotos = res_fotos.get('files', [])
        if not files_fotos: return []
        id_fotos = files_fotos[0]['id']
        q_imgs = f"'{id_fotos}' in parents and mimeType contains 'image/' and trashed = false"
        res_imgs = service.files().list(q=q_imgs, fields='files(id, name)').execute()
        return res_imgs.get('files', [])
    except: return []

@st.cache_data(ttl=60)
def cargar_datos():
    archivo_json = os.path.join(os.path.dirname(__file__), 'credenciales.json')
    creds = ServiceAccountCredentials.from_json_keyfile_name(archivo_json, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    client = gspread.authorize(creds)
    sheet = client.open("datos").sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=[c.strip().upper() for c in data[0]])
    
    # Procesamiento robusto para coordenadas universal (coma o punto)
    for col in ['LATITUD', 'LONGITUD']:
        if col in df.columns:
            df[col + '_MAPA'] = df[col].astype(str).str.strip().str.replace(',', '.')
            df[col + '_MAPA'] = pd.to_numeric(df[col + '_MAPA'], errors='coerce')
    return df

# --- UI PRINCIPAL ---
df_procesado = cargar_datos().dropna(subset=['LATITUD_MAPA', 'LONGITUD_MAPA'])
vandalizados_df = df_procesado[df_procesado['¿SITIO VANDALIZADO ?'].str.strip().str.upper() == 'SI']
no_autorizados_df = df_procesado[df_procesado['EQUIPOS NO AUTORIZADOS'].str.strip().str.upper() == 'SI']

st.title("Monitoreo de Nodos - Puno 2026")

# --- SIDEBAR Y LISTAS ---
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
