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
                                               
You are a Linux systems assistant. Analyze the provided Proxmox LXC container report and generate an HTML summary page with the following specifications:
                                               
	•	The page title must be “PSM Server Report Summary”.
	•	Use clean, valid HTML with basic inline CSS styling for readability (e.g., table borders, padding, bold headers).
	•	Structure the HTML content with the following sections:

1.	List of all LXC Containers Status: Display all LXC containers and their statuses (either running or stopped), disk and RAM used in a table format:
    | Container Name | Status | Disk Used | RAM Used |
                                               
2.	Ollama Service (LXC 205): Check if the Ollama service is running or stopped only in LXC container 205. Display this information as a short, clear sentence or highlighted note.
	
3.	Docker Containers: List all Docker containers and their current status in a table format:
    | Container Name | Status |
     
4.	System Temperatures: Show the temperature of the CPU, HDD, and GPU in a table format:
    | Component | Temperature | Celsius | Is it OK? (If so, green, then red) |
    Take into consideration the following thresholds:
    CPU:
    - 35-55°C: Idle - Typical for well-ventilated systems.
    - 70-85°C: Under Load - Normal under sustained CPU use.
    - 85-95°C: Hot - Acceptable short bursts, but monitor.
    - 95-100°C: Critical - May trigger thermal throttling or shutdown.
    
    GPU:
    - 30-50°C: Idle - Normal desktop state.
    - 60-80°C: Gamming/Load - Normal under load.
    - 80-90°C: High - Still safe, but worth watching.
    - >90°C: Critical - Thermal throttling starts around 92 and 95°C.

    HDD:
    - 30-45°C: Idle - Cool and normal.
    - 45-70°C: Under Load - Acceptable during read/write bursts.
    - >70°C: High - Might reduce performance (thermal throttle).
    - >85°C: Critical - Risk of degradation over time.                                 

Ensure the final output is a clean, readable HTML document with inline styles for table formatting. Avoid external CSS or JavaScript.

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
