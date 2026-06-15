import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import pandas as pd
import folium
from streamlit_folium import st_folium
import os

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Monitoreo Puno 2026")

def get_creds():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if "gcp" in st.secrets:
        creds_dict = json.loads(st.secrets["gcp"]["json"])
        return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        archivo_json = os.path.join(os.path.dirname(__file__), 'credenciales.json')
        return ServiceAccountCredentials.from_json_keyfile_name(archivo_json, scope)

def get_drive_service():
    return build('drive', 'v3', credentials=get_creds())

@st.cache_data(ttl=300) # Aumentado a 5 min para mayor fluidez
def buscar_fotos_drive(codigo_sitio):
    try:
        service = get_drive_service()
        res_nodo = service.files().list(q=f"name = '{codigo_sitio}' and mimeType = 'application/vnd.google-apps.folder'", fields='files(id)').execute()
        files = res_nodo.get('files', [])
        if not files: return []
        id_fotos = service.files().list(q=f"'{files[0]['id']}' in parents and name = '1.FOTOS'", fields='files(id)').execute().get('files', [])
        if not id_fotos: return []
        imgs = service.files().list(q=f"'{id_fotos[0]['id']}' in parents and mimeType contains 'image/'", fields='files(id, name)').execute()
        return imgs.get('files', [])
    except: return []

@st.cache_data(ttl=300)
def cargar_datos():
    client = gspread.authorize(get_creds())
    df = pd.DataFrame(client.open("datos").sheet1.get_all_records())
    df.columns = df.columns.str.upper()
    df['LATITUD_MAPA'] = pd.to_numeric(df['LATITUD'].astype(str).str.replace(',', '.'), errors='coerce')
    df['LONGITUD_MAPA'] = pd.to_numeric(df['LONGITUD'].astype(str).str.replace(',', '.'), errors='coerce')
    return df

# --- UI PRINCIPAL ---
df = cargar_datos().dropna(subset=['LATITUD_MAPA', 'LONGITUD_MAPA'])
vandalizados = df[df['¿SITIO VANDALIZADO ?'].astype(str).str.upper() == 'SI']
no_aut = df[df['EQUIPOS NO AUTORIZADOS'].astype(str).str.upper() == 'SI']

st.title("Monitoreo de Nodos - Puno 2026")

# --- SIDEBAR ---
seleccion = st.sidebar.selectbox("Seleccionar Nodo", ["TODOS"] + df['CODIGO IDENTIFICADOR'].tolist())
st.sidebar.markdown(f"**Vandalizados:** {len(vandalizados)} | **No Aut.:** {len(no_aut)}")

# --- MAPA OPTIMIZADO ---
centro = [df['LATITUD_MAPA'].mean(), df['LONGITUD_MAPA'].mean()] if seleccion == "TODOS" else [df[df['CODIGO IDENTIFICADOR']==seleccion]['LATITUD_MAPA'].iloc[0], df[df['CODIGO IDENTIFICADOR']==seleccion]['LONGITUD_MAPA'].iloc[0]]
mapa = folium.Map(location=centro, zoom_start=8 if seleccion == "TODOS" else 16)

for _, row in df.iterrows():
    # Popup dinámico que muestra todas las columnas
    popup_html = "<div style='font-size:11px; max-height:200px; overflow-y:auto;'>"
    for col in df.columns:
        if col not in ['LATITUD_MAPA', 'LONGITUD_MAPA']:
            popup_html += f"<b>{col}:</b> {row[col]}<br>"
    popup_html += "</div>"
    
    color = 'red' if row['CODIGO IDENTIFICADOR'] == seleccion else 'blue'
    folium.Marker([row['LATITUD_MAPA'], row['LONGITUD_MAPA']], 
                  popup=folium.Popup(popup_html, max_width=300),
                  icon=folium.Icon(color=color)).add_to(mapa)

st_folium(mapa, width=1200, height=500)

# --- FOTOS ---
if seleccion != "TODOS":
    st.subheader(f"Evidencia: {seleccion}")
    fotos = buscar_fotos_drive(seleccion)
    cols = st.columns(4)
    for i, f in enumerate(fotos):
        cols[i % 4].image(f"https://lh3.googleusercontent.com/d/{f['id']}", use_container_width=True)
