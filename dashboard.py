import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import io

st.set_page_config(
    page_title="Monitor Bandi | Lumen Advisors",
    page_icon="logo_lumen.png",
    layout="wide"
)

# Logo e titolo
col_logo, col_titolo = st.columns([1, 8])
with col_logo:
    st.image("logo_lumen.png", width=80)
with col_titolo:
    st.title("Monitor Bandi PMI Campania")
    st.caption(f"Aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Lumen Advisors")

# Carica i dati
try:
    url_excel = "https://github.com/marcotulliovaliante/monitor-bandi-pmi/raw/master/bandi_campania.xlsx"
    response = requests.get(url_excel)
    df = pd.read_excel(io.BytesIO(response.content), sheet_name="Bandi")
    
    # Sidebar filtri
    st.sidebar.header("Filtri")
    
    fonti = ["Tutte"] + sorted(df["Fonte"].unique().tolist())
    fonte_sel = st.sidebar.selectbox("Fonte", fonti)
    
    stati = ["Tutti"] + sorted(df["Stato"].unique().tolist())
    stato_sel = st.sidebar.selectbox("Stato", stati)
    
    if "Pertinenza PMI" in df.columns:
        pertinenze = ["Tutte"] + sorted(df["Pertinenza PMI"].dropna().unique().tolist())
        pertinenza_sel = st.sidebar.selectbox("Pertinenza PMI", pertinenze)
    else:
        pertinenza_sel = "Tutte"
    
    cerca = st.sidebar.text_input("🔍 Cerca nel titolo")
    
    # Applica filtri
    df_filtrato = df.copy()
    if fonte_sel != "Tutte":
        df_filtrato = df_filtrato[df_filtrato["Fonte"] == fonte_sel]
    if stato_sel != "Tutti":
        df_filtrato = df_filtrato[df_filtrato["Stato"] == stato_sel]
    if pertinenza_sel != "Tutte" and "Pertinenza PMI" in df.columns:
        df_filtrato = df_filtrato[df_filtrato["Pertinenza PMI"] == pertinenza_sel]
    if cerca:
        df_filtrato = df_filtrato[df_filtrato["Titolo"].str.contains(cerca, case=False, na=False)]
    
    # Metriche
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totale bandi", len(df))
    col2.metric("Bandi aperti", len(df[df["Stato"] == "✅ Aperto"]))
    col3.metric("Risultati filtrati", len(df_filtrato))
    col4.metric("Fonti monitorate", df["Fonte"].nunique())
    
    st.divider()
    
    # Tabella
    st.subheader(f"Bandi trovati: {len(df_filtrato)}")
    
    colonne = ["Titolo", "Scadenza", "Stato", "Fonte"]
    if "Pertinenza PMI" in df.columns:
        colonne.append("Pertinenza PMI")
    if "Categoria" in df.columns:
        colonne.append("Categoria")
    if "Link" in df.columns:
        colonne.append("Link")
    
    st.dataframe(
        df_filtrato[colonne],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Link": st.column_config.LinkColumn("Link"),
            "Titolo": st.column_config.TextColumn("Titolo", width="large"),
        }
    )
    
    # Export Excel
    st.divider()
    excel_data = df_filtrato.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Scarica CSV",
        data=excel_data,
        file_name=f"bandi_filtrati_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

except FileNotFoundError:
    st.error("File bandi_campania.xlsx non trovato. Esegui prima scraper_bandi.py!")