# bot/nlp_engine.py
# Advanced NLP Engine for Teams Bot + CrewAI

import re
from rapidfuzz import fuzz
from bot.knowledge_base import load_knowledge_base

INTENT_PATTERNS = {
    "instance_recommendation": ["recommend ec2", "suggest ec2", "best ec2 type", "small instance", "test server"],
    "knowledge_query": ["what is", "explain", "define", "tell me about", "how does"],
}

SYNONYM_MAP = {
    "spin up ec2": "launch ec2",
    "new instance": "create ec2",
    "new s3": "create bucket",
    "create s3": "create bucket",
    "make bucket": "create bucket",
    "bucket create": "create bucket",
    "start ec2": "launch ec2",
    "terminate ec2": "delete instance"
}

def normalize_message(message):
    message = message.lower().strip()
    for key, value in SYNONYM_MAP.items():
        if key in message:
            message = message.replace(key, value)
    return message

def detect_intent(user_message):
    user_message = normalize_message(user_message)
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            score = fuzz.partial_ratio(user_message, pattern)
            if score > 85:
                return intent
    return None

def recommend_instance(user_message):
    if any(word in user_message for word in ["test", "dev", "practice", "demo"]):
        return "🖥️ For test or demo environments, I recommend **t3.micro** (low-cost, free tier eligible)."
    if any(word in user_message for word in ["production", "heavy", "enterprise"]):
        return "💪 For production workloads, consider **m5.large** or **c6a.large** depending on CPU/memory needs."
    return "💡 Common instance types: t3.micro (test), t3.medium (dev), m5.large (prod)."

class NLPEngine:

    def __init__(self):
        self.aws_services, self.instance_recommendations, self.knowledge_faq = load_knowledge_base()
        self.intent_patterns = {
            "create_instance": [r"\blaunch.*instance\b", r"\bcreate.*server\b", r"\bspin up.*ec2\b", r"\bnew.*ec2\b"],
            "create_bucket": [r"\bcreate.*bucket\b", r"\bnew.*s3\b"],
            "create_vpc": [r"\bcreate.*vpc\b", r"\bbuild.*vpc\b", r"\bsetup.*vpc\b"],
            "create_user": [r"\bcreate.*user\b", r"\bnew.*iam user\b"],
            "knowledge_query": [r"\bwhat is\b", r"\bexplain\b", r"\bhow does\b", r"\bwhat does\b"],
            "instance_recommendation": [r"\bneed.*instance\b", r"\bthinking.*instance\b", r"\bplan.*test\b", r"\brecommend.*instance\b"]
        }

    def detect_intent(self, text):
        text = text.lower()
        for intent, patterns in self.intent_patterns.items():
            for pat in patterns:
                if re.search(pat, text):
                    return intent
        return self.fuzzy_intent_match(text)

    def knowledge_lookup(self, text):
        text = text.lower()

        # ✅ 1️⃣ Check aws_services
        for keyword, description in self.aws_services.items():
            if keyword in text:
                return description

        # ✅ 2️⃣ Check instance_recommendations
        for keyword, suggestion in self.instance_recommendations.items():
            if keyword in text:
                return suggestion

        # ✅ 3️⃣ Check knowledge_faq exact match
        for item in self.knowledge_faq:
            if item["question"].lower() == text:
                return item["answer"]

        # ✅ 4️⃣ Check partial match on knowledge_faq
        for item in self.knowledge_faq:
            if any(word in text for word in item["question"].lower().split()):
                return item["answer"]

        return None

    def recommend_instance(self, text):
        for keyword, suggestion in self.instance_recommendations.items():
            if keyword in text.lower():
                return suggestion
        return None

    def fuzzy_intent_match(self, text):
        candidates = [
            "create instance", "launch ec2", "create s3 bucket", "create vpc",
            "create user", "iam user", "instance recommendation", "help",
            "what is", "explain"
        ]
        best_score = 0
        best_match = None
        for phrase in candidates:
            score = fuzz.partial_ratio(text.lower(), phrase.lower())
            if score > best_score:
                best_score = score
                best_match = phrase

        if best_score >= 75:
            if "instance" in best_match and "launch" in best_match:
                return "create_instance"
            if "bucket" in best_match:
                return "create_bucket"
            if "vpc" in best_match:
                return "create_vpc"
            if "user" in best_match:
                return "create_user"
            if "instance recommendation" in best_match:
                return "instance_recommendation"
            if "what" in best_match or "explain" in best_match:
                return "knowledge_query"
        return None

# ✅ Singleton instance
nlp_engine = NLPEngine()
