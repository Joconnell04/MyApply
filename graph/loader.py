from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, TextIO, Tuple

from sqlmodel import Session, select

if TYPE_CHECKING:
    from models import GraphEdge, GraphNode

from .schema import GraphEdgePayload, GraphNodePayload, GraphObjectPayload


def _date_to_datetime(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.combine(value, datetime.min.time())


@dataclass
class LoaderResult:
    inserted_nodes: int = 0
    updated_nodes: int = 0
    skipped_nodes: int = 0
    inserted_edges: int = 0
    updated_edges: int = 0
    skipped_edges: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "LoaderResult") -> None:
        self.inserted_nodes += other.inserted_nodes
        self.updated_nodes += other.updated_nodes
        self.skipped_nodes += other.skipped_nodes
        self.inserted_edges += other.inserted_edges
        self.updated_edges += other.updated_edges
        self.skipped_edges += other.skipped_edges
        self.errors.extend(other.errors)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inserted_nodes": self.inserted_nodes,
            "updated_nodes": self.updated_nodes,
            "skipped_nodes": self.skipped_nodes,
            "inserted_edges": self.inserted_edges,
            "updated_edges": self.updated_edges,
            "skipped_edges": self.skipped_edges,
            "errors": self.errors,
        }

    @property
    def ok(self) -> bool:
        return not self.errors


class GraphLoader:
    """Validate and upsert graph content into the database."""

    def __init__(self, session: Session, user_id: Optional[int] = None) -> None:
        self.session = session
        self.user_id = user_id

    def load_path(self, path: Path, auto_commit: bool = True) -> LoaderResult:
        with path.open("r", encoding="utf-8") as handle:
            return self.load_stream(handle, auto_commit=auto_commit)

    def load_stream(self, stream: TextIO, auto_commit: bool = True) -> LoaderResult:
        result = LoaderResult()
        for line_number, raw_line in enumerate(stream, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                payload = self._deserialize(raw_line)
            except Exception as exc:  # pylint: disable=broad-except
                result.errors.append(f"line {line_number}: {exc}")
                continue

            try:
                if isinstance(payload, GraphNodePayload):
                    status = self._upsert_node(payload)
                    if status == "inserted":
                        result.inserted_nodes += 1
                    elif status == "updated":
                        result.updated_nodes += 1
                    else:
                        result.skipped_nodes += 1
                else:
                    status = self._upsert_edge(payload)
                    if status == "inserted":
                        result.inserted_edges += 1
                    elif status == "updated":
                        result.updated_edges += 1
                    else:
                        result.skipped_edges += 1
            except Exception as exc:  # pylint: disable=broad-except
                identifier = getattr(payload, "id", "unknown")
                result.errors.append(f"{identifier}: {exc}")

        if auto_commit and result.ok:
            self.session.commit()
        elif auto_commit and not result.ok:
            self.session.rollback()
        return result

    def load_objects(
        self,
        objects: Iterable[Dict[str, Any]],
        auto_commit: bool = True,
    ) -> LoaderResult:
        buffer = io.StringIO()
        for obj in objects:
            buffer.write(json.dumps(obj))
            buffer.write("\n")
        buffer.seek(0)
        return self.load_stream(buffer, auto_commit=auto_commit)

    def validate_and_upsert(
        self,
        graph_data: Any,
        commit: bool = True,
    ) -> LoaderResult:
        try:
            objects, node_ids, edge_ids = self._normalize_graph_data(graph_data)
        except ValueError as exc:
            result = LoaderResult()
            result.errors.append(str(exc))
            return result

        result = self.load_objects(objects, auto_commit=False)
        if not result.ok:
            self.session.rollback()
            return result

        if not commit:
            self.session.rollback()
            return result

        # Flush pending inserts/updates so we can diff existing data.
        self.session.flush()
        if self.user_id is not None:
            self._sync_removed_objects(node_ids, edge_ids)

        self.session.commit()
        return result

    def _deserialize(self, raw_line: str) -> GraphObjectPayload:
        data = json.loads(raw_line)
        obj_type = data.get("type")
        if obj_type == "node":
            return GraphNodePayload(**data)
        if obj_type == "edge":
            return GraphEdgePayload(**data)
        raise ValueError(f"Unknown graph object type '{obj_type}'")

    def _upsert_node(self, payload: GraphNodePayload) -> str:
        from models import GraphNode

        if self.user_id is None:
            raise ValueError("GraphLoader requires a user_id for node upserts.")

        record = self.session.get(GraphNode, str(payload.id))

        if record and payload.version <= record.version:
            return "skipped"

        if record and record.owner_id != self.user_id:
            raise ValueError("Node belongs to a different user.")

        is_new = record is None
        if is_new:
            record = GraphNode(id=str(payload.id))

        record.owner_id = self.user_id
        record.node_type = payload.node_type
        record.version = payload.version
        record.created_at = payload.created_at
        record.updated_at = payload.updated_at
        record.confidence = float(payload.confidence)
        record.privacy = payload.privacy
        record.labels = list(payload.labels)
        record.provenance = payload.provenance.dict()
        record.data = payload.data.dict()

        self.session.add(record)
        return "inserted" if is_new else "updated"

    def _upsert_edge(self, payload: GraphEdgePayload) -> str:
        from models import GraphEdge

        if self.user_id is None:
            raise ValueError("GraphLoader requires a user_id for edge upserts.")

        record = self.session.get(GraphEdge, str(payload.id))

        if record and payload.version <= record.version:
            return "skipped"

        if record and record.owner_id != self.user_id:
            raise ValueError("Edge belongs to a different user.")

        is_new = record is None
        if is_new:
            record = GraphEdge(id=str(payload.id))

        record.owner_id = self.user_id
        record.edge_type = payload.edge_type
        record.version = payload.version
        record.created_at = payload.created_at
        record.updated_at = payload.updated_at
        record.confidence = float(payload.confidence)
        record.privacy = payload.privacy
        record.labels = list(payload.labels)
        record.provenance = payload.provenance.dict()
        record.from_id = str(payload.from_id)
        record.to_id = str(payload.to_id)
        record.since = _date_to_datetime(payload.since)
        record.until = _date_to_datetime(payload.until)

        self.session.add(record)
        return "inserted" if is_new else "updated"

    def _normalize_graph_data(
        self,
        graph_data: Any,
    ) -> Tuple[List[Dict[str, Any]], set[str], set[str]]:
        if graph_data is None:
            raise ValueError("Graph payload is empty.")

        if isinstance(graph_data, str):
            graph_data = json.loads(graph_data)

        objects: List[Dict[str, Any]] = []
        node_ids: set[str] = set()
        edge_ids: set[str] = set()

        if isinstance(graph_data, list):
            candidates = graph_data
        elif isinstance(graph_data, dict):
            if "objects" in graph_data and isinstance(graph_data["objects"], list):
                candidates = graph_data["objects"]
            else:
                candidates = []
                if isinstance(graph_data.get("nodes"), list):
                    candidates.extend(
                        self._coerce_object(obj, "node") for obj in graph_data["nodes"]
                    )
                if isinstance(graph_data.get("edges"), list):
                    candidates.extend(
                        self._coerce_object(obj, "edge") for obj in graph_data["edges"]
                    )
        else:
            raise ValueError("Graph payload must be a list or dict.")

        if isinstance(graph_data, dict) and "objects" in graph_data and isinstance(graph_data["objects"], list):
            objects = [self._coerce_object(obj) for obj in graph_data["objects"]]
        elif "candidates" in locals():
            objects = [self._coerce_object(obj) for obj in candidates]

        for obj in objects:
            obj_type = obj.get("type")
            obj_id = obj.get("id")
            if obj_type == "node":
                if obj_id:
                    node_ids.add(str(obj_id))
            elif obj_type == "edge":
                if obj_id:
                    edge_ids.add(str(obj_id))
            else:
                raise ValueError(f"Graph object '{obj}' missing valid type.")

        return objects, node_ids, edge_ids

    def _coerce_object(self, obj: Any, fallback_type: Optional[str] = None) -> Dict[str, Any]:
        if not isinstance(obj, dict):
            raise ValueError("Graph objects must be dictionaries.")
        payload = dict(obj)
        if "type" not in payload and fallback_type:
            payload["type"] = fallback_type
        obj_type = payload.get("type")
        if obj_type not in {"node", "edge"}:
            raise ValueError("Graph objects require type 'node' or 'edge'.")
        return payload

    def _sync_removed_objects(self, node_ids: set[str], edge_ids: set[str]) -> None:
        from models import GraphEdge, GraphNode

        # Remove edges not present in the incoming payload.
        edges = (
            self.session.exec(select(GraphEdge).where(GraphEdge.owner_id == self.user_id)).all()
            if self.user_id is not None
            else []
        )
        for edge in edges:
            if edge.id not in edge_ids or edge.from_id not in node_ids or edge.to_id not in node_ids:
                self.session.delete(edge)

        # Remove nodes not present in the incoming payload.
        nodes = (
            self.session.exec(select(GraphNode).where(GraphNode.owner_id == self.user_id)).all()
            if self.user_id is not None
            else []
        )
        for node in nodes:
            if node.id not in node_ids:
                self.session.delete(node)


def parse_graph_payload(
    graph_data: Any,
) -> Tuple[List[GraphNodePayload], List[GraphEdgePayload]]:
    """Convert a structured graph payload into node and edge payloads."""
    if graph_data is None:
        return [], []

    if isinstance(graph_data, str):
        graph_data = json.loads(graph_data)

    objects: List[Dict[str, Any]] = []
    if isinstance(graph_data, dict):
        if isinstance(graph_data.get("objects"), list):
            objects = [obj for obj in graph_data["objects"] if isinstance(obj, dict)]
        else:
            if isinstance(graph_data.get("nodes"), list):
                objects.extend(obj for obj in graph_data["nodes"] if isinstance(obj, dict))
            if isinstance(graph_data.get("edges"), list):
                objects.extend(obj for obj in graph_data["edges"] if isinstance(obj, dict))
    elif isinstance(graph_data, list):
        objects = [obj for obj in graph_data if isinstance(obj, dict)]
    else:
        raise ValueError("Graph payload must be a list or dict.")

    nodes: List[GraphNodePayload] = []
    edges: List[GraphEdgePayload] = []
    for obj in objects:
        obj_type = obj.get("type")
        if obj_type == "node":
            nodes.append(GraphNodePayload(**obj))
        elif obj_type == "edge":
            edges.append(GraphEdgePayload(**obj))
        else:
            raise ValueError("Graph object requires type 'node' or 'edge'.")

    return nodes, edges
