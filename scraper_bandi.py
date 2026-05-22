import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
import anthropic
import json
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ANTHROPIC_API_KEY = "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"
GMAIL_USER = "marcotullio.valiante@gmail.com"
GMAIL_APP_PASSWORD = "gedk gkdb nxvx liqo"
EMAIL_DESTINATARIO = "marcotullio.valiante@gmail.com"
FILE_BANDI_VISTI = "bandi_visti.json"

def analizza_bando_con_claude(titolo, fonte, scadenza):
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        messaggio = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Analizza questo bando per una PMI in Campania.
Titolo: {titolo}
Fonte: {fonte}

Rispondi SOLO con questo JSON, niente altro:
{{"pertinenza": "Alta", "categoria": "Formazione", "motivazione": "esempio"}}

Sostituisci i valori con la tua analisi. Pertinenza può essere Alta, Media o Bassa."""
            }]
        )
        testo = messaggio.content[0].text.strip()
        # Cerca il JSON nella risposta
        import re
        match = re.search(r'\{.*\}', testo, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"pertinenza": "N/D", "categoria": "N/D", "motivazione": testo[:100]}
    except Exception as e:
        return {"pertinenza": "N/D", "categoria": "N/D", "motivazione": str(e)}
BASE_URL_CAMPANIA = "https://agricoltura.regione.campania.it/"
def parse_data(testo):
    if not testo or testo == "Non specificata":
        return None
    mesi = {
        "gennaio": "01", "febbraio": "02", "marzo": "03",
        "aprile": "04", "maggio": "05", "giugno": "06",
        "luglio": "07", "agosto": "08", "settembre": "09",
        "ottobre": "10", "novembre": "11", "dicembre": "12"
    }
    testo_pulito = testo.lower().strip().split(" -")[0].split("–")[0].strip()
    testo_pulito = testo_pulito.replace("prorogato al", "").strip()
    for mese_it, mese_num in mesi.items():
        if mese_it in testo_pulito:
            testo_pulito = testo_pulito.replace(mese_it, mese_num)
    formati = ["%d/%m/%Y", "%d %m %Y", "%d %m%Y", "%Y-%m-%d"]
    for fmt in formati:
        try:
            return datetime.strptime(testo_pulito.strip(), fmt)
        except:
            continue
    return None

def calcola_stato(scadenza_testo):
    data = parse_data(scadenza_testo)
    if data is None:
        return "Non specificata"
    return "✅ Aperto" if data >= datetime.today() else "❌ Scaduto"

def scrapa_invitalia():
    try:
        url = "https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese"
        risposta = requests.get(url, timeout=10)
        soup = BeautifulSoup(risposta.text, "html.parser")
        bandi = []
        titolo_corrente = None
        for tag in soup.find_all(["h3", "p"]):
            testo = tag.text.strip()
            if tag.name == "h3" and len(testo) > 5:
                titolo_corrente = testo
            if tag.name == "p" and "Attivo" in testo and titolo_corrente:
                info = testo.replace("Attivo", "").strip()
                chiusura = ""
                if "Data apertura:" in info:
                    parti = info.split("Data chiusura:")
                    chiusura = parti[1].strip() if len(parti) > 1 else ""
                bandi.append({
                    "Titolo": titolo_corrente,
                    "Scadenza": chiusura if chiusura else "Non specificata",
                    "Link": "https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese",
                    "Fonte": "Invitalia"
                })
        return bandi
    except Exception as e:
        print(f"  ⚠️ Errore Invitalia: {e}")
        return []

def scrapa_regione_campania():
    try:
        url = BASE_URL_CAMPANIA + "bandi.html"
        risposta = requests.get(url, timeout=10)
        soup = BeautifulSoup(risposta.text, "html.parser")
        bandi = []
        tabelle = soup.find_all("table", class_="table")
        for tabella in tabelle:
            righe = tabella.find_all("tr")
            for riga in righe[1:]:
                celle = riga.find_all("td")
                if len(celle) >= 2:
                    titolo = celle[0].text.strip()
                    scadenza = celle[1].text.strip()
                    link_tag = celle[2].find("a") if len(celle) > 2 else None
                    link_rel = link_tag.get("href", "") if link_tag else ""
                    link = BASE_URL_CAMPANIA + link_rel if link_rel else ""
                    if titolo and titolo != "nessun bando aperto":
                        bandi.append({
                            "Titolo": titolo,
                            "Scadenza": scadenza,
                            "Link": link,
                            "Fonte": "Regione Campania - Agricoltura"
                        })
        return bandi
    except Exception as e:
        print(f"  ⚠️ Errore Regione Campania: {e}")
        return []

def scrapa_gal_cilento():
    try:
        url = "https://www.galcilento.it/bandi/"
        risposta = requests.get(url, timeout=10)
        soup = BeautifulSoup(risposta.text, "html.parser")
        bandi = []
        for bando_div in soup.find_all("div", class_="bando-single"):
            titolo_tag = bando_div.find("h2")
            titolo = titolo_tag.text.strip() if titolo_tag else ""
            link_tag = bando_div.find("a")
            link = link_tag.get("href", "") if link_tag else ""
            chiusura = ""
            for te in bando_div.find_all("div", class_="time-event"):
                testo = te.text.strip()
                if "Chiusura" in testo:
                    chiusura = testo.replace("Chiusura:", "").strip()
            if titolo:
                bandi.append({
                    "Titolo": titolo,
                    "Scadenza": chiusura if chiusura else "Non specificata",
                    "Link": link,
                    "Fonte": "GAL Cilento"
                })
        return bandi
    except Exception as e:
        print(f"  ⚠️ Errore GAL Cilento: {e}")
        return []

def scrapa_bandi_ue():
    try:
        print("  Scaricando database bandi UE (attendere...)")
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData/grantsTenders.json"
        risposta = requests.get(url, timeout=60)
        data = risposta.json()
        tutti = data.get("fundingData", {}).get("GrantTenderObj", [])
        bandi = []
        for b in tutti:
            status = b.get("status", {}).get("abbreviation", "")
            if status != "Open":
                continue
            titolo = b.get("title", "N/D")
            deadline_list = b.get("deadlineDatesLong", [])
            if deadline_list:
                scadenza = datetime.fromtimestamp(deadline_list[-1] / 1000).strftime("%d/%m/%Y")
            else:
                scadenza = "Non specificata"
            identificatore = b.get("identifier", "")
            link = f"https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{identificatore}"
            programma = b.get("frameworkProgramme", {}).get("abbreviation", "UE")
            bandi.append({
                "Titolo": titolo,
                "Scadenza": scadenza,
                "Link": link,
                "Fonte": f"UE - {programma}"
            })
        return bandi
    except Exception as e:
        print(f"  ⚠️ Errore bandi UE: {e}")
        return []

def scrapa_incentivi_gov():
    try:
        print("  Scaricando incentivi da incentivi.gov.it...")
        url = "https://www.incentivi.gov.it/solr/coredrupal/select?q.op=OR&wt=json&rows=8000&fl=nid%3Azs_nid%2Cpage_title%3Azs_title%2Copen_date%3Azs_field_open_date%2Cclose_date%3Azs_field_close_date%2Cregions%3Azm_field_regions%2Csubject_type%3Azm_field_subject_type%2Csupport_form%3Azm_field_support_form%2C&q=index_id%3Aincentivi&sort=ds_last_update+desc"
        
        risposta = requests.get(url, timeout=30)
        data = risposta.json()
        docs = data["response"]["docs"]
        
        oggi = datetime.today()
        bandi = []
        
        for doc in docs:
            titolo = doc.get("page_title", "N/D")
            close_date = doc.get("close_date", "")
            open_date = doc.get("open_date", "")
            nid = doc.get("nid", "")
            link = f"https://www.incentivi.gov.it/it/catalogo/{nid}"
            
            # Filtra solo incentivi aperti
            if close_date:
                scadenza_dt = datetime.strptime(close_date[:10], "%Y-%m-%d")
                if scadenza_dt < oggi:
                    continue
                scadenza = scadenza_dt.strftime("%d/%m/%Y")
            else:
                scadenza = "Non specificata"
            
            bandi.append({
                "Titolo": titolo,
                "Scadenza": scadenza,
                "Link": link,
                "Fonte": "incentivi.gov.it"
            })
        
        return bandi
    except Exception as e:
        print(f"  ⚠️ Errore incentivi.gov.it: {e}")
        return []
def carica_bandi_visti():
    try:
        with open(FILE_BANDI_VISTI, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()

def salva_bandi_visti(titoli):
    with open(FILE_BANDI_VISTI, "w", encoding="utf-8") as f:
        json.dump(list(titoli), f, ensure_ascii=False)

def invia_email_bandi(bandi_nuovi, totale_aperti):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔔 Monitor Bandi — {len(bandi_nuovi)} nuovi bandi — {datetime.now().strftime('%d/%m/%Y')}"
        msg["From"] = GMAIL_USER
        msg["To"] = EMAIL_DESTINATARIO

        righe = ""
        for b in bandi_nuovi[:20]:
            pertinenza = b.get("Pertinenza PMI", "")
            colore = "#166534" if pertinenza == "Alta" else "#92400e" if pertinenza == "Media" else "#6B7280"
            righe += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{b['Titolo'][:80]}</td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{b['Scadenza']}</td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;color:{colore};font-weight:bold">{pertinenza}</td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{b['Fonte']}</td>
            </tr>"""

        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto">
            <div style="background:#1A56DB;color:white;padding:20px;border-radius:8px 8px 0 0">
                <h2 style="margin:0">🔔 Monitor Bandi PMI Campania</h2>
                <p style="margin:5px 0 0 0">{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
            <div style="background:#f9fafb;padding:20px;border-radius:0 0 8px 8px">
                <p>Sono stati trovati <strong>{len(bandi_nuovi)} nuovi bandi</strong> oggi.<br>
                Totale bandi aperti nel sistema: <strong>{totale_aperti}</strong></p>
                <table style="width:100%;border-collapse:collapse;background:white;border-radius:8px">
                    <tr style="background:#1A56DB;color:white">
                        <th style="padding:10px;text-align:left">Titolo</th>
                        <th style="padding:10px;text-align:left">Scadenza</th>
                        <th style="padding:10px;text-align:left">Pertinenza</th>
                        <th style="padding:10px;text-align:left">Fonte</th>
                    </tr>
                    {righe}
                </table>
                <p style="color:#6B7280;font-size:12px;margin-top:20px">
                    Monitor Bandi PMI Campania — aggiornamento automatico giornaliero
                </p>
            </div>
        </body></html>"""

        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD.replace(" ", ""))
            server.sendmail(GMAIL_USER, EMAIL_DESTINATARIO, msg.as_string())
        print(f"✅ Email inviata a {EMAIL_DESTINATARIO}")
    except Exception as e:
        print(f"⚠️ Errore invio email: {e}")

def formatta_excel(filename, n_aperti, n_ns, n_scaduti):
    wb = load_workbook(filename)
    ws = wb.active
    ws.title = "Bandi"
    header_fill = PatternFill("solid", fgColor="1A56DB")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    aperto_fill = PatternFill("solid", fgColor="DCFCE7")
    scaduto_fill = PatternFill("solid", fgColor="FEE2E2")
    ns_fill = PatternFill("solid", fgColor="FEF9C3")
    border = Border(
        left=Side(style="thin", color="E5E7EB"),
        right=Side(style="thin", color="E5E7EB"),
        top=Side(style="thin", color="E5E7EB"),
        bottom=Side(style="thin", color="E5E7EB")
    )
    ws.column_dimensions["A"].width = 55
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 50
    ws.column_dimensions["D"].width = 25
    ws.column_dimensions["E"].width = 16
    for col in range(1, 6):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    ws.row_dimensions[1].height = 22
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        stato = row[4].value if row[4].value else ""
        if "Aperto" in stato:
            fill = aperto_fill
        elif "Scaduto" in stato:
            fill = scaduto_fill
        else:
            fill = ns_fill
        for cell in row:
            cell.fill = fill
            cell.border = border
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[row[0].row].height = 30
    ws2 = wb.create_sheet("Riepilogo")
    ws2["A1"] = "Monitor Bandi PMI Campania"
    ws2["A1"].font = Font(bold=True, size=14, color="1A56DB")
    ws2["A3"] = "Ultimo aggiornamento:"
    ws2["B3"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws2["A3"].font = Font(bold=True)
    ws2["A5"] = "Fonti monitorate:"
    ws2["A5"].font = Font(bold=True)
    ws2["A6"] = "• Invitalia"
    ws2["A7"] = "• Regione Campania - Agricoltura"
    ws2["A8"] = "• GAL Cilento"
    ws2["A9"] = "• UE - Funding & Tenders Portal"
    ws2["A11"] = "Totale bandi:"
    ws2["B11"] = n_aperti + n_ns + n_scaduti
    ws2["A12"] = "✅ Aperti:"
    ws2["B12"] = n_aperti
    ws2["A12"].font = Font(color="166534")
    ws2["A13"] = "⏳ Non specificati:"
    ws2["B13"] = n_ns
    ws2["A14"] = "❌ Scaduti:"
    ws2["B14"] = n_scaduti
    ws2["A14"].font = Font(color="991B1B")
    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 20
    wb.save(filename)

# === MAIN ===
print("=" * 50)
print("MONITOR BANDI PMI CAMPANIA")
print(f"Avvio: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("=" * 50)

print("\nScaricando bandi da Invitalia...")
bandi_invitalia = scrapa_invitalia()
print(f"  → {len(bandi_invitalia)} bandi trovati")

print("Scaricando bandi da Regione Campania...")
bandi_campania = scrapa_regione_campania()
print(f"  → {len(bandi_campania)} bandi trovati")

print("Scaricando bandi da GAL Cilento...")
bandi_gal = scrapa_gal_cilento()
print(f"  → {len(bandi_gal)} bandi trovati")

print("Scaricando bandi da incentivi.gov.it...")
bandi_incentivi = scrapa_incentivi_gov()
print(f"  → {len(bandi_incentivi)} bandi trovati")

print("Scaricando bandi da portale UE...")
bandi_ue = scrapa_bandi_ue()
print(f"  → {len(bandi_ue)} bandi trovati")

tutti_i_bandi = bandi_invitalia + bandi_campania + bandi_gal + bandi_ue
print(f"\nTotale bandi raccolti: {len(tutti_i_bandi)}")

df = pd.DataFrame(tutti_i_bandi)
df["Stato"] = df["Scadenza"].apply(calcola_stato)
df["_data_ord"] = df["Scadenza"].apply(parse_data)

df_aperti = df[df["Stato"] == "✅ Aperto"].sort_values("_data_ord")
df_ns = df[df["Stato"] == "Non specificata"]
df_scaduti = df[df["Stato"] == "❌ Scaduto"].sort_values("_data_ord", ascending=False)

df_finale = pd.concat([df_aperti, df_ns, df_scaduti]).drop(columns=["_data_ord"])

filename = "bandi_campania.xlsx"
df_finale.to_excel(filename, index=False)

formatta_excel(filename, len(df_aperti), len(df_ns), len(df_scaduti))

print(f"\n✅ File Excel salvato e formattato!")
print(f"   Aperti: {len(df_aperti)} | Non specificati: {len(df_ns)} | Scaduti: {len(df_scaduti)}")
print(f"\nCompletato: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("=" * 50)

print("=" * 50)
print("MONITOR BANDI PMI CAMPANIA")
print(f"Avvio: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("=" * 50)

print("\nScaricando bandi da Invitalia...")
bandi_invitalia = scrapa_invitalia()
print(f"  → {len(bandi_invitalia)} bandi trovati")

print("Scaricando bandi da Regione Campania...")
bandi_campania = scrapa_regione_campania()
print(f"  → {len(bandi_campania)} bandi trovati")

print("Scaricando bandi da GAL Cilento...")
bandi_gal = scrapa_gal_cilento()
print(f"  → {len(bandi_gal)} bandi trovati")

print("Scaricando bandi da portale UE...")
bandi_ue = scrapa_bandi_ue()
print(f"  → {len(bandi_ue)} bandi trovati")

tutti_i_bandi = bandi_invitalia + bandi_campania + bandi_gal + bandi_ue + bandi_incentivi
print(f"\nTotale bandi raccolti: {len(tutti_i_bandi)}")

df = pd.DataFrame(tutti_i_bandi)
df["Stato"] = df["Scadenza"].apply(calcola_stato)
df["_data_ord"] = df["Scadenza"].apply(parse_data)

# Analisi AI solo sui bandi aperti
print("\nAnalisi AI dei bandi aperti con Claude...")
pertinenza_list = []
categoria_list = []
motivazione_list = []

aperti_mask = df["Stato"] == "✅ Aperto"
totale_aperti = aperti_mask.sum()

for i, (idx, row) in enumerate(df.iterrows()):
    if row["Stato"] == "✅ Aperto":
        if i % 10 == 0:
            print(f"  Analizzando bando {i+1}/{totale_aperti}...")
        analisi = analizza_bando_con_claude(row["Titolo"], row["Fonte"], row["Scadenza"])
        pertinenza_list.append(analisi.get("pertinenza", "N/D"))
        categoria_list.append(analisi.get("categoria", "N/D"))
        motivazione_list.append(analisi.get("motivazione", "N/D"))
    else:
        pertinenza_list.append("")
        categoria_list.append("")
        motivazione_list.append("")

df["Pertinenza PMI"] = pertinenza_list
df["Categoria"] = categoria_list
df["Motivazione AI"] = motivazione_list

df_aperti = df[df["Stato"] == "✅ Aperto"].sort_values(
    ["Pertinenza PMI", "_data_ord"],
    key=lambda x: x.map({"Alta": 0, "Media": 1, "Bassa": 2}) if x.name == "Pertinenza PMI" else x
)
df_ns = df[df["Stato"] == "Non specificata"]
df_scaduti = df[df["Stato"] == "❌ Scaduto"].sort_values("_data_ord", ascending=False)

df_finale = pd.concat([df_aperti, df_ns, df_scaduti]).drop(columns=["_data_ord"])

filename = "bandi_campania.xlsx"
df_finale.to_excel(filename, index=False)

formatta_excel(filename, len(df_aperti), len(df_ns), len(df_scaduti))

# Confronta con bandi già visti
bandi_visti = carica_bandi_visti()
bandi_aperti_lista = df_aperti.to_dict("records")
bandi_nuovi = [b for b in bandi_aperti_lista if b["Titolo"] not in bandi_visti]

# Aggiorna il file dei bandi visti
tutti_titoli = set(df_aperti["Titolo"].tolist())
salva_bandi_visti(tutti_titoli)

# Invia email se ci sono nuovi bandi
if bandi_nuovi:
    print(f"\n📧 Trovati {len(bandi_nuovi)} nuovi bandi — invio email...")
    invia_email_bandi(bandi_nuovi, len(df_aperti))
else:
    print("\n📭 Nessun nuovo bando trovato oggi.")

print(f"\n✅ File Excel salvato con analisi AI!")
print(f"   Aperti: {len(df_aperti)} | Non specificati: {len(df_ns)} | Scaduti: {len(df_scaduti)}")
print(f"\nCompletato: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("=" * 50)
