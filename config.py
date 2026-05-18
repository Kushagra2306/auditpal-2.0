"""AuditPal Configuration"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "AuditPal"
    app_description: str = "Your AI-powered accounting document assistant"

    # Paths
    base_dir: Path = Path(__file__).parent
    data_dir: Path = base_dir / "data"
    credentials_dir: Path = data_dir / "credentials"

    # NotebookLM settings
    max_file_size_mb: int = 50
    supported_extensions: list = [".pdf", ".txt", ".md", ".docx", ".xlsx", ".csv"]

    # Market-test rollout (set via env vars / Streamlit Cloud secrets)
    access_password: str = ""          # ACCESS_PASSWORD: shared gate; empty = no gate
    demo_notebook_ids: str = ""        # DEMO_NOTEBOOK_IDS: comma-separated pool ids
    feedback_form_url: str = ""        # FEEDBACK_FORM_URL: external feedback link
    lock_to_demo: bool = True          # LOCK_TO_DEMO: false = unlocked owner mode
    allow_name_fallback: bool = False  # ALLOW_NAME_FALLBACK: hash-by-name (may collide)

    def get_demo_notebook_ids(self) -> list:
        """Parse demo_notebook_ids into an ordered list of non-empty ids."""
        return [x.strip() for x in (self.demo_notebook_ids or "").split(",") if x.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Document categories for accountants
DOCUMENT_CATEGORIES = {
    "tax_forms": {
        "name": "Tax Forms",
        "icon": "📋",
        "description": "W-2s, 1099s, 1040s, and other tax documents"
    },
    "financial_statements": {
        "name": "Financial Statements",
        "icon": "📊",
        "description": "Balance sheets, income statements, cash flow statements"
    },
    "client_documents": {
        "name": "Client Documents",
        "icon": "👥",
        "description": "Client contracts, invoices, receipts"
    },
    "audit_reports": {
        "name": "Audit Reports",
        "icon": "🔍",
        "description": "Audit findings, compliance reports"
    },
    "other": {
        "name": "Other",
        "icon": "📁",
        "description": "Other documents"
    }
}

# Pre-built prompt templates for accountants
PROMPT_TEMPLATES = {
    "summarize": {
        "name": "📝 Summarize Document",
        "prompt": "Please provide a comprehensive summary of this document, highlighting key financial figures, dates, and important details.",
        "category": "Analysis"
    },
    "key_figures": {
        "name": "🔢 Extract Key Figures",
        "prompt": "List all the key financial figures from these documents including totals, subtotals, tax amounts, and any significant numbers. Present them in a clear format.",
        "category": "Analysis"
    },
    "discrepancies": {
        "name": "⚠️ Find Discrepancies",
        "prompt": "Analyze these documents for any discrepancies, inconsistencies, or potential errors. Flag anything that doesn't add up or seems unusual.",
        "category": "Audit"
    },
    "compare": {
        "name": "🔄 Compare Documents",
        "prompt": "Compare the documents and highlight the key differences, changes, or trends between them.",
        "category": "Analysis"
    },
    "red_flags": {
        "name": "🚩 Identify Red Flags",
        "prompt": "Review these documents for potential red flags, compliance issues, or areas that may need further investigation from an accounting perspective.",
        "category": "Audit"
    },
    "tax_summary": {
        "name": "💰 Tax Summary",
        "prompt": "Provide a tax summary including total income, deductions, credits, and tax liability based on the documents.",
        "category": "Tax"
    },
    "compliance_check": {
        "name": "✅ Compliance Check",
        "prompt": "Check these documents for compliance with standard accounting practices and flag any potential issues.",
        "category": "Audit"
    },
    "timeline": {
        "name": "📅 Create Timeline",
        "prompt": "Create a chronological timeline of all transactions, events, and important dates mentioned in the documents.",
        "category": "Analysis"
    }
}


def get_settings() -> Settings:
    """Get application settings."""
    settings = Settings()
    # Ensure directories exist
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.credentials_dir.mkdir(parents=True, exist_ok=True)
    return settings
