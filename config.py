import os
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "secretary.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

PROJECTS_BASE = os.getenv("PROJECTS_BASE", os.path.expanduser("~/projects"))

# Example project configuration — replace with your own projects
PROJECTS = {
    "web-app": "Main web application, frontend and backend",
    "mobile-api": "Mobile app REST API and push notifications",
    "data-pipeline": "ETL pipelines, data warehouse, analytics",
    "infra": "Infrastructure, CI/CD, monitoring, deployments",
    "docs": "Documentation, blog posts, knowledge base",
}

CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.8
TASK_TIMEOUT_SECONDS = 300
