import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Monitoreo Puno 2026")

def get_creds():
    """Función maestra para obtener credenciales (nube o local)"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if "gcp" in st.secrets:
        # Modo Nube (Secrets)
        creds_dict = json.loads(st.secrets["gcp"]["json"])
        return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Modo Local (Archivo)
        archivo_json = os.path.join(os.path.dirname(__file__), 'credenciales.json')
        return ServiceAccountCredentials.from_json_keyfile_name(archivo_json, scope)

def get_drive_service():
    return build('drive', 'v3', credentials=get_creds())

@st.cache_data(ttl=60)
def buscar_fotos_drive(codigo_sitio):
    try:
        service = get_drive_service()
        # Buscar carpeta del nodo
        q_nodo = f"name = '{codigo_sitio}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_nodo = service.files().list(q=q_nodo, fields='files(id)').execute()
        files = res_nodo.get('files', [])
        if not files: return []
        id_nodo = files[0]['id']
        
        # Buscar carpeta 1.FOTOS
        q_fotos = f"'{id_nodo}' in parents and name = '1.FOTOS' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_fotos = service.files().list(q=q_fotos, fields='files(id)').execute()
        files_fotos = res_fotos.get('files', [])
        if not files_fotos: return []
        id_fotos = files_fotos[0]['id']
        
        # Listar imágenes (usamos webContentLink para visualización)
        q_imgs = f"'{id_fotos}' in parents and mimeType contains 'image/' and trashed = false"
        res_imgs = service.files().list(q=q_imgs, fields='files(id, name, webContentLink)').execute()
        return res_imgs.get('files', [])
    except: return []

@st.cache_data(ttl=60)
def cargar_datos():
    client = gspread.authorize(get_creds())
    sheet = client.open("datos").sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = df.columns.str.strip().str.upper()
    
    # --- AJUSTE CRÍTICO DE COORDENADAS ---
    for col in ['LATITUD', 'LONGITUD']:
        if col in df.columns:
            # Forzamos conversión: quitamos espacios, coma a punto, y a número
            df[col + '_MAPA'] = pd.to_numeric(
                df[col].astype(str).str.strip().str.replace(',', '.'), 
                errors='coerce'
            )
    return df

# --- UI PRINCIPAL ---
df_procesado = cargar_datos().dropna(subset=['LATITUD_MAPA', 'LONGITUD_MAPA'])
vandalizados_df = df_procesado[df_procesado['¿SITIO VANDALIZADO ?'].str.strip().str.upper() == 'SI']
no_autorizados_df = df_procesado[df_procesado['EQUIPOS NO AUTORIZADOS'].str.strip().str.upper() == 'SI']
nodos_no_aut = len(no_autorizados_df)

st.title("Monitoreo de Nodos - Puno 2026")

# --- CONTADORES ---
conteo_sites = df_procesado['NOMBRE DE SITE'].value_counts()
cols = st.columns(len(conteo_sites))
for i, (n, c) in enumerate(conteo_sites.items()):
    with cols[i]:
        st.markdown(f'''<div style="background:#eef6ff; padding:15px; border-radius:10px; text-align:center;">
            <div style="font-weight:bold; font-size:11px;">{n}</div>
            <div style="font-size:24px; color:#0056b3;">{c}</div></div>''', unsafe_allow_html=True)

st.divider()

# --- SIDEBAR ---
st.sidebar.header("Filtros y Detalle")
lista_nodos = ["TODOS"] + df_procesado['CODIGO IDENTIFICADOR'].astype(str).tolist()
seleccion = st.sidebar.selectbox("**Seleccionar Sitio**", lista_nodos)

# --- MAPA ---
df_mostrar = df_procesado if seleccion == "TODOS" else df_procesado[df_procesado['CODIGO IDENTIFICADOR'].astype(str) == seleccion]
mapa = folium.Map(location=[df_mostrar['LATITUD_MAPA'].mean(), df_mostrar['LONGITUD_MAPA'].mean()], zoom_start=8 if seleccion == "TODOS" else 15)
marker_cluster = MarkerCluster().add_to(mapa)

for _, fila in df_mostrar.iterrows():
    folium.Marker([fila['LATITUD_MAPA'], fila['LONGITUD_MAPA']], popup=fila['CODIGO IDENTIFICADOR']).add_to(marker_cluster)
st_folium(mapa, width=1200, height=500)

# --- FOTOS ---
if seleccion != "TODOS":
    st.subheader(f"Registro Fotográfico: {seleccion}")
    fotos = buscar_fotos_drive(seleccion)
    if fotos:
        cols = st.columns(4)
        for i, f in enumerate(fotos):
            # Usamos el enlace webContentLink para visualizar
            if 'webContentLink' in f:
                cols[i % 4].image(f['webContentLink'], caption=f['name'], use_container_width=True)
    else:
        st.warning("No se encontraron fotos en la carpeta '1.FOTOS'.")
