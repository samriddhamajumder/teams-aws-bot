import yaml
import os
import logging

logger = logging.getLogger(__name__)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(BASE_DIR, "knowledge_base.yaml")

def load_knowledge_base():
    if not os.path.exists(KB_PATH):
        logger.warning(f"⚠️ Knowledge base file not found at {KB_PATH}. Continuing without it.")
        return {}, {}, []
    with open(KB_PATH, "r") as f:
        data = yaml.safe_load(f)
        logger.info("✅ Loaded knowledge base file successfully.")
        return data["aws_services"], data["instance_recommendations"], data.get("knowledge_faq", [])
