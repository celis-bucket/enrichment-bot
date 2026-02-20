"""
LLM Category Classification Tool

Purpose: Classify an e-commerce company into one of 23 fixed categories
         using Claude 3.5 Sonnet via the Anthropic API with tool_use.
Inputs: domain, site metadata (title/description/H1), product titles, IG bio
Outputs: {success, data: {category, confidence, evidence}, error}
Dependencies: anthropic SDK, python-dotenv
"""

import os
import json
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv

load_dotenv()

ALLOWED_CATEGORIES = [
    "Accesorios",
    "Alimentos",
    "Alimentos refrigerados",
    "Autopartes",
    "Bebidas",
    "Cosmeticos-belleza",
    "Deporte",
    "Electrónicos",
    "Farmacéutica",
    "Hogar",
    "Infantiles y Bebés",
    "Joyeria/Bisuteria",
    "Juguetes",
    "Juguetes Sexuales",
    "Libros",
    "Mascotas",
    "Papeleria",
    "Ropa",
    "Salud y Bienestar",
    "Suplementos",
    "Tecnología",
    "Textil Hogar",
    "Zapatos",
]

MODEL = "claude-sonnet-4-5-20250929"

SYSTEM_PROMPT = """You are a product category classifier for Latin American e-commerce companies.
You will receive information about a company (domain, page metadata, product samples, and social media info).
You must classify it into EXACTLY ONE category from the provided list.
Also extract the company's commercial brand name (not the domain name).
Always call the classify_category tool with your answer. Pick the single best category even if uncertain."""

CLASSIFICATION_TOOL = {
    "name": "classify_category",
    "description": "Submit the category classification for this e-commerce company.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ALLOWED_CATEGORIES,
                "description": "The single best category for this company.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in the classification (0=guess, 1=certain).",
            },
            "evidence": {
                "type": "string",
                "description": "Brief explanation of what signals led to this classification (max 100 chars).",
            },
            "company_name": {
                "type": "string",
                "description": "The commercial brand/company name (not the domain). E.g. 'Armatura', 'Beauty Boost', 'Medipiel'.",
            },
        },
        "required": ["category", "confidence", "evidence", "company_name"],
    },
}


def classify_category(
    domain: str,
    meta_title: Optional[str] = None,
    meta_description: Optional[str] = None,
    h1_text: Optional[str] = None,
    product_titles: Optional[List[str]] = None,
    ig_bio: Optional[str] = None,
    ig_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify a company into one of 23 e-commerce categories using Claude.

    Returns:
        {success: bool, data: {category, confidence, evidence}, error: str|None}
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "success": False,
            "data": {},
            "error": "ANTHROPIC_API_KEY not set in environment",
        }

    try:
        import anthropic
    except ImportError:
        return {
            "success": False,
            "data": {},
            "error": "anthropic package not installed (pip install anthropic)",
        }

    # Build user message with available signals
    parts = [f"Domain: {domain}"]
    if meta_title:
        parts.append(f"Page title: {meta_title}")
    if meta_description:
        parts.append(f"Meta description: {meta_description}")
    if h1_text:
        parts.append(f"Main heading: {h1_text}")
    if product_titles:
        sample = product_titles[:20]
        parts.append(f"Sample products ({len(sample)}): {', '.join(sample)}")
    if ig_name:
        parts.append(f"Instagram name: {ig_name}")
    if ig_bio:
        parts.append(f"Instagram bio: {ig_bio}")

    user_message = "\n".join(parts)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            tools=[CLASSIFICATION_TOOL],
            tool_choice={"type": "tool", "name": "classify_category"},
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract tool_use block
        for block in response.content:
            if block.type == "tool_use" and block.name == "classify_category":
                result = block.input
                category = result.get("category", "")
                confidence = result.get("confidence", 0)
                evidence = result.get("evidence", "")

                # Validate category
                if category not in ALLOWED_CATEGORIES:
                    return {
                        "success": False,
                        "data": {"category": "", "confidence": 0, "evidence": ""},
                        "error": f"LLM returned invalid category: '{category}'",
                    }

                company_name = result.get("company_name", "")

                return {
                    "success": True,
                    "data": {
                        "category": category,
                        "confidence": round(confidence, 2),
                        "evidence": evidence[:200],
                        "company_name": company_name,
                    },
                    "error": None,
                }

        return {
            "success": False,
            "data": {},
            "error": "No tool_use block in LLM response",
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Anthropic API error: {str(e)}",
        }
