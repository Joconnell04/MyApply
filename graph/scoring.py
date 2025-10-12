from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import exp, log
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union

from .schema import (
    EdgeType,
    GraphEdgePayload,
    GraphNodePayload,
    MetricData,
    MetricDirection,
    NodeType,
    OutcomeCategory,
    OutcomeData,
    ProjectData,
    TaskData,
)


OUTCOME_WEIGHTS: Dict[OutcomeCategory, float] = {
    OutcomeCategory.COST: 1.2,
    OutcomeCategory.REVENUE: 1.3,
    OutcomeCategory.ADOPTION: 1.1,
    OutcomeCategory.SPEED: 1.0,
    OutcomeCategory.RELIABILITY: 0.9,
    OutcomeCategory.QUALITY: 0.8,
}


def calculate_project_impact_scores(
    nodes: Iterable[GraphNodePayload],
    edges: Iterable[GraphEdgePayload],
) -> Dict[str, float]:
    """Compute weighted metric deltas for each project."""
    node_map: Dict[str, GraphNodePayload] = {str(node.id): node for node in nodes}
    task_to_project: Dict[str, str] = {}
    outcome_to_project: Dict[str, str] = {}
    outcome_metrics: Dict[str, Set[str]] = defaultdict(set)

    for edge in edges:
        if edge.edge_type == EdgeType.CONTAINS_TASK:
            task_to_project[str(edge.to_id)] = str(edge.from_id)
        elif edge.edge_type == EdgeType.PRODUCED_OUTCOME:
            source_id = str(edge.from_id)
            outcome_id = str(edge.to_id)
            project_id = None
            source_node = node_map.get(source_id)
            if source_node:
                if source_node.node_type == NodeType.PROJECT:
                    project_id = source_id
                elif source_node.node_type == NodeType.TASK:
                    project_id = task_to_project.get(source_id)
            else:
                project_id = task_to_project.get(source_id)
            if project_id:
                outcome_to_project[outcome_id] = project_id
        elif edge.edge_type == EdgeType.MEASURED_BY:
            outcome_metrics[str(edge.from_id)].add(str(edge.to_id))

    project_scores: Dict[str, float] = defaultdict(float)
    for outcome_id, project_id in outcome_to_project.items():
        outcome_node = node_map.get(outcome_id)
        if not outcome_node or outcome_node.node_type != NodeType.OUTCOME:
            continue
        outcome_data = outcome_node.data
        if not isinstance(outcome_data, OutcomeData):
            continue
        weight = OUTCOME_WEIGHTS.get(outcome_data.category, 1.0)
        metric_ids = outcome_metrics.get(outcome_id, set())
        for metric_id in metric_ids:
            metric_node = node_map.get(metric_id)
            if not metric_node or metric_node.node_type != NodeType.METRIC:
                continue
            metric_data = metric_node.data
            if not isinstance(metric_data, MetricData):
                continue
            baseline = metric_data.baseline_value or 0.0
            final = metric_data.final_value or 0.0
            delta = final - baseline
            if metric_data.direction == MetricDirection.LOWER_IS_BETTER:
                delta = baseline - final
            elif metric_data.direction == MetricDirection.TARGET:
                delta = abs(final - baseline)
            project_scores[project_id] += weight * delta

    return dict(project_scores)


def calculate_seniority_signal(
    nodes: Iterable[GraphNodePayload],
    edges: Iterable[GraphEdgePayload],
) -> int:
    """Count projects with ≥2 outcomes, ≥3 tools, and ≥1 decision."""
    node_map: Dict[str, GraphNodePayload] = {str(node.id): node for node in nodes}
    project_ids = {str(node.id) for node in nodes if node.node_type == NodeType.PROJECT}

    task_to_project: Dict[str, str] = {}
    project_outcomes: Dict[str, Set[str]] = defaultdict(set)
    project_tools: Dict[str, Set[str]] = defaultdict(set)
    project_decisions: Dict[str, Set[str]] = defaultdict(set)

    for edge in edges:
        source = str(edge.from_id)
        target = str(edge.to_id)
        if edge.edge_type == EdgeType.CONTAINS_TASK:
            task_to_project[target] = source
        elif edge.edge_type == EdgeType.PRODUCED_OUTCOME:
            project_id = source if source in project_ids else task_to_project.get(source)
            if project_id:
                project_outcomes[project_id].add(target)
        elif edge.edge_type == EdgeType.USED_TOOL:
            project_id = source if source in project_ids else task_to_project.get(source)
            if project_id:
                project_tools[project_id].add(target)
        elif edge.edge_type == EdgeType.MADE_DECISION:
            project_id = source if source in project_ids else task_to_project.get(source)
            if project_id:
                project_decisions[project_id].add(target)

    qualified = 0
    for project_id in project_ids:
        outcomes = len(project_outcomes[project_id])
        tools = len(project_tools[project_id])
        decisions = len(project_decisions[project_id])
        if outcomes >= 2 and tools >= 3 and decisions >= 1:
            qualified += 1
    return qualified


def recency_boost(end_date: Optional[date], reference_date: Optional[date] = None, half_life_days: int = 365) -> float:
    """Exponential decay factor for recency bias."""
    if end_date is None:
        return 1.0
    if reference_date is None:
        reference_date = date.today()
    delta_days = (reference_date - end_date).days
    if delta_days <= 0:
        return 1.0
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    decay_constant = log(2) / half_life_days
    return exp(-decay_constant * delta_days)


def rank_facts(
    nodes: Iterable[GraphNodePayload],
    edges: Iterable[GraphEdgePayload],
    jd_factors: Dict[str, Union[List[str], str, None]],
    top_n: int = 10,
) -> List[Dict[str, object]]:
    """Score task facts against JD factors and return sorted metadata."""
    node_map: Dict[str, GraphNodePayload] = {str(node.id): node for node in nodes}
    edges_from: Dict[str, List[GraphEdgePayload]] = defaultdict(list)
    edges_to: Dict[str, List[GraphEdgePayload]] = defaultdict(list)
    for edge in edges:
        edges_from[str(edge.from_id)].append(edge)
        edges_to[str(edge.to_id)].append(edge)

    def _normalize_list(value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if isinstance(item, (str, int, float))]
        if isinstance(value, str):
            return [value]
        return [str(value)]

    def _tokenize(text: str) -> Set[str]:
        return {token.lower() for token in text.replace("/", " ").replace(",", " ").split() if len(token) > 2}

    jd_must_skills = {skill.lower() for skill in _normalize_list(jd_factors.get("must_have_skills"))}
    jd_nice_skills = {skill.lower() for skill in _normalize_list(jd_factors.get("nice_to_have_skills"))}
    jd_skill_targets = jd_must_skills | jd_nice_skills
    jd_ats_keywords = {kw.lower() for kw in _normalize_list(jd_factors.get("ats_keywords"))}
    jd_domains = {domain.lower() for domain in _normalize_list(jd_factors.get("domain"))}
    jd_metric_signals = {signal.lower() for signal in _normalize_list(jd_factors.get("metrics_signals"))}

    ranked: List[Dict[str, object]] = []

    for node in nodes:
        if node.node_type != NodeType.TASK:
            continue

        task_id = str(node.id)
        task_data = node.data
        if not isinstance(task_data, TaskData):
            continue

        project_id: Optional[str] = None
        for edge in edges_to.get(task_id, []):
            if edge.edge_type == EdgeType.CONTAINS_TASK:
                project_id = str(edge.from_id)
                break

        project_data: Optional[ProjectData] = None
        project_name: Optional[str] = None
        project_domains: Set[str] = set()
        if project_id and (project := node_map.get(project_id)):
            if isinstance(project.data, ProjectData):
                project_data = project.data
                project_name = project_data.name
                project_domains = {domain.lower() for domain in project_data.domain}

        skill_nodes: Set[str] = set()
        skills_original: Dict[str, str] = {}
        for edge in edges_from.get(task_id, []):
            if edge.edge_type == EdgeType.APPLIED_SKILL:
                skill_node = node_map.get(str(edge.to_id))
                if skill_node and skill_node.node_type == NodeType.SKILL:
                    skill_name = getattr(skill_node.data, "name", None)
                    if skill_name:
                        lowered = skill_name.lower()
                        skill_nodes.add(lowered)
                        skills_original[lowered] = skill_name

        outcome_ids = [
            str(edge.to_id)
            for edge in edges_from.get(task_id, [])
            if edge.edge_type == EdgeType.PRODUCED_OUTCOME
        ]
        metric_names: Dict[str, str] = {}
        for outcome_id in outcome_ids:
            for edge in edges_from.get(outcome_id, []):
                if edge.edge_type == EdgeType.MEASURED_BY:
                    metric_node = node_map.get(str(edge.to_id))
                    if metric_node and metric_node.node_type == NodeType.METRIC:
                        metric_data = metric_node.data
                        if isinstance(metric_data, MetricData):
                            name = metric_data.name
                            metric_names[name.lower()] = name

        ats_tokens = set(node.labels)
        ats_tokens.update(_tokenize(task_data.name))
        ats_tokens.update(_tokenize(task_data.description or ""))
        for outcome_id in outcome_ids:
            outcome_node = node_map.get(outcome_id)
            if outcome_node and isinstance(outcome_node.data, OutcomeData):
                ats_tokens.update(_tokenize(outcome_node.data.title))
                ats_tokens.update(_tokenize(outcome_node.data.description or ""))

        matched_skills = jd_skill_targets & skill_nodes
        matched_ats = jd_ats_keywords & ats_tokens
        matched_domains = jd_domains & project_domains

        skill_overlap = len(matched_skills) / max(len(jd_skill_targets), 1)
        ats_overlap = len(matched_ats) / max(len(jd_ats_keywords), 1)
        domain_match = 1.0 if matched_domains else 0.0

        metric_intersection = {
            metric for metric in metric_names if metric in jd_metric_signals
        }
        if jd_metric_signals:
            metric_relevance = len(metric_intersection) / len(jd_metric_signals)
        else:
            metric_relevance = 1.0 if metric_names else 0.0

        recency_end = task_data.end_date or (project_data.end_date if project_data else None)
        recency_score = recency_boost(recency_end) if recency_end else 0.6

        score = (
            0.40 * skill_overlap
            + 0.20 * ats_overlap
            + 0.15 * domain_match
            + 0.15 * metric_relevance
            + 0.10 * recency_score
        )

        ranked.append(
            {
                "id": task_id,
                "score": round(score, 4),
                "metadata": {
                    "task_name": task_data.name,
                    "task_description": task_data.description or "",
                    "project_name": project_name,
                    "skills": [skills_original[skill] for skill in matched_skills],
                    "all_skills": [skills_original[skill] for skill in skill_nodes],
                    "ats_matches": list(matched_ats),
                    "domains": list(project_domains),
                    "matched_domains": list(matched_domains),
                    "metrics": [metric_names[m] for m in metric_names],
                    "matched_metrics": [metric_names[m] for m in metric_intersection],
                    "recency": recency_score,
                    "end_date": recency_end.isoformat() if recency_end else None,
                },
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)

    if top_n and len(ranked) > top_n:
        ranked = ranked[:top_n]

    return ranked
