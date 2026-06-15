import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os
from googleapiclient.discovery import build

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Monitoreo Puno 2026")

def get_drive_service():
    if "gcp" in st.secrets:
        creds_dict = json.loads(st.secrets["gcp"]["json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, ['https://www.googleapis.com/auth/drive']
        )
    else:
        archivo_json = os.path.join(os.path.dirname(__file__), 'credenciales.json')
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            archivo_json, ['https://www.googleapis.com/auth/drive']
        )
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
        res_imgs = service.files().list(q=q_imgs, fields='files(id, name, webContentLink)').execute()
        return res_imgs.get('files', [])
    except: return []

@st.cache_data(ttl=60)
def cargar_datos():
    if "gcp" in st.secrets:
        creds_dict = json.loads(st.secrets["gcp"]["json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
    else:
        archivo_json = os.path.join(os.path.dirname(__file__), 'credenciales.json')
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            archivo_json, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
    client = gspread.authorize(creds)
    sheet = client.open("datos").sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=[c.strip().upper() for c in data[0]])
    for col in ['LATITUD', 'LONGITUD']:
        if col in df.columns:
            df[col + '_MAPA'] = pd.to_numeric(df[col].astype(str).str.strip().str.replace(',', '.'), errors='coerce')
    return df

# --- UI PRINCIPAL ---
df_procesado = cargar_datos().dropna(subset=['LATITUD_MAPA', 'LONGITUD_MAPA'])
st.title("Monitoreo de Nodos - Puno 2026")

# SIDEBAR: Filtros y Alertas
st.sidebar.header("Filtros")
lista_nodos = ["TODOS"] + df_procesado['CODIGO IDENTIFICADOR'].astype(str).tolist()
seleccion = st.sidebar.selectbox("Seleccionar Código Identificador", lista_nodos)

# Lógica de Alertas
vandalizados = df_procesado[df_procesado['¿SITIO VANDALIZADO ?'].str.strip().str.upper() == 'SI']
no_autorizados = df_procesado[df_procesado['EQUIPOS NO AUTORIZADOS'].str.strip().str.upper() == 'SI']

with st.sidebar.expander("Alertas en Tiempo Real", expanded=True):
    st.markdown("<h6 style='color:red;'>⚠️ Vandalizados:</h6>", unsafe_allow_html=True)
    for nodo in vandalizados['CODIGO IDENTIFICADOR']: st.write(nodo)
    st.markdown("<h6 style='color:purple;'>🚫 No Autorizados:</h6>", unsafe_allow_html=True)
    for nodo in no_autorizados['CODIGO IDENTIFICADOR']: st.write(nodo)

# --- MAPA ---
df_mostrar = df_procesado if seleccion == "TODOS" else df_procesado[df_procesado['CODIGO IDENTIFICADOR'].astype(str) == seleccion]
mapa = folium.Map(location=[df_mostrar['LATITUD_MAPA'].mean(), df_mostrar['LONGITUD_MAPA'].mean()], zoom_start=12 if seleccion == "TODOS" else 15)
marker_cluster = MarkerCluster().add_to(mapa)
for _, fila in df_mostrar.iterrows():
    folium.Marker([fila['LATITUD_MAPA'], fila['LONGITUD_MAPA']], popup=fila['CODIGO IDENTIFICADOR']).add_to(marker_cluster)
st_folium(mapa, width=1000, height=450)

# --- FOTOS ---
if seleccion != "TODOS":
    st.subheader(f"Evidencia Fotográfica: {seleccion}")
    fotos = buscar_fotos_drive(seleccion)
    if fotos:
        cols = st.columns(3)
        for i, f in enumerate(fotos):
            cols[i % 3].image(f['webContentLink'], caption=f['name'], use_column_width=True)
    else:
        st.info("Sin fotos disponibles en carpeta '1.FOTOS'.")
