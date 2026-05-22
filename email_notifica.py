import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

GMAIL_USER = "marcotullio.valiante@gmail.com"      # sostituisci con la tua email Gmail
GMAIL_APP_PASSWORD = "gedk gkdb nxvx liqo"  # la tua app password
EMAIL_DESTINATARIO = "marcotullio.valiante@gmail.com"  # dove vuoi ricevere le notifiche

def invia_email_bandi(bandi_nuovi, totale_aperti):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 Monitor Bandi — {len(bandi_nuovi)} nuovi bandi — {datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_DESTINATARIO

    # Corpo email in HTML
    righe = ""
    for b in bandi_nuovi[:20]:  # massimo 20 in email
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

# Test
if __name__ == "__main__":
    bandi_test = [
        {"Titolo": "Sviluppo competenze PMI", "Scadenza": "23/06/2026", "Pertinenza PMI": "Alta", "Fonte": "Invitalia"},
        {"Titolo": "Bando FESR Campania", "Scadenza": "30/07/2026", "Pertinenza PMI": "Media", "Fonte": "Regione Campania"},
    ]
    invia_email_bandi(bandi_test, 853)