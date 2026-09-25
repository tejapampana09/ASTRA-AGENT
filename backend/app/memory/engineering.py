from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.observability.logging import logger


@dataclass
class EngineeringDecision:
    """
    Long-term architectural and engineering decision or convention.
    Captures architectural rules, problematic modules, proven bug-fix patterns,
    and testing conventions.
    """
    decision_id: str
    repo_id: str
    category: str  # "architecture", "problematic_module", "proven_fix", "convention", "rule"
    subject: str   # e.g., "auth/jwt.py", "Pydantic Models", "Database Sessions"
    decision: str  # Detailed architectural rule or directive
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "repo_id": self.repo_id,
            "category": self.category,
            "subject": self.subject,
            "decision": self.decision,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


class EngineeringMemoryStore:
    """
    Durable repository engineering memory store for Phase 3.
    Persists architectural decisions, problematic modules, and engineering rules
    across tasks and process restarts.
    """

    def __init__(self, db_session_factory=None):
        if db_session_factory is None:
            try:
                from app.database.session import get_sync_session_factory
                self._session_factory = get_sync_session_factory()
            except Exception:
                self._session_factory = None
        else:
            self._session_factory = db_session_factory

        # Working cache: repo_id -> List[EngineeringDecision]
        self._decisions: Dict[str, List[EngineeringDecision]] = {}

    def record_decision(
        self,
        repo_id: str,
        category: str,
        subject: str,
        decision: str,
        evidence: Optional[Dict[str, Any]] = None,
        decision_id: Optional[str] = None,
    ) -> EngineeringDecision:
        """Records an engineering decision to working memory and database."""
        d_id = decision_id or f"dec-{repo_id}-{category[:4]}-{abs(hash(subject)) % 100000}"
        item = EngineeringDecision(
            decision_id=d_id,
            repo_id=repo_id,
            category=category,
            subject=subject,
            decision=decision,
            evidence=evidence or {},
        )

        if repo_id not in self._decisions:
            self._decisions[repo_id] = []
        self._decisions[repo_id].append(item)

        if self._session_factory:
            try:
                from app.database.models import EngineeringDecisionRecord
                with self._session_factory() as session:
                    rec = EngineeringDecisionRecord(
                        id=d_id,
                        repo_id=repo_id,
                        category=category,
                        subject=subject,
                        decision=decision,
                        evidence=evidence or {},
                    )
                    session.merge(rec)
                    session.commit()
            except Exception as e:
                logger.warning(f"Could not persist engineering decision to DB: {e}")

        logger.info(f"Recorded engineering decision [{category.upper()}] for {repo_id}: '{subject}'")
        return item

    def get_decisions(
        self,
        repo_id: str,
        category: Optional[str] = None
    ) -> List[EngineeringDecision]:
        """Returns all decisions for a repo, fetching from DB if not yet loaded."""
        items = list(self._decisions.get(repo_id, []))

        if self._session_factory:
            try:
                from app.database.models import EngineeringDecisionRecord
                from sqlalchemy import select
                with self._session_factory() as session:
                    query = select(EngineeringDecisionRecord).filter_by(repo_id=repo_id)
                    if category:
                        query = query.filter_by(category=category)
                    records = session.execute(query).scalars().all()

                    existing_ids = {d.decision_id for d in items}
                    for rec in records:
                        if rec.id not in existing_ids:
                            dec_obj = EngineeringDecision(
                                decision_id=rec.id,
                                repo_id=rec.repo_id,
                                category=rec.category,
                                subject=rec.subject,
                                decision=rec.decision,
                                evidence=rec.evidence or {},
                                timestamp=rec.created_at.isoformat() if rec.created_at else ""
                            )
                            items.append(dec_obj)
                            existing_ids.add(rec.id)
            except Exception as e:
                logger.debug(f"Engineering decision DB fallback: {e}")

        if category:
            return [d for d in items if d.category == category]
        return items

    def find_relevant_decisions(
        self,
        repo_id: str,
        target_files: Optional[List[str]] = None,
        goal: str = "",
        top_k: int = 5
    ) -> List[EngineeringDecision]:
        """Finds engineering decisions matching the target files or goal keywords."""
        all_decs = self.get_decisions(repo_id)
        if not all_decs:
            return []

        target_set = set(f.lower() for f in (target_files or []))
        goal_tokens = set(re.findall(r"\w+", goal.lower()))

        scored = []
        for dec in all_decs:
            score = 0.0
            subj_lower = dec.subject.lower()
            dec_text_lower = dec.decision.lower()

            # Subject matches target files
            for tf in target_set:
                if tf in subj_lower or subj_lower in tf:
                    score += 5.0

            # Goal keywords overlap with subject or decision text
            for tok in goal_tokens:
                if len(tok) > 3:
                    if tok in subj_lower:
                        score += 3.0
                    if tok in dec_text_lower:
                        score += 1.0

            # Problematic modules and conventions get slight baseline boost for awareness
            if dec.category in ["problematic_module", "convention", "rule"]:
                score += 1.0

            if score > 0:
                scored.append((dec, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [d for d, _ in scored[:top_k]]

    def format_decisions_for_prompt(self, decisions: List[EngineeringDecision]) -> str:
        """Formats engineering decisions and rules into markdown prompt context."""
        if not decisions:
            return "No previous engineering decisions or repository-specific rules recorded."

        lines = ["### Repository Engineering Decisions & Architectural Rules"]
        for idx, d in enumerate(decisions, 1):
            category_badge = d.category.replace("_", " ").upper()
            lines.append(f"\n{idx}. **[{category_badge}] {d.subject}**")
            lines.append(f"   - Rule/Decision: {d.decision}")
            if d.evidence and isinstance(d.evidence, dict):
                evidence_notes = d.evidence.get("notes") or d.evidence.get("rationale")
                if evidence_notes:
                    lines.append(f"   - Rationale: {evidence_notes}")

        return "\n".join(lines)


# Global singleton instance
_engineering_memory_store: Optional[EngineeringMemoryStore] = None


def get_engineering_memory_store() -> EngineeringMemoryStore:
    global _engineering_memory_store
    if _engineering_memory_store is None:
        _engineering_memory_store = EngineeringMemoryStore()
    return _engineering_memory_store


def set_engineering_memory_store(store: EngineeringMemoryStore) -> None:
    global _engineering_memory_store
    _engineering_memory_store = store
