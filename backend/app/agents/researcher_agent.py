# app/agents/researcher_agent.py
"""
Researcher Agent - Adaptive Information Gathering with LLM Reasoning

Implements Dewey-style scaffolding: learns optimal question-answering sequences
through multi-turn communication with Policy Agent.

Core Responsibilities:
1. Answer the critical questions about the return using LLM reasoning
2. Validate answers through Policy Agent communication
3. Refine answers based on policy feedback
4. Track confidence and validation status

Future RL Enhancement:
- Policy gradient learning for optimal question sequencing
- Adaptive information gathering based on customer tier
- Transfer learning across product categories
"""
from __future__ import annotations
from datetime import datetime
import json
import logging
import os
import re
from typing import Any

import litellm
from app.config import get_settings
from app.services.item_lookup import lookup_item_by_sk
from app.services.store_sales_lookup import (
    lookup_purchase_date_by_item_and_email,
    lookup_store_sales_by_customer_email,
)

logger = logging.getLogger("agents.researcher")
settings = get_settings()

# LiteLLM model for reasoning
LLM_MODEL = "gpt-4o-mini"

# System prompt for the Researcher Agent's LLM reasoning
RESEARCHER_SYSTEM_PROMPT = """You are an expert Walmart's customer support researcher analyzing product returns.

Your job is to reason through a specific question about a return using the available context.

You must provide:
1. A clear, specific answer to the question
2. A confidence score (0.0 to 1.0) for your answer
3. Brief reasoning explaining how you arrived at the answer

Respond with ONLY a valid JSON object - no markdown, no preamble:
{
  "answer": "<your specific answer to the question>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explaining your reasoning>"
}

Guidelines:
- If the context doesn't contain enough information, say "Unknown - requires [what's needed]" and set confidence low (0.2-0.4)
- If you can infer from available context, state your inference clearly and set confidence medium (0.5-0.7)
- If the context directly provides the answer, state it confidently (0.8-1.0)
- Always be specific - avoid vague answers like "it depends" or "maybe"
"""


class ResearcherAgent:
    """
    Multi-agent researcher that gathers return information through
    iterative communication with Policy Agent using LLM reasoning.
    """
    
    # The critical questions every return must answer
    CRITICAL_QUESTIONS = [
        {
            "id": 1,
            "question": "Has the customer provided a valid receipt, order number, or payment transcript for the returned item?",
            "key": "proof_of_purchase",
            "context_keys": ["item_sk", "packaging_condition"],
        },
        {
            "id": 2,
            "question": "Was the item 'Purchased/Sold/Shipped from a authorized Walmart Store' or a 'Marketplace' seller?",
            "key": "seller_type",
            "context_keys": ["item_sk"],
        },
        {
            "id": 3,
            "question": "What is the specific purchase or delivery date for the returned item?",
            "key": "purchase_date",
            "context_keys": ["item_sk"],
        },
        {
            "id": 4,
            "question": "What is the specific category for the returned item?",
            "key": "item_category",
            "context_keys": ["item_sk"],
        },
        {
            "id": 5,
            "question": "Can the employee visually confirm the returned package is in the original packaging and the receipt shown to customer service is authentic?",
            "key": "visual_authenticity",
            "context_keys": ["packaging_condition", "item_sk"],
        },
        {
            "id": 6,
            "question": "Was the returned item sent by mail or returned in-store?",
            "key": "return_channel",
            "context_keys": ["item_sk"],
        },
        {
            "id": 7,
            "question": "Why is the customer returning the item?",
            "key": "return_reason",
            "context_keys": ["packaging_condition", "packaging_factor"],
        }
    ]
    
    def __init__(self):
        self.communication_history = []

    def _make_source_check(
        self,
        source_name: str,
        status: str,
        exact_issue: str,
        evidence: str = "",
        confidence: float = 0.0,
        source_ref: str = "",
    ) -> dict[str, Any]:
        return {
            "source_name": source_name,
            "status": status,
            "exact_issue": exact_issue,
            "evidence": evidence,
            "confidence": max(0.0, min(1.0, float(confidence))),
            "source_ref": source_ref,
            "compliant": status == "compliant",
        }

    def _aggregate_exact_issue(self, source_checks: list[dict[str, Any]]) -> str:
        issues = [
            f"{check['source_name']}: {check['exact_issue']}"
            for check in source_checks
            if check.get("status") in ("deviation", "error", "missing") and check.get("exact_issue")
        ]
        if issues:
            return " | ".join(issues)
        return "No source deviations detected."

    def _normalize_follow_up_answers(
        self,
        follow_up_answers: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}
        if not follow_up_answers:
            return normalized

        if isinstance(follow_up_answers, dict):
            for key, value in follow_up_answers.items():
                if value is not None:
                    normalized[str(key)] = str(value).strip()
            return normalized

        for entry in follow_up_answers:
            if not isinstance(entry, dict):
                continue
            answer = str(entry.get("answer", "")).strip()
            if not answer:
                continue
            if entry.get("key") is not None:
                normalized[str(entry["key"])] = answer
            if entry.get("question_id") is not None:
                normalized[str(entry["question_id"])] = answer
            if entry.get("question"):
                normalized[str(entry["question"])] = answer
        return normalized

    def _normalize_text(self, text: str | None) -> str:
        return re.sub(r"\s+", " ", (text or "").strip()).lower()

    def _extract_date_phrase(self, remarks: str) -> str:
        if not remarks:
            return ""

        date_patterns = [
            r"\b(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{2,4})?\b",
            r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\.?(?:,\s*\d{2,4})?\b",
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, remarks, flags=re.IGNORECASE)
            if match:
                return match.group(0)

        relative_patterns = [
            "today",
            "yesterday",
            "last week",
            "last month",
            "this week",
            "this month",
            "earlier this year",
            "a few days ago",
            "recently",
            "this morning",
            "tonight",
            "last night",
        ]
        remarks_lower = remarks.lower()
        for phrase in relative_patterns:
            if phrase in remarks_lower:
                return phrase
        return ""

    def _normalize_date_fragment(self, fragment: str) -> dict[str, Any] | None:
        text = re.sub(r"\s+", " ", (fragment or "").strip())
        if not text:
            return None

        relative_phrases = [
            "today",
            "yesterday",
            "last week",
            "last month",
            "this week",
            "this month",
            "earlier this year",
            "a few days ago",
            "recently",
            "this morning",
            "tonight",
            "last night",
        ]
        lowered = text.lower()
        for phrase in relative_phrases:
            if phrase in lowered:
                return {
                    "raw_text": text,
                    "date_provided": True,
                    "normalized_date": None,
                    "parse_status": "relative",
                    "source_format": "relative_reference",
                    "reasoning": (
                        "Customer provided a date reference, but it is relative and "
                        "needs an exact calendar date before Snowflake validation."
                    ),
                }

        cleaned = text
        cleaned = re.sub(r"(?i)\b(of)\b", " ", cleaned)
        cleaned = re.sub(r"(?i)(\d{1,2})(st|nd|rd|th)\b", r"\1", cleaned)
        cleaned = cleaned.replace(",", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        def _parse_with_dateutil(value: str, dayfirst: bool = False, yearfirst: bool = False) -> datetime | None:
            try:
                from dateutil import parser as date_parser

                return date_parser.parse(
                    value,
                    fuzzy=True,
                    dayfirst=dayfirst,
                    yearfirst=yearfirst,
                )
            except Exception:
                return None

        parsed = None
        source_format = ""

        iso_match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})", cleaned)
        if iso_match:
            try:
                parsed = datetime(
                    int(iso_match.group("year")),
                    int(iso_match.group("month")),
                    int(iso_match.group("day")),
                )
                source_format = "iso"
            except ValueError:
                parsed = None

        if parsed is None:
            numeric_match = re.fullmatch(
                r"(?P<a>\d{1,4})[/-](?P<b>\d{1,2})[/-](?P<c>\d{1,4})",
                cleaned,
            )
            if numeric_match:
                first = numeric_match.group("a")
                third = numeric_match.group("c")
                if len(first) == 4:
                    parsed = _parse_with_dateutil(cleaned, yearfirst=True)
                    source_format = "numeric_year_first"
                elif len(third) == 4:
                    dayfirst = int(first) > 12 and int(numeric_match.group("b")) <= 12
                    parsed = _parse_with_dateutil(cleaned, dayfirst=dayfirst)
                    source_format = "numeric_slash_or_dash"
                else:
                    parsed = _parse_with_dateutil(cleaned)
                    source_format = "numeric_short_year"

        if parsed is None:
            parsed = _parse_with_dateutil(cleaned)
            if parsed is not None:
                source_format = "textual_or_fallback"

        if parsed is None:
            return {
                "raw_text": text,
                "date_provided": True,
                "normalized_date": None,
                "parse_status": "unparsed",
                "source_format": "unknown",
                "reasoning": (
                    "A date-like value was mentioned, but it could not be normalized "
                    "reliably into Snowflake's YYYY-MM-DD format."
                ),
            }

        return {
            "raw_text": text,
            "date_provided": True,
            "normalized_date": parsed.date().isoformat(),
            "parse_status": "normalized",
            "source_format": source_format or "parsed",
            "reasoning": (
                "Customer remarks include a date reference that has been normalized "
                "into Snowflake format."
            ),
        }

    def _extract_yes_no_confirmation(self, remarks: str) -> dict[str, Any] | None:
        normalized = self._normalize_text(remarks)
        if not normalized:
            return None

        negative_terms = [
            "not original packaging",
            "no original packaging",
            "opened package",
            "tampered",
            "fake receipt",
            "not authentic",
            "receipt is fake",
            "receipt is not authentic",
        ]
        positive_package_terms = [
            "original packaging",
            "sealed package",
            "unopened package",
            "untampered package",
        ]
        positive_receipt_terms = [
            "authentic receipt",
            "receipt is authentic",
            "valid receipt",
            "real receipt",
            "original receipt",
        ]

        if any(term in normalized for term in negative_terms):
            return {
                "answer": "No",
                "confidence": 0.85,
                "reasoning": "Customer remarks include a negative indicator for packaging authenticity or receipt authenticity.",
                "evidence": remarks.strip(),
            }

        if any(term in normalized for term in positive_package_terms) and any(
            term in normalized for term in positive_receipt_terms
        ):
            return {
                "answer": "Yes",
                "confidence": 0.84,
                "reasoning": "Customer remarks indicate original packaging and an authentic receipt.",
                "evidence": remarks.strip(),
            }

        return None

    def _extract_return_channel(self, remarks: str) -> dict[str, Any] | None:
        normalized = self._normalize_text(remarks)
        if not normalized:
            return None

        mail_terms = [
            "by mail",
            "mailed back",
            "return by mail",
            "ship it back",
            "shipped back",
            "mail return",
            "postal return",
        ]
        store_terms = [
            "in-store",
            "in store",
            "store return",
            "returned to store",
            "dropped off at store",
            "brought to store",
            "customer service desk",
        ]

        if any(term in normalized for term in mail_terms):
            return {
                "answer": "Mail",
                "confidence": 0.82,
                "reasoning": "Customer remarks indicate the return was handled by mail.",
                "evidence": remarks.strip(),
            }

        if any(term in normalized for term in store_terms):
            return {
                "answer": "In-store",
                "confidence": 0.82,
                "reasoning": "Customer remarks indicate the return was handled in-store.",
                "evidence": remarks.strip(),
            }

        return None

    def _extract_answer_from_remarks(
        self,
        q_spec: dict[str, Any],
        remarks: str,
        context: dict[str, Any],
        sales_history: dict[str, Any],
        sales_lookup: dict[str, Any],
        item_lookup: dict[str, Any],
    ) -> dict[str, Any] | None:
        remarks_clean = remarks.strip()
        if not remarks_clean:
            return None

        normalized = self._normalize_text(remarks_clean)
        q_key = q_spec["key"]

        if q_key == "seller_type":
            if any(term in normalized for term in ["marketplace", "third-party seller", "3rd party seller"]):
                return {
                    "answer": "Marketplace seller",
                    "confidence": 0.86,
                    "reasoning": "Customer remarks explicitly mention a marketplace/third-party seller.",
                    "evidence": remarks_clean,
                }
            if any(term in normalized for term in ["sold & shipped by walmart", "sold and shipped by walmart", "sold by walmart"]):
                return {
                    "answer": "Sold & Shipped by Walmart",
                    "confidence": 0.92,
                    "reasoning": "Customer remarks explicitly mention Walmart fulfillment.",
                    "evidence": remarks_clean,
                }

        elif q_key == "purchase_date":
            date_reference = self._normalize_date_fragment(self._extract_date_phrase(remarks_clean))
            if date_reference and date_reference.get("normalized_date"):
                return {
                    "answer": date_reference["normalized_date"],
                    "confidence": 0.91,
                    "reasoning": date_reference["reasoning"],
                    "evidence": remarks_clean,
                    "date_reference": date_reference,
                }
            if date_reference and date_reference.get("date_provided"):
                return {
                    "answer": date_reference["raw_text"],
                    "confidence": 0.55,
                    "reasoning": date_reference["reasoning"],
                    "evidence": remarks_clean,
                    "date_reference": date_reference,
                }

        elif q_key == "item_category":
            item_category = str(item_lookup.get("item_category", "")).strip()
            item_category_full = str(item_lookup.get("item_category_full", "")).strip()
            item_name = str(item_lookup.get("item_name", "")).strip()
            sales_category = ""
            if sales_history.get("rows"):
                first_row = sales_history["rows"][0]
                sales_category = str(first_row.get("item_category", "")).strip()

            inferred_category = item_category or item_category_full or sales_category
            if inferred_category:
                return {
                    "answer": inferred_category,
                    "confidence": 0.95,
                    "reasoning": "Item category was inferred directly from Snowflake item or sales records.",
                    "evidence": item_lookup.get("evidence", sales_history.get("evidence", "")) or remarks_clean,
                    "source": "snowflake",
                }
            if item_category and item_category.lower() in normalized:
                return {
                    "answer": item_category,
                    "confidence": 0.9,
                    "reasoning": "Customer remarks explicitly mention the item category.",
                    "evidence": remarks_clean,
                }
            if item_category_full and item_category_full.lower() in normalized:
                return {
                    "answer": item_category_full,
                    "confidence": 0.9,
                    "reasoning": "Customer remarks explicitly mention the item category.",
                    "evidence": remarks_clean,
                }
            if item_name and item_name.lower() in normalized:
                return {
                    "answer": item_category or item_category_full or item_name,
                    "confidence": 0.8,
                    "reasoning": "Customer remarks mention the product name tied to the item lookup.",
                    "evidence": remarks_clean,
                }

        elif q_key == "visual_authenticity":
            confirmation = self._extract_yes_no_confirmation(remarks_clean)
            if confirmation:
                return confirmation

        elif q_key == "return_channel":
            channel = self._extract_return_channel(remarks_clean)
            if channel:
                return channel

        elif q_key == "proof_of_purchase":
            if any(
                term in normalized
                for term in [
                    "receipt",
                    "order number",
                    "order no",
                    "order #",
                    "payment card",
                    "original payment card",
                    "invoice",
                    "proof of purchase",
                ]
            ):
                negative_terms = [
                    "no receipt",
                    "without receipt",
                    "don't have receipt",
                    "do not have receipt",
                    "no order number",
                    "no payment card",
                ]
                if any(term in normalized for term in negative_terms):
                    return {
                        "answer": "No, the customer indicated the required purchase proof is not available.",
                        "confidence": 0.84,
                        "reasoning": "Customer remarks explicitly state the required proof is missing.",
                        "evidence": remarks_clean,
                    }
                return {
                    "answer": "Yes, the receipt, order number, or original payment card is available and valid.",
                    "confidence": 0.9,
                    "reasoning": "Customer remarks explicitly confirm purchase proof availability.",
                    "evidence": remarks_clean,
                }

        elif q_key == "return_reason":
            reason_map = [
                ("damaged", "Item arrived damaged or packaging was damaged."),
                ("defective", "Item is defective."),
                ("wrong size", "Item is the wrong size."),
                ("wrong item", "Customer received the wrong item."),
                ("changed mind", "Customer changed their mind."),
                ("not needed", "Customer no longer needs the item."),
                ("late delivery", "Delivery arrived too late."),
                ("missing parts", "Item is missing parts."),
                ("broken", "Item is broken."),
                ("too small", "Item is too small."),
                ("too large", "Item is too large."),
            ]
            for phrase, answer in reason_map:
                if phrase in normalized:
                    return {
                        "answer": answer,
                        "confidence": 0.84,
                        "reasoning": "Customer remarks describe the return reason directly.",
                        "evidence": remarks_clean,
                    }

            if len(normalized) > 0:
                return {
                    "answer": remarks_clean,
                    "confidence": 0.55,
                    "reasoning": "Customer remarks contain a return explanation that can be used as the base reason.",
                    "evidence": remarks_clean,
                }

        return None

    def _analyze_customer_remarks(
        self,
        customer_remarks: str,
        sales_history: dict[str, Any],
        sales_lookup: dict[str, Any],
        item_lookup: dict[str, Any],
    ) -> dict[str, Any]:
        remarks = (customer_remarks or "").strip()
        analysis: dict[str, Any] = {
            "provided": bool(remarks),
            "summary": "",
            "raw_remarks": remarks,
            "answers_by_key": {},
            "date_mentions": [],
            "covered_questions": [],
            "missing_questions": [],
            "follow_up_questions": [],
            "coverage": {"answered": 0, "missing": len(self.CRITICAL_QUESTIONS)},
        }

        if not remarks:
            analysis["summary"] = "No customer remarks were provided."
            analysis["missing_questions"] = [
                {
                    "question_id": q["id"],
                    "question": q["question"],
                    "key": q["key"],
                    "needed": True,
                    "reason": "No customer remarks provided.",
                }
                for q in self.CRITICAL_QUESTIONS
            ]
            analysis["follow_up_questions"] = [
                {
                    "question_id": q["id"],
                    "question": q["question"],
                    "key": q["key"],
                    "reason": "No customer remarks provided.",
                }
                for q in self.CRITICAL_QUESTIONS
            ]
            return analysis

        date_reference = self._normalize_date_fragment(self._extract_date_phrase(remarks))
        if date_reference:
            analysis["date_mentions"].append(date_reference)
            if date_reference.get("normalized_date"):
                analysis["summary"] = (
                    f"Customer remarks include a date reference normalized to "
                    f"{date_reference['normalized_date']}."
                )
            else:
                analysis["summary"] = (
                    "Customer remarks include a date reference, but it needs a more "
                    "exact calendar value for Snowflake validation."
                )

        for q_spec in self.CRITICAL_QUESTIONS:
            extracted = self._extract_answer_from_remarks(
                q_spec=q_spec,
                remarks=remarks,
                context={},
                sales_history=sales_history,
                sales_lookup=sales_lookup,
                item_lookup=item_lookup,
            )
            if extracted:
                answer_source = extracted.get("source", "customer_remarks")
                analysis["answers_by_key"][q_spec["key"]] = {
                    **extracted,
                    "question_id": q_spec["id"],
                    "question": q_spec["question"],
                    "answer_source": answer_source,
                }
                analysis["covered_questions"].append(
                    {
                        "question_id": q_spec["id"],
                        "question": q_spec["question"],
                        "answer": extracted["answer"],
                        "answer_source": answer_source,
                    }
                )
            else:
                analysis["missing_questions"].append(
                    {
                        "question_id": q_spec["id"],
                        "question": q_spec["question"],
                        "key": q_spec["key"],
                        "needed": True,
                        "reason": "Customer remarks did not provide enough information.",
                    }
                )
                analysis["follow_up_questions"].append(
                    {
                        "question_id": q_spec["id"],
                        "question": q_spec["question"],
                        "key": q_spec["key"],
                        "reason": "Customer remarks did not provide enough information.",
                    }
                )

        analysis["coverage"] = {
            "answered": len(analysis["covered_questions"]),
            "missing": len(analysis["missing_questions"]),
        }
        if analysis["covered_questions"]:
            answered_names = ", ".join(
                f"Q{item['question_id']}" for item in analysis["covered_questions"]
            )
        else:
            answered_names = "none"
        analysis["summary"] = (
            f"Customer remarks covered {analysis['coverage']['answered']} "
            f"of {len(self.CRITICAL_QUESTIONS)} required questions ({answered_names})."
        )
        return analysis

    def _question_source_checks(
        self,
        q_key: str,
        remarks_answer: dict[str, Any] | None,
        sales_history: dict[str, Any],
        sales_lookup: dict[str, Any],
        item_lookup: dict[str, Any],
        return_reason: str,
        follow_up_answer: str,
        validation_result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []

        if remarks_answer:
            source_name = "SNOWFLAKE" if remarks_answer.get("source") == "snowflake" else "CUSTOMER_REMARKS"
            source_ref = "Snowflake.ITEM/STORE_SALES" if source_name == "SNOWFLAKE" else "request.customer_remarks"
            checks.append(
                self._make_source_check(
                    source_name=source_name,
                    status="compliant",
                    exact_issue=(
                        "Item category was inferred from Snowflake item or sales records."
                        if source_name == "SNOWFLAKE"
                        else "Customer remarks supplied the base answer for this question."
                    ),
                    evidence=remarks_answer.get("evidence", remarks_answer.get("answer", "")),
                    confidence=remarks_answer.get("confidence", 0.0),
                    source_ref=source_ref,
                )
            )

        if q_key == "seller_type":
            checks.append(
                self._make_source_check(
                    source_name=sales_history.get("source_name", "STORE_SALES"),
                    status=sales_history.get("compliance_status", "missing"),
                    exact_issue=(
                        "Seller channel is inferred from the customer/item sale history."
                        if sales_history.get("valid")
                        else sales_history.get("exact_issue", sales_history.get("note", ""))
                    ),
                    evidence=sales_history.get("evidence", sales_history.get("note", "")),
                    confidence=sales_history.get("confidence", 0.0),
                    source_ref="Snowflake.STORE_SALES",
                )
            )
        if q_key == "purchase_date":
            checks.append(
                self._make_source_check(
                    source_name=sales_history.get("source_name", "STORE_SALES"),
                    status=sales_history.get("compliance_status", "missing"),
                    exact_issue=sales_history.get("exact_issue", sales_history.get("note", "")),
                    evidence=sales_history.get("note", ""),
                    confidence=sales_history.get("confidence", 0.0),
                    source_ref="Snowflake.STORE_SALES",
                )
            )
            checks.append(
                self._make_source_check(
                    source_name=sales_lookup.get("source_name", "STORE_SALES"),
                    status=sales_lookup.get("compliance_status", "missing"),
                    exact_issue=sales_lookup.get("exact_issue", sales_lookup.get("note", "")),
                    evidence=sales_lookup.get("evidence", sales_lookup.get("note", "")),
                    confidence=sales_lookup.get("confidence", 0.0),
                    source_ref="Snowflake.STORE_SALES",
                )
            )
        if q_key == "item_category":
            checks.append(
                self._make_source_check(
                    source_name=item_lookup.get("source_name", "ITEM"),
                    status=item_lookup.get("compliance_status", "missing"),
                    exact_issue=item_lookup.get("exact_issue", item_lookup.get("note", "")),
                    evidence=item_lookup.get("evidence", item_lookup.get("note", "")),
                    confidence=item_lookup.get("confidence", 0.0),
                    source_ref="Snowflake.ITEM",
                )
            )
        if q_key == "proof_of_purchase":
            checks.append(
                self._make_source_check(
                    source_name=sales_history.get("source_name", "STORE_SALES"),
                    status=sales_history.get("compliance_status", "missing"),
                    exact_issue=(
                        "Order history exists and supports proof-of-purchase availability."
                        if sales_history.get("valid")
                        else sales_history.get("exact_issue", sales_history.get("note", ""))
                    ),
                    evidence=sales_history.get("evidence", sales_history.get("note", "")),
                    confidence=sales_history.get("confidence", 0.0),
                    source_ref="Snowflake.STORE_SALES",
                )
            )
        if q_key == "return_reason":
            if return_reason.strip():
                checks.append(
                    self._make_source_check(
                        source_name="CUSTOMER_INPUT",
                        status="compliant",
                        exact_issue="Customer supplied a return reason in the request.",
                        evidence=return_reason.strip(),
                        confidence=0.9,
                        source_ref="request.return_reason",
                    )
                )
            else:
                checks.append(
                    self._make_source_check(
                        source_name="CUSTOMER_INPUT",
                        status="missing",
                        exact_issue="No return reason was supplied in the request.",
                        evidence="",
                        confidence=0.0,
                        source_ref="request.return_reason",
                    )
                )

        if follow_up_answer.strip():
            checks.append(
                self._make_source_check(
                    source_name="CUSTOMER_FOLLOW_UP",
                    status="compliant",
                    exact_issue="Customer follow-up answer supplied for this question.",
                    evidence=follow_up_answer.strip(),
                    confidence=0.88,
                    source_ref="request.follow_up_answers",
                )
            )
        elif q_key not in ("return_reason",) and not remarks_answer:
            checks.append(
                self._make_source_check(
                    source_name="CUSTOMER_FOLLOW_UP",
                    status="missing",
                    exact_issue="No follow-up answer was provided for this question.",
                    evidence="",
                    confidence=0.0,
                    source_ref="request.follow_up_answers",
                )
            )

        checks.append(
            self._make_source_check(
                source_name=validation_result.get("source_name", "POLICY"),
                status=validation_result.get(
                    "compliance_status",
                    "compliant" if validation_result.get("valid") else "deviation",
                ),
                exact_issue=validation_result.get("exact_issue", validation_result.get("note", "")),
                evidence=validation_result.get("evidence", ""),
                confidence=validation_result.get("confidence", 0.0),
                source_ref=validation_result.get("policy_ref", ""),
            )
        )

        return checks
        
    async def investigate_return(
        self, 
        item_context: dict[str, Any],
        policy_agent: Any,  # PolicyAgent instance
        customer_email: str | None = None,
        customer_remarks: str | None = None,
        follow_up_answers: list[dict[str, Any]] | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Main investigation loop: gather answers to all 5 questions
        through iterative communication with Policy Agent.
        
        Args:
            item_context: {item_sk, price, return_qty, packaging_condition, packaging_factor}
            policy_agent: PolicyAgent instance for validation
            
        Returns:
            {
                "questions": [QuestionAnswer],
                "exchanges": [ResearcherPolicyExchange],
                "assessment_complete": bool,
                "assessment_confidence": float
            }
        """
        logger.info("")
        logger.info("🔬 RESEARCHER AGENT: Beginning investigation")
        logger.info(f"   Context: Item SK {item_context['item_sk']}, "
                   f"Packaging: {item_context['packaging_condition']}")
        return_reason = (customer_remarks or item_context.get("customer_remarks") or item_context.get("return_reason", "")).strip()
        follow_up_answer_map = self._normalize_follow_up_answers(follow_up_answers)

        sales_history = {}
        sales_lookup = {}
        item_lookup = {}
        if customer_email:
            sales_history = lookup_store_sales_by_customer_email(customer_email)
            sales_lookup = lookup_purchase_date_by_item_and_email(
                item_sk=int(item_context["item_sk"]),
                customer_email=customer_email,
            )
            item_lookup = lookup_item_by_sk(int(item_context["item_sk"]))
            logger.info(
                "   STORE_SALES history: %s | %s",
                sales_history.get("valid"),
                sales_history.get("note"),
            )
            logger.info(
                "   STORE_SALES lookup: %s | %s",
                sales_lookup.get("valid"),
                sales_lookup.get("note"),
            )
            logger.info(
                "   ITEM lookup: %s | %s",
                item_lookup.get("valid"),
                item_lookup.get("note"),
            )
            if not sales_lookup.get("valid"):
                logger.info("   STORE_SALES exact issue: %s", sales_lookup.get("exact_issue") or sales_lookup.get("note"))

        resolved_context = {**item_context, **sales_history, **sales_lookup, **item_lookup}
        if customer_email:
            resolved_context["customer_email"] = customer_email
        if return_reason:
            resolved_context["customer_remarks"] = return_reason

        remarks_analysis = self._analyze_customer_remarks(
            customer_remarks=return_reason,
            sales_history=sales_history,
            sales_lookup=sales_lookup,
            item_lookup=item_lookup,
        )
        logger.info("   Customer remarks provided: %s", remarks_analysis.get("provided"))
        logger.info("   Customer remarks summary: %s", remarks_analysis.get("summary"))
        if remarks_analysis.get("follow_up_questions"):
            logger.info("   Follow-up questions needed: %s", len(remarks_analysis["follow_up_questions"]))
            for follow_up in remarks_analysis["follow_up_questions"]:
                logger.info("      - Q%s: %s", follow_up.get("question_id", "?"), follow_up.get("question", ""))
        if follow_up_answer_map:
            logger.info("   Follow-up answers provided: %s", len(follow_up_answer_map))
        awaiting_user_input = bool(remarks_analysis.get("follow_up_questions")) and not bool(follow_up_answer_map)
        
        questions_answered = []
        exchanges = []
        
        # ── Investigate each question sequentially ────────────────────────
        for q_spec in self.CRITICAL_QUESTIONS:
            logger.info("")
            logger.info(f"📋 Question {q_spec['id']}: {q_spec['question']}")
            
            # Step 1: Researcher uses LLM to formulate initial answer
            remarks_answer = remarks_analysis.get("answers_by_key", {}).get(q_spec["key"])
            follow_up_answer = (
                follow_up_answer_map.get(q_spec["key"])
                or follow_up_answer_map.get(str(q_spec["id"]))
                or follow_up_answer_map.get(q_spec["question"])
                or ""
            )
            if remarks_answer:
                initial_answer = {
                    "answer": remarks_answer["answer"],
                    "confidence": float(remarks_answer.get("confidence", 0.8)),
                    "reasoning": remarks_answer.get("reasoning", "Customer remarks supplied the answer."),
                }
            elif follow_up_answer:
                initial_answer = {
                    "answer": follow_up_answer,
                    "confidence": 0.82,
                    "reasoning": "Customer provided a follow-up answer for this question.",
                }
            elif q_spec["key"] == "purchase_date" and sales_lookup.get("valid"):
                initial_answer = {
                    "answer": sales_lookup.get("purchase_date", "Unknown"),
                    "confidence": float(sales_lookup.get("confidence", 0.9)),
                    "reasoning": sales_lookup.get(
                        "note",
                        "Confirmed through STORE_SALES lookup.",
                    ),
                }
            elif q_spec["key"] == "item_category" and item_lookup.get("valid"):
                initial_answer = {
                    "answer": item_lookup.get("item_category", "Unknown"),
                    "confidence": float(item_lookup.get("confidence", 0.9)),
                    "reasoning": item_lookup.get(
                        "note",
                        "Confirmed through ITEM lookup.",
                    ),
                }
            elif q_spec["key"] == "item_category" and sales_history.get("valid"):
                sales_rows = sales_history.get("rows", [])
                first_row = sales_rows[0] if sales_rows else {}
                inferred_category = first_row.get("item_category") or first_row.get("item_name")
                initial_answer = {
                    "answer": inferred_category or "Unknown",
                    "confidence": 0.9 if inferred_category else float(sales_history.get("confidence", 0.6)),
                    "reasoning": "Item category was inferred from Snowflake sales records.",
                }
            else:
                if awaiting_user_input:
                    initial_answer = {
                        "answer": "Pending customer input",
                        "confidence": 0.0,
                        "reasoning": "Awaiting a customer follow-up response for this question.",
                    }
                else:
                    initial_answer = await self._formulate_answer_llm(q_spec, resolved_context)
            logger.info(f"   Initial Answer: {initial_answer['answer']}")
            logger.info(f"   Initial Confidence: {initial_answer['confidence']:.2f}")
            logger.info(f"   Initial Reasoning: {initial_answer['reasoning']}")
            
            # Step 2: Ask Policy Agent to validate
            policy_query = self._build_policy_query(q_spec, initial_answer)
            logger.info(f"   Policy Query: {policy_query}")

            if initial_answer["answer"] == "Pending customer input":
                validation_result = {
                    "valid": False,
                    "compliance_status": "pending",
                    "exact_issue": "Awaiting customer follow-up answer before policy validation.",
                    "evidence": "",
                    "note": "Awaiting customer follow-up answer before policy validation.",
                    "confidence": 0.0,
                    "policy_ref": "pending",
                    "source_name": "CUSTOMER_FOLLOW_UP",
                    "retrieved_policies": [],
                }
            else:
                validation_result = await policy_agent.validate(
                    question=q_spec["question"],
                    proposed_answer=initial_answer["answer"],
                    query=policy_query,
                    context=resolved_context
                )
            
            logger.info(f"   Policy Validation: {validation_result['valid']}")
            if validation_result.get("note"):
                logger.info(f"   Validation Note: {validation_result['note']}")
            if validation_result.get("exact_issue"):
                logger.info(f"   Policy Exact Issue: {validation_result['exact_issue']}")

            source_checks = self._question_source_checks(
                q_key=q_spec["key"],
                remarks_answer=remarks_answer,
                sales_history=sales_history,
                sales_lookup=sales_lookup,
                item_lookup=item_lookup,
                return_reason=return_reason,
                follow_up_answer=follow_up_answer,
                validation_result=validation_result,
            )

            # Step 3: Researcher adjusts based on validation
            final_answer, final_confidence = self._adjust_answer(
                initial_answer,
                validation_result
            )

            logger.info(f"   ✓ Final Answer: {final_answer}")
            logger.info(f"   Final Confidence: {final_confidence:.2f}")
            logger.info(f"   Source Exact Issue: {self._aggregate_exact_issue(source_checks)}")

            if remarks_answer:
                answer_source = "customer_remarks"
                if q_spec["key"] == "item_category" and remarks_answer.get("source") == "snowflake":
                    answer_source = "snowflake"
            elif q_spec["key"] == "purchase_date" and sales_lookup.get("valid"):
                answer_source = "store_sales"
            elif q_spec["key"] == "item_category" and item_lookup.get("valid"):
                answer_source = "snowflake"
            elif q_spec["key"] == "item_category" and sales_history.get("valid"):
                answer_source = "snowflake"
            elif q_spec["key"] in ("visual_authenticity", "return_channel") and remarks_answer:
                answer_source = "customer_remarks"
            elif q_spec["key"] in ("seller_type", "proof_of_purchase") and sales_history.get("valid"):
                answer_source = "store_sales"
            elif initial_answer["answer"] == "Pending customer input":
                answer_source = "pending_user_input"
            else:
                answer_source = "llm"

            # Record the question-answer
            questions_answered.append({
                "question": q_spec["question"],
                "answer": final_answer,
                "confidence": final_confidence,
                "validated": all(
                    check["status"] in ("compliant", "insufficient_evidence")
                    for check in source_checks
                ),
                "validation_note": validation_result.get("note", ""),
                "exact_issue": self._aggregate_exact_issue(source_checks),
                "source_checks": source_checks,
                "answer_source": answer_source,
            })
            
            # Record the communication exchange
            exchanges.append({
                "question_id": q_spec["id"],
                "question": q_spec["question"],
                "researcher_answer": initial_answer["answer"],
                "policy_query": policy_query,
                "policy_validation": validation_result,
                "final_answer": final_answer,
                "confidence": final_confidence,
                "exact_issue": self._aggregate_exact_issue(source_checks),
                "source_checks": source_checks,
            })
        
        # ── Compute overall assessment ────────────────────────────────────
        all_validated = all(qa["validated"] for qa in questions_answered)
        avg_confidence = sum(qa["confidence"] for qa in questions_answered) / len(questions_answered)
        
        assessment_complete = all_validated and avg_confidence >= 0.7
        awaiting_follow_up = awaiting_user_input
        
        logger.info("")
        logger.info(f"🎯 INVESTIGATION COMPLETE")
        logger.info(f"   All Validated: {all_validated}")
        logger.info(f"   Avg Confidence: {avg_confidence:.2f}")
        logger.info(f"   Assessment Complete: {assessment_complete}")
        
        return {
            "questions": questions_answered,
            "exchanges": exchanges,
            "assessment_complete": assessment_complete,
            "assessment_confidence": avg_confidence,
            "sales_history": sales_history,
            "sales_validation": sales_lookup,
            "item_validation": item_lookup,
            "resolved_context": resolved_context,
            "remarks_analysis": remarks_analysis,
            "follow_up_questions": remarks_analysis.get("follow_up_questions", []),
            "awaiting_follow_up": awaiting_follow_up,
        }
    
    async def _formulate_answer_llm(
        self, 
        q_spec: dict, 
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Use LLM to formulate answer to a question based on available context.
        
        This is where RL will eventually optimize the prompting strategy.
        Currently uses standard LLM reasoning with temperature=0.2.
        """
        question = q_spec["question"]
        q_key = q_spec["key"]
        
        # Build context description for the LLM
        context_str = self._build_context_description(context, q_spec["context_keys"])
        
        # Build the user prompt
        user_prompt = f"""## Question to Answer:
{question}

## Available Context:
{context_str}

Analyze the context and provide your best answer to the question. Remember to include:
- answer: Your specific answer
- confidence: How confident you are (0.0 to 1.0)
- reasoning: One sentence explaining your logic

Respond with ONLY the JSON object."""
        
        try:
            # Call LLM via LiteLLM
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
            
            response = litellm.completion(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": RESEARCHER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,  # Low temp for consistent reasoning
                max_tokens=300,
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            # Parse JSON response
            cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
            result = json.loads(cleaned)
            
            # Validate schema
            if "answer" not in result or "confidence" not in result:
                raise ValueError("LLM response missing required fields")
            
            # Ensure confidence is in valid range
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            result.setdefault("reasoning", "LLM reasoning not provided")
            
            return result
            
        except Exception as exc:
            logger.warning(f"LLM call failed for question '{question}': {exc}")
            logger.info("Falling back to rule-based answer")
            
            # Fallback to rule-based if LLM fails
            return self._formulate_answer_fallback(q_spec, context)
    
    def _build_context_description(
        self, 
        context: dict[str, Any],
        relevant_keys: list[str]
    ) -> str:
        """Build a natural language description of available context."""
        desc_parts = []
        
        if "item_sk" in relevant_keys:
            desc_parts.append(f"- Item SK: {context.get('item_sk', 'Unknown')}")
        
        if "price" in relevant_keys or "price" in context:
            desc_parts.append(f"- Item Price: ${context.get('price', 0):.2f}")
        
        if "return_qty" in relevant_keys or "return_qty" in context:
            desc_parts.append(f"- Return Quantity: {context.get('return_qty', 1)} unit(s)")
        
        if "packaging_condition" in relevant_keys:
            pkg = context.get('packaging_condition', 'Unknown')
            desc_parts.append(f"- Packaging Condition: {pkg}")
        
        if "packaging_factor" in relevant_keys:
            factor = context.get('packaging_factor', 0)
            desc_parts.append(f"- Packaging Damage Factor: {factor:.2f} ({int(factor * 100)}% net loss)")
        
        # Add all context for completeness
        desc_parts.append("\n## Full Context Available:")
        for key, value in context.items():
            desc_parts.append(f"- {key}: {value}")
        
        return "\n".join(desc_parts)
    
    def _formulate_answer_fallback(
        self, 
        q_spec: dict, 
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Fallback rule-based logic when LLM fails.
        Same as original implementation.
        """
        q_key = q_spec["key"]
        
        # Question 1: Seller type
        if q_key == "seller_type":
            return {
                "answer": "Sold & Shipped by Walmart",
                "confidence": 0.7,
                "reasoning": "Default assumption for Item SK in TPC-DS schema"
            }
        
        # Question 2: Purchase/delivery date
        elif q_key == "purchase_date":
            return {
                "answer": "Unknown - requires customer input or order lookup",
                "confidence": 0.3,
                "reasoning": "Purchase date not provided in item context"
            }
        
        # Question 3: Item category
        elif q_key == "item_category":
            return {
                "answer": str(context.get("item_category", "Unknown - requires Snowflake ITEM or STORE_SALES lookup")),
                "confidence": 0.95 if context.get("item_category") else 0.4,
                "reasoning": "Item category is best inferred from Snowflake ITEM or STORE_SALES records."
            }

        elif q_key == "visual_authenticity":
            return {
                "answer": "No",
                "confidence": 0.4,
                "reasoning": "Visual authenticity cannot be confirmed from item context alone."
            }

        elif q_key == "return_channel":
            return {
                "answer": "Unknown - requires customer confirmation",
                "confidence": 0.3,
                "reasoning": "Return channel is not provided in item context."
            }

        # Question 4: Proof of purchase
        elif q_key == "proof_of_purchase":
            pkg = context.get("packaging_condition", "")
            if pkg in ["sealed", "intact"]:
                return {
                    "answer": "Likely available - packaging suggests recent purchase with intact materials",
                    "confidence": 0.6,
                    "reasoning": f"Packaging condition '{pkg}' suggests proof may be intact"
                }
            else:
                return {
                    "answer": "May not be available - damaged packaging suggests proof may be lost",
                    "confidence": 0.4,
                    "reasoning": f"Packaging condition '{pkg}' suggests proof may be compromised"
                }
        
        # Question 5: Return reason
        elif q_key == "return_reason":
            pkg = context.get("packaging_condition", "")
            factor = context.get("packaging_factor", 0)
            
            if pkg in ["destroyed", "heavy"]:
                return {
                    "answer": "Packaging damage during shipping - item potentially unusable",
                    "confidence": 0.8,
                    "reasoning": f"High packaging factor ({factor}) indicates severe damage"
                }
            elif pkg in ["moderate", "minor"]:
                return {
                    "answer": "Packaging shows damage - customer may be concerned about product integrity",
                    "confidence": 0.7,
                    "reasoning": f"Moderate packaging factor ({factor}) suggests concern"
                }
            else:
                return {
                    "answer": "Unknown - undamaged packaging suggests other reason (fit, preference, etc.)",
                    "confidence": 0.5,
                    "reasoning": "No damage signal from packaging assessment"
                }
        
        # Fallback
        return {
            "answer": "Unknown",
            "confidence": 0.0,
            "reasoning": "No logic implemented for this question"
        }
    
    def _build_policy_query(
        self, 
        q_spec: dict, 
        initial_answer: dict[str, Any]
    ) -> str:
        """
        Convert question + answer into a policy validation query.
        
        This query will be sent to Policy Agent for scrapling-based validation.
        """
        q_key = q_spec["key"]
        answer = initial_answer["answer"]
        
        # Build domain-specific query for policy lookup
        if q_key == "seller_type":
            return "walmart return policy marketplace seller"
        
        elif q_key == "purchase_date":
            return "walmart return policy time limit days"
        
        elif q_key == "item_category":
            return f"walmart return policy category {answer}"

        elif q_key == "visual_authenticity":
            return "walmart return policy original packaging receipt authenticity"

        elif q_key == "return_channel":
            return "walmart return policy mail in-store return method"

        elif q_key == "proof_of_purchase":
            return "walmart return policy receipt required"
        
        elif q_key == "return_reason":
            if "damage" in answer.lower():
                return "walmart return policy damaged item"
            else:
                return "walmart return policy general"
        
        return "walmart return policy"
    
    def _adjust_answer(
        self,
        initial_answer: dict[str, Any],
        validation_result: dict[str, Any]
    ) -> tuple[str, float]:
        """
        Adjust answer based on Policy Agent validation feedback.
        
        If validation passes -> use initial answer
        If validation fails -> adjust based on policy guidance
        """
        if validation_result["valid"]:
            # Policy confirms our answer
            return (
                initial_answer["answer"],
                min(1.0, initial_answer["confidence"] + 0.1)  # Boost confidence
            )
        else:
            return (initial_answer["answer"], initial_answer["confidence"] * 0.8)
