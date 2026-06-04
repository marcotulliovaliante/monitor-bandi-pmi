import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import io

# Autenticazione
PASSWORD_USER = "lumen2026"
PASSWORD_ADMIN = "lumenadmin2026"

def check_password():
    if "ruolo" not in st.session_state:
        st.session_state.ruolo = None
    if st.session_state.ruolo is None:
        st.image("logo_lumen.png", width=120)
        st.title("Monitor Bandi PMI Campania")
        st.subheader("Accesso riservato | Lumen Advisors")
        pwd = st.text_input("Password", type="password")
        if st.button("Accedi"):
            if pwd == PASSWORD_ADMIN:
                st.session_state.ruolo = "admin"
                st.rerun()
            elif pwd == PASSWORD_USER:
                st.session_state.ruolo = "user"
                st.rerun()
            else:
                st.error("Password errata")
        st.stop()

check_password()

st.set_page_config(
    page_title="Monitor Bandi | Lumen Advisors",
    page_icon="logo_lumen.png",
    layout="wide"
)

col_logo, col_titolo = st.columns([1, 8])
with col_logo:
    st.image("logo_lumen.png", width=80)
with col_titolo:
    st.title("Monitor Bandi PMI Campania")
    st.caption(f"Aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Lumen Advisors")

try:
    url_excel = "https://github.com/marcotulliovaliante/monitor-bandi-pmi/raw/master/bandi_campania.xlsx"
    response = requests.get(url_excel)
    df = pd.read_excel(io.BytesIO(response.content), sheet_name="Bandi")

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

    df_filtrato = df.copy()
    if fonte_sel != "Tutte":
        df_filtrato = df_filtrato[df_filtrato["Fonte"] == fonte_sel]
    if stato_sel != "Tutti":
        df_filtrato = df_filtrato[df_filtrato["Stato"] == stato_sel]
    if pertinenza_sel != "Tutte" and "Pertinenza PMI" in df.columns:
        df_filtrato = df_filtrato[df_filtrato["Pertinenza PMI"] == pertinenza_sel]
    if cerca:
        df_filtrato = df_filtrato[df_filtrato["Titolo"].str.contains(cerca, case=False, na=False)]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totale bandi", len(df))
    col2.metric("Bandi aperti", len(df[df["Stato"] == "✅ Aperto"]))
    col3.metric("Risultati filtrati", len(df_filtrato))
    col4.metric("Fonti monitorate", df["Fonte"].nunique())

    st.divider()

    if st.session_state.ruolo == "admin":
        with st.expander("⚙️ Pannello di controllo"):
            st.subheader("Lancia lo scraper manualmente")
            st.caption("Avvia il workflow GitHub Actions per aggiornare i bandi")
            if st.button("🚀 Aggiorna bandi ora"):
                token = st.secrets.get("PAT_TOKEN", "")
                if token:
                    r = requests.post(
                        "https://api.github.com/repos/marcotulliovaliante/monitor-bandi-pmi/actions/workflows/monitor_bandi.yml/dispatches",
                        headers={
                            "Authorization": f"token {token}",
                            "Accept": "application/vnd.github.v3+json"
                        },
                        json={"ref": "master"}
                    )
                    if r.status_code == 204:
                        st.success("✅ Workflow avviato! Attendi 15 minuti per i risultati.")
                    else:
                        st.error(f"Errore: {r.status_code} — {r.text}")
                else:
                    st.error("PAT_TOKEN non configurato")

            st.divider()
            st.subheader("📧 Gestione destinatari email")
            try:
                r_config = requests.get(
                    "https://raw.githubusercontent.com/marcotulliovaliante/monitor-bandi-pmi/master/config.json"
                )
                config = r_config.json()
                destinatari = config.get("destinatari", [])
            except:
                destinatari = []

            st.write("**Destinatari attuali:**")
            for email in destinatari:
                st.write(f"• {email}")

            nuova_email = st.text_input("Aggiungi email")
            if st.button("➕ Aggiungi destinatario"):
                if nuova_email and nuova_email not in destinatari:
                    destinatari.append(nuova_email)
                    token = st.secrets.get("PAT_TOKEN", "")
                    if token:
                        import base64
                        import json as json_lib
                        nuovo_config = json_lib.dumps({"destinatari": destinatari}, indent=4)
                        r_get = requests.get(
                            "https://api.github.com/repos/marcotulliovaliante/monitor-bandi-pmi/contents/config.json",
                            headers={"Authorization": f"token {token}"}
                        )
                        sha = r_get.json().get("sha", "")
                        requests.put(
                            "https://api.github.com/repos/marcotulliovaliante/monitor-bandi-pmi/contents/config.json",
                            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                            json={
                                "message": f"Aggiunto destinatario {nuova_email}",
                                "content": base64.b64encode(nuovo_config.encode()).decode(),
                                "sha": sha
                            }
                        )
                        st.success(f"✅ {nuova_email} aggiunto!")
                        st.rerun()

        st.divider()

    # Tabella principale
    st.subheader(f"Bandi trovati: {len(df_filtrato)}")

    colonne_principali = ["Titolo", "Scadenza", "Fonte"]
    if "Pertinenza PMI" in df.columns:
        colonne_principali.append("Pertinenza PMI")
    if "Link" in df.columns:
        colonne_principali.append("Link")

    st.dataframe(
        df_filtrato[colonne_principali],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Titolo": st.column_config.TextColumn("Titolo", width="large"),
            "Scadenza": st.column_config.TextColumn("Scadenza", width="medium"),
            "Fonte": st.column_config.TextColumn("Fonte", width="medium"),
            "Pertinenza PMI": st.column_config.TextColumn("Pertinenza", width="small"),
            "Link": st.column_config.LinkColumn("🔗", width="small", display_text="Apri"),
        }
    )

    # Dettaglio bando
    st.divider()
    st.subheader("🔍 Dettaglio bando")
    titoli = ["— Seleziona un bando —"] + df_filtrato["Titolo"].tolist()
    bando_sel = st.selectbox("Seleziona bando", titoli)

    if bando_sel != "— Seleziona un bando —":
        bando = df_filtrato[df_filtrato["Titolo"] == bando_sel].iloc[0]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Titolo:** {bando['Titolo']}")
            st.markdown(f"**Fonte:** {bando['Fonte']}")
            st.markdown(f"**Scadenza:** {bando['Scadenza']}")
            if "Data pubblicazione" in bando:
                st.markdown(f"**Data pubblicazione:** {bando['Data pubblicazione']}")
        with col2:
            if "Pertinenza PMI" in bando:
                st.markdown(f"**Pertinenza PMI:** {bando['Pertinenza PMI']}")
            if "Categoria" in bando:
                st.markdown(f"**Categoria:** {bando['Categoria']}")
            if "Motivazione AI" in bando:
                st.markdown(f"**Analisi AI:** {bando['Motivazione AI']}")
            if "Link" in bando and bando["Link"]:
                st.link_button("🔗 Vai al bando", bando["Link"])

    st.divider()
    csv_data = df_filtrato.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Scarica CSV",
        data=csv_data,
        file_name=f"bandi_filtrati_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

except Exception as e:
    st.error(f"Errore nel caricamento dei dati: {e}")