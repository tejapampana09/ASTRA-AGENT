from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.observability.logging import logger


@dataclass
class ImpactAnalysisReport:
    """
    Detailed report of code change impact analysis.
    Identifies all files, symbols, and tests that could be impacted by changing target files.
    """
    target_files: List[str]
    affected_files: List[str]
    affected_symbols: List[str]
    dependency_chain: Dict[str, List[str]]
    relevant_tests: List[str]
    blast_radius_score: float  # 0.0 (isolated) to 1.0 (repo-wide)
    risk_level: str            # "LOW", "MEDIUM", "HIGH"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_files": self.target_files,
            "affected_files": self.affected_files,
            "affected_symbols": self.affected_symbols,
            "dependency_chain": self.dependency_chain,
            "relevant_tests": self.relevant_tests,
            "blast_radius_score": round(self.blast_radius_score, 3),
            "risk_level": self.risk_level,
        }


class ChangeImpactAnalyzer:
    """
    Autonomous Change Impact Analyzer for Phase 3.
    Uses Python AST parsing to inspect import graphs, symbol definitions,
    and call dependencies across the codebase before changes are made.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def analyze_impact(
        self,
        target_files: List[str],
        all_repo_files: Optional[List[str]] = None
    ) -> ImpactAnalysisReport:
        """
        Analyzes the potential impact of modifying `target_files`.
        Traverses:
        Target Files -> Exported Symbols -> Importers -> Reverse Dependencies -> Relevant Tests.
        """
        norm_targets = [f.replace("\\", "/").lstrip("./") for f in target_files]
        if not norm_targets:
            return ImpactAnalysisReport(
                target_files=[],
                affected_files=[],
                affected_symbols=[],
                dependency_chain={},
                relevant_tests=[],
                blast_radius_score=0.0,
                risk_level="LOW",
            )

        # 1. Discover all Python and test files in workspace
        all_py_files: List[Path] = []
        if all_repo_files:
            for rf in all_repo_files:
                p = self.workspace_path / rf
                if p.suffix == ".py" and p.exists():
                    all_py_files.append(p)
        else:
            all_py_files = [
                p for p in self.workspace_path.rglob("*.py")
                if not any(part.startswith(".") or part in ["venv", ".venv", "site-packages", "node_modules"] for part in p.parts)
            ]

        # 2. Extract defined symbols and module names from target files
        target_symbols: Set[str] = set()
        target_module_stems: Set[str] = set()

        for t_file in norm_targets:
            full_t = self.workspace_path / t_file
            target_module_stems.add(Path(t_file).stem)
            # Module path e.g. "auth.service" from "auth/service.py"
            mod_dot = t_file.replace("/", ".").replace(".py", "")
            target_module_stems.add(mod_dot)

            if full_t.exists() and full_t.is_file():
                try:
                    tree = ast.parse(full_t.read_text(encoding="utf-8", errors="ignore"))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            target_symbols.add(node.name)
                except Exception as e:
                    logger.debug(f"Could not parse target file AST {t_file}: {e}")

        # 3. Scan all repo files to build import dependency graph
        direct_dependents: Set[str] = set()
        dependency_chain: Dict[str, List[str]] = {t: [] for t in norm_targets}
        test_files: List[str] = []
        total_py_count = max(len(all_py_files), 1)

        for py_path in all_py_files:
            rel_str = py_path.relative_to(self.workspace_path).as_posix()
            is_test_file = "test" in py_path.name.lower() or "tests/" in rel_str.lower()
            if is_test_file:
                test_files.append(rel_str)

            if rel_str in norm_targets:
                continue

            try:
                content = py_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content)

                imports_target = False
                imported_symbols: List[str] = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if any(alias.name == stem or alias.name.startswith(stem + ".") for stem in target_module_stems):
                                imports_target = True
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        if any(mod == stem or mod.startswith(stem + ".") for stem in target_module_stems):
                            imports_target = True
                            for alias in node.names:
                                if alias.name in target_symbols:
                                    imported_symbols.append(alias.name)

                # Heuristic text match fallback for dynamically resolved imports
                if not imports_target:
                    for stem in target_module_stems:
                        if stem in content:
                            imports_target = True
                            break

                if imports_target:
                    direct_dependents.add(rel_str)
                    for t in norm_targets:
                        t_stem = Path(t).stem
                        if t_stem in content:
                            dependency_chain[t].append(rel_str)

            except Exception as e:
                logger.debug(f"Error analyzing import dependencies in {rel_str}: {e}")

        affected_files = sorted(list(direct_dependents))

        # 4. Map relevant tests
        relevant_tests: Set[str] = set()
        for af in affected_files:
            if "test" in af.lower():
                relevant_tests.add(af)

        for tf in norm_targets:
            stem = Path(tf).stem
            for test_f in test_files:
                if stem in test_f or (f"test_{stem}" in test_f) or (f"{stem}_test" in test_f):
                    relevant_tests.add(test_f)

        # Fallback: if no specific tests matched, include general test suite
        if not relevant_tests and test_files:
            relevant_tests.update(test_files[:3])

        # 5. Compute Blast Radius and Risk Level
        impacted_count = len(affected_files)
        blast_radius = min(1.0, impacted_count / total_py_count) if total_py_count > 0 else 0.0

        # Critical infrastructure weighting
        critical_infra = any(
            any(ci in t.lower() for ci in ["database", "config", "session", "base", "core"])
            for t in norm_targets
        )
        if critical_infra:
            blast_radius = min(1.0, blast_radius + 0.3)

        if blast_radius > 0.4 or impacted_count >= 5 or critical_infra:
            risk_level = "HIGH"
        elif blast_radius > 0.15 or impacted_count >= 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        logger.info(
            f"Impact analysis complete for {norm_targets}: "
            f"{len(affected_files)} affected files, {len(relevant_tests)} relevant tests, risk={risk_level}"
        )

        return ImpactAnalysisReport(
            target_files=norm_targets,
            affected_files=affected_files,
            affected_symbols=sorted(list(target_symbols)),
            dependency_chain=dependency_chain,
            relevant_tests=sorted(list(relevant_tests)),
            blast_radius_score=blast_radius,
            risk_level=risk_level,
        )
