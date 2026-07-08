import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import io
import anthropic
import json
import re
from genera_factsheet_word import genera_factsheet_word

# ── Autenticazione ──────────────────────────────────────────────────────────
PASSWORD_USER  = "lumen2026"
PASSWORD_ADMIN = "lumenadmin2026"

def check_password():
    if "ruolo" not in st.session_state:
        st.session_state.ruolo = None
    if st.session_state.ruolo is None:
        st.image("logo_lumen.png", width=120)
        st.title("Lumen Scout")
        st.subheader("Monitor bandi e finanziamenti | Lumen Opportunities")
        st.caption("Accesso riservato — Lumen Advisors")
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
    page_title="Lumen Scout | Lumen Advisors",
    page_icon="logo_lumen.png",
    layout="wide"
)

# ── Header ───────────────────────────────────────────────────────────────────
col_logo, col_titolo = st.columns([1, 8])
with col_logo:
    st.image("logo_lumen.png", width=80)
with col_titolo:
    st.title("Lumen Scout")
    st.caption(f"Monitor bandi e finanziamenti — Lumen Opportunities | Lumen Advisors · Aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ── Estrazione dati bando con Claude ─────────────────────────────────────────
def estrai_dati_bando(titolo, fonte, scadenza, link, tipo_beneficiario, motivazione_ai):
    """Legge la pagina del bando ed estrae i dati strutturati con Claude Sonnet."""

    # 1. Scarica il testo della pagina del bando
    testo_bando = ""
    try:
        r = requests.get(link, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        testo_bando = soup.get_text(separator="\n", strip=True)[:8000]
    except Exception as e:
        testo_bando = f"[Impossibile leggere la pagina: {e}]"

    # 2. Claude estrae i dati strutturati
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key)

    prompt_estrazione = f"""Sei un analista di bandi pubblici italiani. Analizza il seguente testo di un bando e restituisci SOLO un oggetto JSON valido con i dati strutturati richiesti.

TITOLO BANDO: {titolo}
FONTE: {fonte}
SCADENZA: {scadenza}
TIPO BENEFICIARIO: {tipo_beneficiario}
ANALISI AI: {motivazione_ai}

TESTO PAGINA BANDO:
{testo_bando}

Restituisci SOLO questo JSON, niente altro:
{{
  "ente_promotore": "es. Ministero del Turismo · Invitalia",
  "sottotitolo": "frase descrittiva sintetica del bando (max 15 parole)",
  "descrizione_intro": "2-3 frasi che descrivono lo scopo del bando, il tipo di procedura e la dotazione totale",
  "dotazione_totale": "es. €109M",
  "agevolazione_principale": "es. 54% fondo perduto",
  "agevolazione_nota": "es. + 46% finanziamento agevolato",
  "investimento_range": "es. €1M – €15M",
  "investimento_nota": "es. per programma di investimento",
  "investimento_minimo": "es. € 1.000.000",
  "investimento_minimo_nota": "es. per programma",
  "investimento_massimo": "es. € 15.000.000",
  "investimento_massimo_nota": "es. per programma",
  "mix_fp_pct": 54,
  "mix_fp_label": "es. 54% Fondo Perduto",
  "mix_fin_pct": 46,
  "mix_fin_label": "es. 46% Fin. Agevolato",
  "mix_nota": "es. Contributo a fondo perduto + finanziamento agevolato a tasso ridotto",
  "chi_candidarsi": ["requisito 1", "requisito 2", "requisito 3", "requisito 4"],
  "tempistiche": [
    {{"label": "Apertura sportello", "value": "data"}},
    {{"label": "Chiusura sportello", "value": "data"}},
    {{"label": "Presentazione", "value": "modalità"}},
    {{"label": "Regime aiuti", "value": "es. GBER / de minimis"}}
  ],
  "note_aggiuntive": "eventuali note importanti sul bando (opzionale, lascia vuoto se non rilevante)"
}}

Se un dato non è disponibile nel testo, usa "N/D". Per mix_fp_pct e mix_fin_pct usa numeri interi (sommano a 100). Se non c'è un mix chiaro usa 100 e 0."""

    risposta = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt_estrazione}]
    )
    testo_json = risposta.content[0].text.strip()
    match = re.search(r'\{.*\}', testo_json, re.DOTALL)
    if not match:
        raise ValueError("Claude non ha restituito un JSON valido")
    return json.loads(match.group())


def genera_factsheet_html(dati: dict, titolo: str, fonte: str) -> str:
    """Genera il factsheet in formato HTML dalla palette Lumen."""
    mix_fp  = dati.get("mix_fp_pct", 100)
    mix_fin = dati.get("mix_fin_pct", 0)
    chi_list = "".join(f"<li>{r}</li>" for r in dati.get("chi_candidarsi", []))
    temp_rows = "".join(
        f'<div class="timing-row"><div class="timing-label">{t["label"]}</div><div class="timing-value">{t["value"]}</div></div>'
        for t in dati.get("tempistiche", [])
    )
    mix_bar_html = ""
    if mix_fp > 0 and mix_fin > 0:
        mix_bar_html = f"""<div class="mix-bar">
          <div class="mix-intro">Composizione dell'agevolazione</div>
          <div class="mix-track">
            <div class="mix-fp" style="width:{mix_fp}%"><span class="mix-label-bar">{dati.get("mix_fp_label","")}</span></div>
            <div class="mix-fin" style="width:{mix_fin}%"><span class="mix-label-bar dark">{dati.get("mix_fin_label","")}</span></div>
          </div>
          <div class="mix-legend">
            <div class="mix-legend-item"><div class="mix-dot" style="background:#0F6E56"></div>{dati.get("mix_nota","")}</div>
          </div>
        </div>"""
    note_html = ""
    if dati.get("note_aggiuntive") and dati["note_aggiuntive"].strip() and dati["note_aggiuntive"] != "N/D":
        note_html = f'<div class="intro-box" style="border-left-color:#0F6E56;margin-top:0;margin-bottom:18px"><strong>Note:</strong> {dati["note_aggiuntive"]}</div>'

    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8">
<title>{titolo} — Factsheet | Lumen Advisors</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  :root{{--vn:#0a2e22;--vs:#0F6E56;--oro:#C9A84C;--oc:#e8d5a3;--bg:#f7f7f5;--gt:#555;--txt:#1a1a1a;--wh:#fff}}
  body{{font-family:'Montserrat',sans-serif;background:var(--wh);color:var(--txt);width:210mm;margin:0 auto;font-size:13px}}
  .header{{background:var(--vn);padding:18px 28px 16px;display:flex;justify-content:space-between;align-items:center}}
  .logo-top{{font-size:16px;font-weight:800;letter-spacing:3px;color:var(--wh);line-height:1}}
  .logo-sub{{font-size:8px;letter-spacing:2px;color:var(--oc);text-transform:uppercase;margin-top:3px}}
  .header-badge{{border:1.5px solid var(--oro);color:var(--oro);font-size:9px;font-weight:700;letter-spacing:2px;padding:6px 14px;text-transform:uppercase}}
  .hero{{background:var(--vn);padding:4px 28px 22px;border-bottom:3px solid var(--oro)}}
  .hero-eyebrow{{font-size:9px;font-weight:600;letter-spacing:2px;color:var(--oro);text-transform:uppercase;margin-bottom:6px}}
  .hero-title{{font-size:36px;font-weight:800;color:var(--wh);letter-spacing:-0.5px;line-height:1.05;text-transform:uppercase}}
  .hero-sub{{font-family:'Cormorant Garamond',serif;font-size:14px;font-style:italic;color:var(--oc);margin-top:6px}}
  .intro-box{{background:var(--bg);border-left:4px solid var(--oro);padding:14px 18px;margin:18px 28px;font-size:12px;line-height:1.7}}
  .intro-box strong{{color:var(--vn);font-weight:700}}
  .section-label{{font-size:9px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--vs);border-bottom:1px solid var(--oro);padding-bottom:5px;margin:0 28px 12px}}
  .numeri-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:0 28px 18px}}
  .numero-card{{background:var(--vn);padding:14px 10px 12px;text-align:center}}
  .numero-card .valore{{font-family:'Cormorant Garamond',serif;font-size:30px;font-weight:600;color:var(--oro);line-height:1;margin-bottom:6px}}
  .numero-card .label{{font-size:8px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--wh);opacity:.85;line-height:1.4}}
  .numero-card .sub-label{{font-size:8.5px;color:var(--oc);margin-top:3px;opacity:.75}}
  .invest-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:0 28px 14px}}
  .invest-card{{border:1px solid #ddd;padding:12px 14px}}
  .ic-label{{font-size:8.5px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--vs);margin-bottom:5px}}
  .ic-value{{font-family:'Cormorant Garamond',serif;font-size:20px;font-weight:600;color:var(--vn)}}
  .ic-note{{font-size:10px;color:var(--gt);margin-top:3px}}
  .mix-bar{{margin:0 28px 18px}}
  .mix-intro{{font-size:10px;color:var(--gt);margin-bottom:5px}}
  .mix-track{{display:flex;height:22px;border-radius:2px;overflow:hidden;margin-bottom:6px}}
  .mix-fp{{background:var(--vs);display:flex;align-items:center;justify-content:center}}
  .mix-fin{{background:var(--oro);display:flex;align-items:center;justify-content:center}}
  .mix-label-bar{{font-size:8.5px;font-weight:700;color:var(--wh)}}
  .mix-label-bar.dark{{color:var(--vn)}}
  .mix-legend{{display:flex;gap:12px}}
  .mix-legend-item{{display:flex;align-items:center;gap:6px;font-size:9.5px;color:var(--gt)}}
  .mix-dot{{width:9px;height:9px;border-radius:1px;flex-shrink:0}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 28px 18px}}
  .col-box{{border:1px solid #e0e0e0;padding:14px}}
  .col-box-title{{font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--vn);border-bottom:1.5px solid var(--oro);padding-bottom:6px;margin-bottom:10px}}
  .col-box ul{{list-style:none}}
  .col-box ul li{{font-size:10.5px;line-height:1.6;padding:3px 0 3px 14px;position:relative}}
  .col-box ul li::before{{content:"•";position:absolute;left:0;color:var(--oro);font-size:13px;line-height:1.3}}
  .timing-row{{display:flex;gap:8px;padding:5px 0;border-bottom:1px solid #f0f0f0;align-items:baseline}}
  .timing-row:last-child{{border-bottom:none}}
  .timing-label{{font-size:9.5px;font-weight:700;color:var(--vn);min-width:95px;flex-shrink:0}}
  .timing-value{{font-size:10px;color:var(--gt);line-height:1.4}}
  .cta-footer{{background:var(--vn);margin:0 28px;padding:14px 18px;display:flex;justify-content:space-between;align-items:center}}
  .cta-title{{font-size:12px;font-weight:700;color:var(--wh);margin-bottom:4px}}
  .cta-desc{{font-size:9.5px;color:var(--oc);line-height:1.5}}
  .cta-right{{text-align:right;flex-shrink:0;margin-left:20px}}
  .cta-right p{{font-size:10px;color:var(--oro);line-height:1.9}}
  .page-footer{{display:flex;justify-content:space-between;align-items:center;padding:10px 28px;border-top:1px solid #e0e0e0;margin-top:12px}}
  .pf-name{{font-size:9px;font-weight:700;letter-spacing:2px;color:var(--vn);text-transform:uppercase}}
  .pf-sub{{font-size:7.5px;color:var(--gt);letter-spacing:1.5px;text-transform:uppercase}}
  .pf-right{{font-size:9.5px;color:var(--vs)}}
  @media print{{body{{width:210mm}}.header,.hero,.cta-footer,.numero-card,.mix-fp,.mix-fin{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<div class="header">
  <div style="display:flex;align-items:center;gap:10px">
    <svg width="34" height="34" viewBox="0 0 40 40" fill="none"><polygon points="20,2 38,20 20,38 2,20" fill="none" stroke="#C9A84C" stroke-width="2"/><polygon points="20,8 32,20 20,32 8,20" fill="none" stroke="#C9A84C" stroke-width="1"/><polygon points="20,14 26,20 20,26 14,20" fill="#C9A84C"/></svg>
    <div><div class="logo-top">LUMEN</div><div class="logo-sub">Advisors · Advisory · Planning · Wealth</div></div>
  </div>
  <div class="header-badge">Opportunità di Finanziamento</div>
</div>
<div class="hero">
  <div class="hero-eyebrow">{dati.get("ente_promotore", fonte)}</div>
  <div class="hero-title">{titolo}</div>
  <div class="hero-sub">{dati.get("sottotitolo","")}</div>
</div>
<div class="intro-box">{dati.get("descrizione_intro","")}</div>
<div class="section-label">Numeri Chiave</div>
<div class="numeri-grid">
  <div class="numero-card"><div class="valore">{dati.get("dotazione_totale","N/D")}</div><div class="label">Dotazione Totale Disponibile</div></div>
  <div class="numero-card"><div class="valore">{dati.get("agevolazione_principale","N/D")}</div><div class="label">Agevolazione Principale</div><div class="sub-label">{dati.get("agevolazione_nota","")}</div></div>
  <div class="numero-card"><div class="valore">{dati.get("investimento_range","N/D")}</div><div class="label">Investimento Ammissibile</div><div class="sub-label">{dati.get("investimento_nota","")}</div></div>
</div>
<div class="section-label">Struttura dell'Agevolazione</div>
<div class="invest-grid">
  <div class="invest-card"><div class="ic-label">Investimento Minimo</div><div class="ic-value">{dati.get("investimento_minimo","N/D")}</div><div class="ic-note">{dati.get("investimento_minimo_nota","")}</div></div>
  <div class="invest-card"><div class="ic-label">Investimento Massimo</div><div class="ic-value">{dati.get("investimento_massimo","N/D")}</div><div class="ic-note">{dati.get("investimento_massimo_nota","")}</div></div>
</div>
{mix_bar_html}{note_html}
<div class="section-label">Beneficiari e Tempistiche</div>
<div class="two-col">
  <div class="col-box"><div class="col-box-title">Chi può candidarsi</div><ul>{chi_list}</ul></div>
  <div class="col-box"><div class="col-box-title">Tempistiche principali</div>{temp_rows}</div>
</div>
<div class="cta-footer">
  <div><div class="cta-title">Lumen Advisors supporta la vostra candidatura</div>
  <div class="cta-desc">Verifica di eligibilità · Strutturazione del programma · Predisposizione della domanda · Monitoraggio e rendicontazione</div></div>
  <div class="cta-right"><p>info@lumenadvisors.it</p><p>+41 79 601 5800</p><p>www.lumenadvisors.it</p></div>
</div>
<div class="page-footer">
  <div style="display:flex;align-items:center;gap:8px">
    <svg width="20" height="20" viewBox="0 0 40 40" fill="none"><polygon points="20,2 38,20 20,38 2,20" fill="none" stroke="#C9A84C" stroke-width="2.5"/><polygon points="20,10 30,20 20,30 10,20" fill="#C9A84C"/></svg>
    <div><div class="pf-name">Lumen Advisors</div><div class="pf-sub">Advisory · Planning · Wealth</div></div>
  </div>
  <div style="font-size:9px;font-style:italic;color:#555">Documento riservato · Uso esclusivo del destinatario</div>
  <div class="pf-right">www.lumenadvisors.it</div>
</div>
</body></html>"""


# ── Caricamento dati ─────────────────────────────────────────────────────────
try:
    url_excel = "https://github.com/marcotulliovaliante/monitor-bandi-pmi/raw/master/bandi_campania.xlsx"
    response = requests.get(url_excel)
    df = pd.read_excel(io.BytesIO(response.content), sheet_name="Bandi")

    # ── Filtri sidebar ───────────────────────────────────────────────────────
    st.sidebar.header("Filtri")
    fonti = ["Tutte"] + sorted(df["Fonte"].unique().tolist())
    fonte_sel = st.sidebar.selectbox("Fonte", fonti)
    stati = ["Tutti"] + sorted(df["Stato"].unique().tolist())
    stato_sel = st.sidebar.selectbox("Stato", stati)

    if "Tipo Beneficiario" in df.columns:
        tipi = ["Tutti"] + sorted(df["Tipo Beneficiario"].dropna().replace("", pd.NA).dropna().unique().tolist())
        tipo_sel = st.sidebar.selectbox("Tipo Beneficiario", tipi)
    else:
        tipo_sel = "Tutti"

    if "Qualità Bando" in df.columns:
        qualita_sel = st.sidebar.selectbox("Qualità Bando", ["Tutte", "Alta", "Media", "Bassa"])
    else:
        qualita_sel = "Tutte"

    cerca = st.sidebar.text_input("🔍 Cerca nel titolo")

    df_filtrato = df.copy()
    if fonte_sel != "Tutte":
        df_filtrato = df_filtrato[df_filtrato["Fonte"] == fonte_sel]
    if stato_sel != "Tutti":
        df_filtrato = df_filtrato[df_filtrato["Stato"] == stato_sel]
    if tipo_sel != "Tutti" and "Tipo Beneficiario" in df.columns:
        df_filtrato = df_filtrato[df_filtrato["Tipo Beneficiario"].str.contains(tipo_sel, na=False)]
    if qualita_sel != "Tutte" and "Qualità Bando" in df.columns:
        df_filtrato = df_filtrato[df_filtrato["Qualità Bando"] == qualita_sel]
    if cerca:
        df_filtrato = df_filtrato[df_filtrato["Titolo"].str.contains(cerca, case=False, na=False)]

    # ── Metriche ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totale bandi", len(df))
    col2.metric("Bandi aperti", len(df[df["Stato"] == "✅ Aperto"]))
    col3.metric("Risultati filtrati", len(df_filtrato))
    col4.metric("Fonti monitorate", df["Fonte"].nunique())

    st.divider()

    # ── Pannello Admin ───────────────────────────────────────────────────────
    if st.session_state.ruolo == "admin":
        with st.expander("⚙️ Pannello di controllo"):
            st.subheader("Lancia lo scraper manualmente")
            st.caption("Avvia il workflow GitHub Actions per aggiornare i bandi")
            if st.button("🚀 Aggiorna bandi ora"):
                token = st.secrets.get("PAT_TOKEN", "")
                if token:
                    r = requests.post(
                        "https://api.github.com/repos/marcotulliovaliante/monitor-bandi-pmi/actions/workflows/monitor_bandi.yml/dispatches",
                        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                        json={"ref": "master"}
                    )
                    if r.status_code == 204:
                        st.success("✅ Workflow avviato! Attendi 30 minuti per i risultati.")
                    else:
                        st.error(f"Errore: {r.status_code} — {r.text}")
                else:
                    st.error("PAT_TOKEN non configurato")

            st.divider()
            st.subheader("📧 Gestione destinatari email")
            try:
                r_config = requests.get("https://raw.githubusercontent.com/marcotulliovaliante/monitor-bandi-pmi/master/config.json")
                config = r_config.json()
                destinatari = config.get("destinatari", [])
            except:
                destinatari = []

            for email in destinatari:
                st.write(f"• {email}")

            nuova_email = st.text_input("Aggiungi email")
            if st.button("➕ Aggiungi destinatario"):
                if nuova_email and nuova_email not in destinatari:
                    destinatari.append(nuova_email)
                    token = st.secrets.get("PAT_TOKEN", "")
                    if token:
                        import base64, json as json_lib
                        nuovo_config = json_lib.dumps({"destinatari": destinatari}, indent=4)
                        r_get = requests.get(
                            "https://api.github.com/repos/marcotulliovaliante/monitor-bandi-pmi/contents/config.json",
                            headers={"Authorization": f"token {token}"}
                        )
                        sha = r_get.json().get("sha", "")
                        requests.put(
                            "https://api.github.com/repos/marcotulliovaliante/monitor-bandi-pmi/contents/config.json",
                            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                            json={"message": f"Aggiunto destinatario {nuova_email}",
                                  "content": base64.b64encode(nuovo_config.encode()).decode(), "sha": sha}
                        )
                        st.success(f"✅ {nuova_email} aggiunto!")
                        st.rerun()
        st.divider()

    # ── Tabella bandi ────────────────────────────────────────────────────────
    st.subheader(f"Bandi trovati: {len(df_filtrato)}")
    colonne_principali = ["Titolo", "Scadenza", "Tipo Beneficiario", "Qualità Bando", "Fonte", "Link"]
    colonne_presenti = [c for c in colonne_principali if c in df_filtrato.columns]

    st.dataframe(
        df_filtrato[colonne_presenti],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Titolo": st.column_config.TextColumn("Titolo", width="large"),
            "Scadenza": st.column_config.TextColumn("Scadenza", width="medium"),
            "Tipo Beneficiario": st.column_config.TextColumn("Beneficiari", width="medium"),
            "Qualità Bando": st.column_config.TextColumn("Qualità", width="small"),
            "Fonte": st.column_config.TextColumn("Fonte", width="medium"),
            "Link": st.column_config.LinkColumn("🔗", width="small", display_text="Apri"),
        }
    )

    # ── Dettaglio bando + Genera Factsheet ───────────────────────────────────
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
            if "Tipo Beneficiario" in bando and str(bando["Tipo Beneficiario"]) not in ["nan", "", "N/D"]:
                st.markdown(f"**Tipo Beneficiario:** {bando['Tipo Beneficiario']}")
        with col2:
            if "Qualità Bando" in bando and str(bando["Qualità Bando"]) not in ["nan", ""]:
                st.markdown(f"**Qualità Bando:** {bando['Qualità Bando']}")
            if "Settore ATECO" in bando and str(bando["Settore ATECO"]) not in ["nan", "N/A", ""]:
                st.markdown(f"**Settore ATECO:** {bando['Settore ATECO']}")
            if "Settore ETS" in bando and str(bando["Settore ETS"]) not in ["nan", "N/A", ""]:
                st.markdown(f"**Settore ETS:** {bando['Settore ETS']}")
            if "Fascia Demografica" in bando and str(bando["Fascia Demografica"]) not in ["nan", "N/A", ""]:
                st.markdown(f"**Fascia Demografica:** {bando['Fascia Demografica']}")
            if "Motivazione AI" in bando and str(bando["Motivazione AI"]) not in ["nan", ""]:
                st.markdown(f"**Analisi AI:** {bando['Motivazione AI']}")
            if "Link" in bando and str(bando["Link"]) not in ["nan", ""]:
                st.link_button("🔗 Vai al bando", str(bando["Link"]))

        # ── Pulsante Genera Factsheet (solo Admin) ───────────────────────────
        if st.session_state.ruolo == "admin":
            st.divider()
            link_bando = str(bando.get("Link", "")) if str(bando.get("Link", "")) not in ["nan", ""] else ""

        if not link_bando:
            st.warning("⚠️ Link non disponibile per questo bando — impossibile generare il factsheet automatico.")
        else:
            col_btn, col_info = st.columns([2, 5])
            with col_btn:
                genera_btn = st.button("📄 Genera Factsheet", type="primary", use_container_width=True)
            with col_info:
                st.caption("Claude Sonnet legge la pagina del bando e genera un factsheet Lumen pronto da scaricare e stampare. Operazione: ~30 secondi.")

            if genera_btn:
                with st.spinner("⏳ Claude sta leggendo il bando e generando il factsheet..."):
                    try:
                        dati = estrai_dati_bando(
                            titolo=str(bando["Titolo"]),
                            fonte=str(bando["Fonte"]),
                            scadenza=str(bando["Scadenza"]),
                            link=link_bando,
                            tipo_beneficiario=str(bando.get("Tipo Beneficiario", "N/D")),
                            motivazione_ai=str(bando.get("Motivazione AI", ""))
                        )
                        nome_file = str(bando["Titolo"]).lower().replace(" ", "_").replace("/", "-")[:40]
                        data_oggi = datetime.now().strftime('%Y%m%d')
                        st.success("✅ Factsheet generato!")
                        col_html, col_word = st.columns(2)
                        with col_html:
                            html_bytes = genera_factsheet_html(dati, str(bando["Titolo"]), str(bando["Fonte"])).encode("utf-8")
                            st.download_button(
                                label="⬇️ Scarica HTML",
                                data=html_bytes,
                                file_name=f"factsheet_{nome_file}_{data_oggi}.html",
                                mime="text/html",
                                type="primary",
                                use_container_width=True
                            )
                            st.caption("Layout completo → apri nel browser → stampa PDF")
                        with col_word:
                            docx_bytes = genera_factsheet_word(dati, str(bando["Titolo"]), str(bando["Fonte"]), str(bando["Scadenza"]))
                            st.download_button(
                                label="⬇️ Scarica Word",
                                data=docx_bytes,
                                file_name=f"factsheet_{nome_file}_{data_oggi}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )
                            st.caption("Campi N/D evidenziati → modifica in Word → stampa PDF")
                    except Exception as e:
                        st.error(f"Errore nella generazione del factsheet: {e}")

    # ── Download Admin ───────────────────────────────────────────────────────
    if st.session_state.ruolo == "admin":
        st.divider()
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            r_excel = requests.get("https://github.com/marcotulliovaliante/monitor-bandi-pmi/raw/master/bandi_campania.xlsx")
            st.download_button(
                label="⬇️ Scarica Excel completo",
                data=r_excel.content,
                file_name=f"bandi_campania_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col_down2:
            csv_data = df_filtrato.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Scarica CSV filtrato",
                data=csv_data,
                file_name=f"bandi_filtrati_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

except Exception as e:
    st.error(f"Errore nel caricamento dei dati: {e}")
