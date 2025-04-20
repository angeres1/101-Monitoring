import os
import smtplib
import logging
import subprocess
from datetime import datetime
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
log_path = "/var/log/lxc_report.log"
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
file_path = "/app/lxc-reports/lxc_status_report.txt"
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
    <h2>\ud83d\udd10 Let's Encrypt Certificates</h2>
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
    "proxmox.psmsquad.com": "/mnt/certs/live/npm-25/fullchain.pem"
}

cert_section = get_cert_expiration_html(cert_map)

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

\ud83d\udce6 1. List of all LXC Containers:

Display the container name, status (Running/Stopped), disk used, and RAM used. Format as a table:

| Container Name | Status | Disk Used | RAM Used |

Disk and RAM can be extracted from lines like:
   \u279c /dev/loop0 1.1G used of 8.5G (13% mounted on /)
   \ud83d\udd39 RAM Usage: 830Mi / 2.0Gi (40% used)

---

\u2699\ufe0f 2. Ollama Service (LXC 205):

Extract and show a one-line sentence if ollama.service is:
- active \u2705
- inactive \u26a0\ufe0f
- not found \u274c

Highlight the result with bold or colored span.

---

\ud83d\udc33 3. Docker Containers:

List all Docker containers that are found inside LXC containers. Table format:

| Container Name | Status |

Extract lines like:
   \u279c myservice (Up 3 hours)
   \u279c postgres (Exited)

Ignore containers that don't have Docker installed.

---

\ud83c\udf21\ufe0f 4. System Temperatures:

Extract temperatures from these lines:
   \ud83c\udf21\ufe0f CPU Temperature (Tctl): 57.5\u00b0C
   \ud83d\udcc0 NVMe Temperature: 48.0\u00b0C
   \ud83c\udf21\ufe0f Temperature: 70\u00b0C (GPU)

Compare them against thresholds below and classify each one with a "Status" column:

| Component | Temperature | Celsius | Status (OK/Warning/Critical) |

Use colored spans in Status:
- `<span style=\"color:green\">OK</span>`
- `<span style=\"color:orange\">Warning</span>`
- `<span style=\"color:red\">Critical</span>`

**Thresholds:**
- CPU:
  - Idle: 35-55\u00b0C \u2192 OK
  - Load: 70-85\u00b0C \u2192 OK
  - Hot: 85-95\u00b0C \u2192 Warning
  - Critical: >95\u00b0C \u2192 Critical

- GPU:
  - Idle: 30-50\u00b0C \u2192 OK
  - Load: 60-80\u00b0C \u2192 OK
  - High: 80-90\u00b0C \u2192 Warning
  - Critical: >90\u00b0C \u2192 Critical

- HDD:
  - Idle: 30-45\u00b0C \u2192 OK
  - Load: 45-70\u00b0C \u2192 OK
  - High: >70\u00b0C \u2192 Warning
  - Critical: >85\u00b0C \u2192 Critical

---

{raw_status}

{cert_section}
""")

llm = ChatOpenAI(model="gpt-4o", temperature=0)
chain = prompt_template | llm
html_summary = chain.invoke({"raw_status": raw_status, "cert_section": cert_section}).content

logging.info("\u2705 Summary generated.")

# === 5. Email ===
msg = MIMEMultipart()
msg["Subject"] = "\ud83d\udcca Daily PSM Server Executive Report"
msg["From"] = smtp_user
msg["To"] = smtp_user

msg.attach(MIMEText(html_summary, "html"))

with open(file_path, "rb") as f:
    attachment = MIMEApplication(f.read(), _subtype="txt")
    attachment.add_header("Content-Disposition", "attachment", filename="lxc_status_report.txt")
    msg.attach(attachment)

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