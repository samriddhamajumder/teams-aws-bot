# Tikogen — AI-Driven CloudOps Assistant

> Automate your AWS infrastructure through natural language inside Microsoft Teams.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-tikogen.com-2563EB?style=flat-square)](https://tikogen.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![AWS](https://img.shields.io/badge/AWS-Cloud-FF9900?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com)
[![Azure](https://img.shields.io/badge/Hosted-Azure-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)](https://azure.microsoft.com)
[![CrewAI](https://img.shields.io/badge/Orchestration-CrewAI-black?style=flat-square)](https://crewai.com)

---

## What is Tikogen?

Managing cloud infrastructure shouldn't require navigating IAM consoles, writing YAML, or opening tickets.

**Tikogen** is a CloudOps assistant that lives inside Microsoft Teams. Ask it to launch an EC2 instance, audit IAM roles, create a VPC, or manage S3 — and it gets it done. Instantly. Securely. In plain English.

No portal. No CLI. No delay.

---

## Features

| Capability | Description |
|---|---|
| 🖥️ **EC2 Provisioning** | Launch instances with default or custom configs via a single message |
| 🔐 **IAM Audit** | Inspect roles, policies, and access patterns on demand |
| 🌐 **VPC Creation** | Architect secure VPCs with subnets, NAT, and IGW automatically |
| 📦 **S3 Operations** | Create buckets, upload files, and manage access policies |

---

## Architecture

```
Microsoft Teams
      │
      ▼
  Bot Framework  ──►  NLP Intent Detection (LLaMA3 via Ollama)
      │
      ▼
  CrewAI Orchestration
      │
      ├──► aws_crew_tools/ec2_handler.py
      ├──► aws_crew_tools/iam_handler.py
      ├──► aws_crew_tools/vpc_handler.py
      └──► aws_crew_tools/s3_handler.py
                │
                ▼
           AWS SDK (boto3)
                │
                ▼
         AWS Infrastructure
```

---

## Tech Stack

- **LLM** — Ollama (LLaMA3) for local NLP intent detection
- **Orchestration** — CrewAI for multi-step agentic workflows
- **Bot Framework** — Microsoft Bot Framework with Adaptive Cards UI
- **Cloud Provider** — AWS (EC2, IAM, VPC, S3 via boto3)
- **Hosting** — Azure (production deployment)
- **Auth** — OAuth 2.0 secured
- **Language** — Python 3.10+

---

## Getting Started

### Prerequisites

- Python 3.10+
- Ollama installed and running locally
- AWS credentials configured (`~/.aws/credentials`)
- Microsoft Teams Bot registration (App ID + Password)
- Azure account for hosting (optional for local dev)

### Installation

```bash
# Clone the repo
git clone https://github.com/samriddhamajumder/teams-aws-bot.git
cd teams-aws-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in your credentials in .env
```

### Environment Variables

```env
MICROSOFT_APP_ID=your_teams_app_id
MICROSOFT_APP_PASSWORD=your_teams_app_password
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_DEFAULT_REGION=us-east-1
OLLAMA_BASE_URL=http://localhost:11434
```

### Run Locally

```bash
python app.py
```

---

## Usage Examples

Once connected to Teams, just type:

```
"Launch an EC2 instance, keep everything default"
"Audit my IAM roles and show unused permissions"
"Create a secure VPC with public and private subnets"
"List all S3 buckets and their access policies"
```

Tikogen detects intent, builds the workflow, executes securely against AWS, and responds with a structured Adaptive Card — all within Teams.

---

## Project Structure

```
teams-aws-bot/
├── app.py                  # Bot entrypoint
├── bot/                    # Teams bot logic & Adaptive Cards
├── aws_crew_tools/         # AWS operation handlers (EC2, IAM, VPC, S3)
├── crew_handler.py         # CrewAI orchestration layer
├── templates/              # Adaptive Card templates
├── requirements.txt
└── .env                    # Environment config (not committed)
```

---

## Live Demo

Visit **[tikogen.com](https://tikogen.com)** to explore features and request a private beta demo.

---

## Author

**Samriddha Majumder**
[LinkedIn](https://linkedin.com/in/samriddha-majumder) · [GitHub](https://github.com/samriddhamajumder)

---

> Built to make CloudOps feel human — and fast.
