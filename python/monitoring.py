import os
import smtplib
import logging
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
    logging.error("🚫 Report file not found. Email skipped.")
    exit(1)

with open(file_path, "r") as f:
    raw_status = f.read()

# === 4. Summary generation with ChatGPT ===
os.environ["OPENAI_API_KEY"] = openai_api_key  # Make it compatible with LangChain

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

---

{raw_status}
""")

llm = ChatOpenAI(model="gpt-4o", temperature=0)
chain = prompt_template | llm
html_summary = chain.invoke({"raw_status": raw_status}).content

logging.info("✅ Summary generated.")

# === 5. Email ===
msg = MIMEMultipart()
msg["Subject"] = "📊 Daily PSM Server Executive Report"
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
    logging.info("📧 Email sent successfully to %s", smtp_user)
except Exception as e:
    logging.error(f"❌ Failed to send email: {e}")

# === 7. End ===
