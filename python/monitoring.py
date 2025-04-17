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
load_dotenv("/app/PSM-Squad/.env")
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
file_path = "/app/PSM-Squad/lxc_status_report.txt"
if not os.path.exists(file_path):
    logging.error("🚫 Report file not found. Email skipped.")
    exit(1)

with open(file_path, "r") as f:
    raw_status = f.read()

# === 4. Summary generation with ChatGPT ===
os.environ["OPENAI_API_KEY"] = openai_api_key  # Make it compatible with LangChain

prompt_template = PromptTemplate.from_template("""
You are a Linux systems assistant. Analyze this Proxmox LXC container report and generate a summary in HTML format.

1. The title should be PSM Server Report Summary
2. Which containers and their names are running or stopped?
3. Which services, like Ollama, and their names are running or stopped?
4. Are there any services and their names not running or missing in any LCX?
5. Are any Docker containers and their names down in any LCX?

Report:
{raw_status}
""")

llm = ChatOpenAI(model="gpt-4", temperature=0)
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
