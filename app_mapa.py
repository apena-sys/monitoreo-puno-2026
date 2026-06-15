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
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = df.columns.str.strip().str.upper()
    for col in ['LATITUD', 'LONGITUD']:
        if col in df.columns: df[col + '_MAPA'] = pd.to_numeric(df[col].astype(str).str.strip().str.replace(',', '.'), errors='coerce')
    return df

# --- UI PRINCIPAL ---
df_procesado = cargar_datos().dropna(subset=['LATITUD_MAPA', 'LONGITUD_MAPA'])
vandalizados_df = df_procesado[df_procesado['¿SITIO VANDALIZADO ?'].str.strip().str.upper() == 'SI']
no_autorizados_df = df_procesado[df_procesado['EQUIPOS NO AUTORIZADOS'].str.strip().str.upper() == 'SI']
nodos_no_aut = len(no_autorizados_df)

st.title("Monitoreo de Nodos - Puno 2026")
st.markdown("**Componentes de la Red de Acceso Puno**")

# --- CONTADORES ---
conteo_sites = df_procesado['NOMBRE DE SITE'].value_counts()
cols = st.columns(len(conteo_sites))
for i, (n, c) in enumerate(conteo_sites.items()):
    with cols[i]:
        st.markdown(f'''
            <div style="background:#eef6ff; border: 1px solid #b3d7ff; padding:20px; border-radius:10px; text-align:center; min-height:120px; display:flex; flex-direction:column; justify-content:center;">
                <div style="font-weight:bold; color:#555; font-size:11px; text-transform:uppercase;">{n}</div>
                <div style="font-weight:bold; color:#0056b3; font-size:28px; margin-top:5px;">{c}</div>
            </div>
        ''', unsafe_allow_html=True)

st.divider()

# --- SIDEBAR ---
st.sidebar.header("Filtros y Detalle")
lista_nodos = ["TODOS"] + df_procesado['CODIGO IDENTIFICADOR'].astype(str).tolist()
seleccion = st.sidebar.selectbox("**Seleccionar el Código Identificador del Sitio**", lista_nodos)

df_procesado['FECHA_TEMP'] = df_procesado['FECHA DE INSPECCIÓN 2026'].str.strip()
st.sidebar.markdown(f"""<div style="font-size:14px; margin-top:10px;">
<b>Vandalizados:</b> <span style='color:red;'>{len(vandalizados_df)}</span><br>
<b>Inspeccionado 2026:</b> <span style='color:green;'>{df_procesado[df_procesado['FECHA_TEMP'] != ''].shape[0]}</span><br>
<b>No Inspeccionado:</b> <span style='color:orange;'>{df_procesado[df_procesado['FECHA_TEMP'] == ''].shape[0]}</span><br>
<b>Equipos No Autorizados:</b> <span style='color:purple;'>{nodos_no_aut}</span></div>""", unsafe_allow_html=True)

# Desglose detallado con estética mejorada
with st.sidebar.expander("Ver lista de sitios afectados"):
    if not vandalizados_df.empty:
        st.markdown("<h6 style='color:red; margin-bottom:5px;'>⚠️ Sitios Vandalizados:</h6>", unsafe_allow_html=True)
        for sitio in vandalizados_df['CODIGO IDENTIFICADOR']:
            st.markdown(f"<div style='background:#fff0f0; border-left:4px solid red; padding:5px; margin-bottom:3px; font-size:12px;'>{sitio}</div>", unsafe_allow_html=True)
    
    if not no_autorizados_df.empty:
        st.markdown("<h6 style='color:purple; margin-bottom:10px; margin-top:10px;'>🚫 Equipos No Autorizados:</h6>", unsafe_allow_html=True)
        for sitio in no_autorizados_df['CODIGO IDENTIFICADOR']:
            st.markdown(f"<div style='background:#f9f0ff; border-left:4px solid purple; padding:5px; margin-bottom:3px; font-size:12px;'>{sitio}</div>", unsafe_allow_html=True)

# --- MAPA ---
df_mostrar = df_procesado if seleccion == "TODOS" else df_procesado[df_procesado['CODIGO IDENTIFICADOR'].astype(str) == seleccion]
lat_m = df_mostrar['LATITUD_MAPA'].mean() if seleccion == "TODOS" else df_mostrar['LATITUD_MAPA'].iloc[0]
lon_m = df_mostrar['LONGITUD_MAPA'].mean() if seleccion == "TODOS" else df_mostrar['LONGITUD_MAPA'].iloc[0]
z = 8 if seleccion == "TODOS" else 15

mapa = folium.Map(location=[lat_m, lon_m], zoom_start=z, tiles="OpenStreetMap")
marker_cluster = MarkerCluster().add_to(mapa)

for _, fila in df_mostrar.iterrows():
    html_popup = f"""<div style="width:300px; font-family: sans-serif; font-size:12px;">
    <h4 style="margin:0; color:#0056b3;">{fila['CODIGO IDENTIFICADOR']}</h4><hr style="margin:5px 0;">
    <table style="width:100%;">""" + "".join([f"<tr><td style='padding:2px; font-weight:bold; width:45%;'>{col.title()}:</td><td style='padding:2px;'>{fila[col]}</td></tr>" for col in df_procesado.columns if col not in ['LATITUD_MAPA', 'LONGITUD_MAPA', 'FECHA_TEMP', 'ITEM']]) + "</table></div>"
    folium.Marker([fila['LATITUD_MAPA'], fila['LONGITUD_MAPA']], popup=folium.Popup(html_popup, max_width=350)).add_to(marker_cluster)

st_folium(mapa, width=1200, height=600)

# --- VISUALIZACIÓN FOTOS ---
if seleccion != "TODOS":
    st.subheader(f"Registro Fotográfico: {seleccion}")
    fotos = buscar_fotos_drive(seleccion)
    if fotos:
        cols = st.columns(4)
        for i, f in enumerate(fotos):
            with cols[i % 4]:
                st.image(f"https://lh3.googleusercontent.com/d/{f['id']}", caption=f.get('name'), width="stretch")
    else:
        st.warning("No se encontraron fotos en la carpeta '1.FOTOS'.")
