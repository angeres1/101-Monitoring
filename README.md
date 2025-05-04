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
101 root/monitoring
├── python
   └── monitoring.py          # Main monitoring script
├── .env.example              # Environment file template for API/email credentials
├── lxc-qm-reports
   └── lxc_status_report.txt  # Generated report file (excluded from Git)
```

## ⚙️ Technologies

- Python 3 (inside Ubuntu 24.04 LXC)
- LangChain + OpenAI API
- Gmail SMTP
- cron + SCP

## 🛠️ Setup Instructions

1. Create a `.env` file using `.env.example`:
   env
   OPENAI_API_KEY=your-key
   EMAIL_USER=you@gmail.com
   EMAIL_PASSWORD=your-app-password

2. Install dependencies:
   bash
   pip3 install langchain openai

3. Add the script to your crontab (inside LXC 101):
   bash
   crontab -e

   cron
   15 6 * * * python3 /root/monitoring/python/monitoring.py >> /var/log/monitoring-cron.log 2>&1

4. (Optional) Check the log:
   Full: cat /var/log/monitoring-cron.log
   Latest: tail -n 30 /var/log/monitoring-cron.log
   Real Time: tail -f /var/log/monitoring-cron.log

## 📡 Runtime

- LXC ID: `101`
- IP Address: `192.168.10.11`
- Hostname: `ct-monitoring`
- Python script path: `/root/monitoring/python/monitoring.py`

## 🔗 Related Projects

- [201-StartPage](https://github.com/angeres1/201-StartPage)
- [PSM-Squad](https://github.com/angeres1/PSM-Squad) – Core homelab documentation