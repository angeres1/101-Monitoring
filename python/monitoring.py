import os
import smtplib
import logging
import subprocess
import re
from datetime import datetime
from email.message import EmailMessage
from email.mime.text import MIMEText
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

# === 1. Load variables from .env ===
load_dotenv("/root/monitoring/.env")
openai_api_key = os.getenv("OPENAI_API_KEY")
smtp_user = os.getenv("EMAIL_USER")
smtp_password = os.getenv("EMAIL_PASSWORD")

# === 2. Configure logging in persistent file ===
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
    logging.error("🚫 Report file not found. Email skipped.")
    exit(1)

with open(file_path, "r") as f:
    raw_status = f.read()

# === 4. Summary generation with ChatGPT ===
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

💻 1. PSM Host Hardware Summary
Show CPU, RAM, Disk Usage, and Uptime.
                                               
🎮 2. NVIDIA GPU Info
Show GPU name, memory, and utilization.
                                                                                                                                       
🔒 3. Tailscale VPN Status:
Show status of Tailscale VPN connection.
                                               
🧠 4. PSM AI SERVER (VM 302):
Show RAM, Uptime, Disk Usage and status of containers psmfrigate, psmollama and psmopenwebui.
                                               
🏡 5. Home Assistant Status (VM 301):
Show RAM, Uptime, Disk Usage, and Core Version.
                                               
📦 6. List of all LXC Containers:
Display the container name, status (Running/Stopped), disk used, and RAM used. Format as a table.

🐳 7. Docker Containers:
Table of containers with name and status.

≈
                                               
---

{raw_status}
""")

llm = ChatOpenAI(model="gpt-4o", temperature=0)
chain = prompt_template | llm

raw_status = raw_status.encode("utf-8", "replace").decode("utf-8")
html_summary = chain.invoke({"raw_status": raw_status}).content

# Sanitize HTML output
html_summary = re.sub(r'^```(?:html)?\s*', '', html_summary, flags=re.IGNORECASE)
html_summary = re.sub(r'^\s*html\s*\n', '', html_summary, flags=re.IGNORECASE)
html_summary = html_summary.replace("```", "").strip()

# === 5. Format final email HTML ===
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
    <p>This is your daily PSM Server report.<br>
    (If parts don’t display correctly, please enable HTML view).</p>
    {html_summary}
  </body>
</html>
"""

# === 6. Email sending ===
msg = EmailMessage()
msg["Subject"] = "📊 Daily PSM Server Executive Report"
msg["From"] = smtp_user
recipients = [smtp_user, "aleja.als@gmail.com"]
msg["To"] = ", ".join(recipients)

msg.set_content(
    "This is your daily PSM Server report.\n"
    "If you do not see a formatted report, please view the HTML version.",
    subtype="plain",
    charset="utf-8"
)

msg.add_alternative(email_html, subtype="html", charset="utf-8")
logging.debug("Email MIME payload:\n%s", msg.as_string())

try:
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
    logging.info("📧 Email sent successfully to %s", smtp_user)
except Exception as e:
    logging.error(f"❌ Failed to send email: {e}")