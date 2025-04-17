# 🧭 101 Monitoring

This repository contains the monitoring logic for the PSM Homelab running on Proxmox VE. The script checks the health of LXC containers and services, generates daily reports, and sends automated emails.

## 🔍 Features

- Inspects all active LXC containers in the Proxmox host
- Detects and reports Docker containers and systemd services per container
- Uses OpenAI via LangChain to generate HTML-formatted summaries
- Sends reports by email with log attachments
- Transfers reports via SCP to a shared path inside the Monitoring container

## 📁 Structure

```
101 monitoring/
├── monitoring.py          # Main monitoring script
├── .env.example           # Environment file template for API/email credentials
└── lxc_status_report.txt  # Generated report file (excluded from Git)
```

## ⚙️ Technologies

- Python 3 (inside Ubuntu 24.04 LXC)
- LangChain + OpenAI API
- Gmail SMTP
- cron + SCP

## 🛠️ Setup Instructions

1. Create a `.env` file using `.env.example`:
   ```env
   OPENAI_API_KEY=your-key
   EMAIL_USER=you@gmail.com
   EMAIL_PASSWORD=your-app-password
   ```

2. Install dependencies:
   ```bash
   pip3 install langchain openai
   ```

3. Add the script to your crontab (inside LXC 101):
   ```bash
   crontab -e
   ```

   ```cron
   15 5 * * * python3 /app/PSM-Squad/repository/monitoring/monitoring.py
   ```

4. (Optional) Check the log:
   ```bash
   tail -f /var/log/lxc_report.log
   ```

## 📡 Runtime

- LXC ID: `101`
- IP Address: `192.168.10.31`
- Hostname: `monitoring`
- Python script path: `/app/PSM-Squad/repository/monitoring/monitoring.py`

## 🔗 Related Projects

- [203-StartPage](https://github.com/angeres1/203-StartPage)
- [PSM-Squad](https://github.com/angeres1/PSM-Squad) – Core homelab documentation