import os
import smtplib
import logging
import subprocess
import re
from datetime import datetime
from email.header import Header
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

# === 1. Load variables from .env ===
load_dotenv("/app/monitoring/.env")
openai_api_key = os.getenv("OPENAI_API_KEY")
smtp_user = os.getenv("EMAIL_USER")
smtp_password = os.getenv("EMAIL_PASSWORD")

# === 2. Configure logging in persistant file ===
log_path = "/var/log/lxc_qm_report.log"
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="[{asctime}] {levelname}: {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.info("")
logging.info("===== 🕒 New Daily Execution: %s =====", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# === 3. Load the original report ===
file_path = "/root/lxc-qm-reports/lxc_qm_status_report.txt"
if not os.path.exists(file_path):
    logging.error("\ud83d\udeab Report file not found. Email skipped.")
    exit(1)

with open(file_path, "r") as f:
    raw_status = f.read()

# === 4. Prepare Certificate Section ===
def get_cert_expiration_html(cert_map):
    html_rows = ""
    for domain, path in cert_map.items():
        try:
            output = subprocess.check_output([
                "openssl", "x509", "-enddate", "-noout", "-in", path
            ]).decode().strip()
            expiry_str = output.split('=')[1]
            expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
            days_left = (expiry_date - datetime.utcnow()).days

            if days_left > 30:
                status = '<span style="color:green">\u2705 OK</span>'
            elif 15 < days_left <= 30:
                status = '<span style="color:orange">\u26a0\ufe0f Renew Soon</span>'
            else:
                status = '<span style="color:red">\u274c Expiring</span>'

            html_rows += f"<tr><td>{domain}</td><td>{expiry_date.date()}</td><td>{days_left}</td><td>{status}</td></tr>\n"

        except Exception as e:
            html_rows += f"<tr><td>{domain}</td><td colspan='3' style='color:red;'>Error: {e}</td></tr>\n"

    return f"""
    <h2>&#128274; Let's Encrypt Certificates</h2>  <!-- HTML Unicode for 🔒 -->
    <table border=\"1\" cellspacing=\"0\" cellpadding=\"6\">
        <thead>
            <tr><th>Domain</th><th>Expires On</th><th>Days Left</th><th>Status</th></tr>
        </thead>
        <tbody>
            {html_rows}
        </tbody>
    </table>
    """

cert_map = {
    "start.psmsquad.com": "/mnt/certs/live/npm-27/fullchain.pem",
    "n8n.psmsquad.com": "/mnt/certs/live/npm-32/fullchain.pem",
    "ollama-ui.psmsquad.com": "/mnt/certs/live/npm-33/fullchain.pem",
    "home.psmsquad.com": "/mnt/certs/live/npm-31/fullchain.pem",
    "proxmox.psmsquad.com": "/mnt/certs/live/npm-25/fullchain.pem",
    "cloud.psmsquad.com": "/mnt/certs/live/npm-34/fullchain.pem",
}

cert_section = get_cert_expiration_html(cert_map)
cert_section = cert_section.encode("utf-8", "replace").decode("utf-8")

# === 5. Summary generation with ChatGPT ===
os.environ["OPENAI_API_KEY"] = openai_api_key

prompt_template = PromptTemplate.from_template("""

You are a Linux systems assistant. Analyze the provided Proxmox LXC container report and generate a full HTML summary page with the following:

1. Use a clean HTML structure with inline styles only (no external CSS or JavaScript).
2. The final page title must be: <title>PSM Server Report Summary</title>.
3. Use consistent <h2> or <h3> headers for each section.
4. Always use <table> with <thead> and <tbody> for tabular data.
5. Avoid including any section if no data is found for it.
6. Use semantic, valid HTML only.

Your summary must include the following sections:

---

📦 1. List of all LXC Containers:

Display the container name, status (Running/Stopped), disk used, and RAM used. Format as a table:

| Container Name | Status | Disk Used | RAM Used |

Disk and RAM can be extracted from lines like:
   ➜ /dev/loop0 1.1G used of 8.5G (13% mounted on /)
   🔹 RAM Usage: 830Mi / 2.0Gi (40% used)

---

⚙️ 2. Ollama Service (LXC 205):

Extract and show a one-line sentence if ollama.service is:
- active ✅
- inactive ⚠️
- not found ❌

Highlight the result with bold or colored span.

---

🐳 3. Docker Containers:

List all Docker containers that are found inside LXC containers. Table format:

| Container Name | Status |

Extract lines like:
   ➜ myservice (Up 3 hours)
   ➜ postgres (Exited)

Ignore containers that don't have Docker installed.

---

🌡️ 4. System Temperatures:

Extract temperatures from these lines:
   🌡️ CPU Temperature (Tctl): 57.5°C
   📀 NVMe Temperature: 48.0°C
   🌡️ Temperature: 70°C (GPU)

Compare them against thresholds below and classify each one with a "Status" column:

| Component | Temperature | Celsius | Status (OK/Warning/Critical) |

Use colored spans in Status:
- `<span style="color:green">OK</span>`
- `<span style="color:orange">Warning</span>`
- `<span style="color:red">Critical</span>`

**Thresholds:**
- CPU:
  - Idle: 35-55°C → OK
  - Load: 70-85°C → OK
  - Hot: 85-95°C → Warning
  - Critical: >95°C → Critical

- GPU:
  - Idle: 30-50°C → OK
  - Load: 60-80°C → OK
  - High: 80-90°C → Warning
  - Critical: >90°C → Critical

- HDD:
  - Idle: 30-45°C → OK
  - Load: 45-70°C → OK
  - High: >70°C → Warning
  - Critical: >85°C → Critical
                                               
🏡 5. Home Assistant Status (VM 130):
Extract and display RAM, Uptime, Disk Usage, and Core Version from the text.

---
                                               
💽 6. Host disk Usage:
Extract and display the usage, total and the percentage of the disk host information.

---

{raw_status}

{cert_section}
""")

#print("=== CERT SECTION PREVIEW ===")
#print(cert_section)
#print("============================")

llm = ChatOpenAI(model="gpt-4o", temperature=0)
chain = prompt_template | llm

raw_status = raw_status.encode("utf-8", "replace").decode("utf-8")
cert_section = cert_section.encode("utf-8", "replace").decode("utf-8")

html_summary = chain.invoke({
    "raw_status": raw_status,
    "cert_section": ""
}).content

# 🔧 Clean up Markdown-style block tags and remove stray leading 'html'
# Remove any opening ``` or ```html
html_summary = re.sub(r'^```(?:html)?\s*', '', html_summary, flags=re.IGNORECASE)
# Remove a leading "html" on its own line (from leftover code-fence labels)
html_summary = re.sub(r'^\s*html\s*\n', '', html_summary, flags=re.IGNORECASE)
# Remove any remaining fences and trim whitespace
html_summary = html_summary.replace("```", "").strip()

# Manually append cert block
html_summary += "\n\n" + cert_section

#with open("/app/monitoring/html_debug_out.html", "w", encoding="utf-8") as f:
#    f.write(html_summary)

logging.info("\u2705 Summary generated.")

# Wrap the summary in full HTML
email_html = f"""
<html>
  <head>
    <meta charset="UTF-8">
    <title>PSM Server Report</title>
    <style>
      table {{
        width: auto !important;
        table-layout: auto !important;
        border-collapse: collapse;
      }}
      th, td {{
        padding: 4px 8px;
        white-space: nowrap;
        border: 1px solid #ccc;
      }}
    </style>
  </head>
  <body>
    <!-- Visible notice for HTML clients -->
    <p>This is your daily PSM Server report.<br>
    (If parts don’t display correctly, please enable HTML view).</p>
    {html_summary}
  </body>
</html>
"""

# === 5. Email ===
# 1️⃣ Plain-text fallback
msg = EmailMessage()
msg["Subject"] = "📊 Daily PSM Server Executive Report"
msg["From"]    = smtp_user
recipients = [smtp_user, "aleja.als@gmail.com"]
msg["To"] = ", ".join(recipients)

msg.set_content(
    "This is your daily PSM Server report.\n"
    "If you do not see a formatted report, please view the HTML version.",
    subtype="plain",
    charset="utf-8"
)

# 2️⃣ HTML alternative
msg.add_alternative(
    email_html,
    subtype="html",
    charset="utf-8"
)

logging.debug("Email MIME payload:\n%s", msg.as_string())

# === 6. Send emil via SMTP ===
try:
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
    logging.info("\ud83d\udce7 Email sent successfully to %s", smtp_user)
except Exception as e:
    logging.error(f"\u274c Failed to send email: {e}")

# === 7. End ===