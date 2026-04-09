"""
core/pipeline/model.py
Data model for Visual Pipeline Builder.

A Pipeline is a directed graph:
  [DataSource] → [QueryFilter?] → [GeoprocessNode*] → [OutputNode]

Each Node has:
  - node_id  : unique str
  - node_type: "source" | "query" | "geoprocess" | "output"
  - params   : dict of node-specific parameters
  - position : (x, y) on canvas

Edges: list of (from_node_id, to_node_id)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


NODE_TYPES = {
    "source":     ("📦", "Data Source",      "#1e4a2a"),
    "query":      ("🔍", "Query Filter",     "#1e2a4a"),
    "geoprocess": ("⚙",  "Geoprocessing",   "#2a1e4a"),
    "output":     ("💾", "Output Table",     "#4a2a1e"),
}


@dataclass
class PipelineNode:
    node_id:   str
    node_type: str            # source | query | geoprocess | output
    params:    Dict[str, Any] = field(default_factory=dict)
    x: float = 0.0
    y: float = 0.0

    @staticmethod
    def new(node_type: str, x: float = 0, y: float = 0) -> "PipelineNode":
        return PipelineNode(
            node_id=str(uuid.uuid4())[:8],
            node_type=node_type,
            x=x, y=y,
        )

    @property
    def label(self) -> str:
        t = self.node_type
        if t == "source":
            tbl = self.params.get("table", "")
            return f"📦 {tbl}" if tbl else "📦 Source"
        if t == "query":
            return "🔍 Query Filter"
        if t == "geoprocess":
            op = self.params.get("operation", "")
            return f"⚙ {op}" if op else "⚙ Geoprocess"
        if t == "output":
            tbl = self.params.get("output_table", "")
            return f"💾 {tbl}" if tbl else "💾 Output"
        return self.node_type

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineNode":
        return cls(**d)


@dataclass
class PipelineEdge:
    from_id: str
    to_id:   str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineEdge":
        return cls(**d)


@dataclass
class Pipeline:
    name:        str = "Pipeline Baru"
    description: str = ""
    nodes:       List[PipelineNode] = field(default_factory=list)
    edges:       List[PipelineEdge] = field(default_factory=list)

    # ── Graph helpers ──────────────────────────────────────────────────────────

    def add_node(self, node: PipelineNode):
        self.nodes.append(node)

    def remove_node(self, node_id: str):
        self.nodes = [n for n in self.nodes if n.node_id != node_id]
        self.edges = [e for e in self.edges
                      if e.from_id != node_id and e.to_id != node_id]

    def add_edge(self, from_id: str, to_id: str) -> bool:
        """Add edge, reject if it would create a cycle or duplicate."""
        if from_id == to_id:
            return False
        if any(e.from_id == from_id and e.to_id == to_id for e in self.edges):
            return False
        self.edges.append(PipelineEdge(from_id, to_id))
        return True

    def remove_edge(self, from_id: str, to_id: str):
        self.edges = [e for e in self.edges
                      if not (e.from_id == from_id and e.to_id == to_id)]

    def node_by_id(self, node_id: str) -> Optional[PipelineNode]:
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def successors(self, node_id: str) -> List[PipelineNode]:
        ids = {e.to_id for e in self.edges if e.from_id == node_id}
        return [n for n in self.nodes if n.node_id in ids]

    def predecessors(self, node_id: str) -> List[PipelineNode]:
        ids = {e.from_id for e in self.edges if e.to_id == node_id}
        return [n for n in self.nodes if n.node_id in ids]

    def topological_order(self) -> List[PipelineNode]:
        """Kahn's algorithm — raises ValueError if cycle detected."""
        in_degree: Dict[str, int] = {n.node_id: 0 for n in self.nodes}
        for e in self.edges:
            in_degree[e.to_id] = in_degree.get(e.to_id, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: List[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for succ in self.successors(nid):
                in_degree[succ.node_id] -= 1
                if in_degree[succ.node_id] == 0:
                    queue.append(succ.node_id)

        if len(order) != len(self.nodes):
            raise ValueError("Pipeline mengandung siklus (cycle)")
        return [self.node_by_id(nid) for nid in order]

    def validate(self) -> List[str]:
        """Return list of validation error messages (empty = OK)."""
        errors = []
        sources = [n for n in self.nodes if n.node_type == "source"]
        outputs = [n for n in self.nodes if n.node_type == "output"]

        if not sources:
            errors.append("Pipeline harus memiliki minimal 1 node Data Source")
        if not outputs:
            errors.append("Pipeline harus memiliki minimal 1 node Output")

        for n in self.nodes:
            if n.node_type == "source" and not n.params.get("table"):
                errors.append(f"Node Source [{n.node_id}]: tabel belum dipilih")
            if n.node_type == "geoprocess" and not n.params.get("operation"):
                errors.append(f"Node Geoprocess [{n.node_id}]: operasi belum dipilih")
            if n.node_type == "output" and not n.params.get("output_table"):
                errors.append(f"Node Output [{n.node_id}]: nama tabel output belum diisi")

        try:
            self.topological_order()
        except ValueError as e:
            errors.append(str(e))

        return errors

    # ── Serialization ──────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Pipeline":
        return cls(
            name=d.get("name", "Pipeline"),
            description=d.get("description", ""),
            nodes=[PipelineNode.from_dict(n) for n in d.get("nodes", [])],
            edges=[PipelineEdge.from_dict(e) for e in d.get("edges", [])],
        )

    @classmethod
    def from_json(cls, s: str) -> "Pipeline":
        return cls.from_dict(json.loads(s))

    def save_to_file(self, path) -> Tuple[bool, str]:
        try:
            from pathlib import Path
            Path(path).write_text(self.to_json(), encoding="utf-8")
            return True, f"Pipeline disimpan: {Path(path).name}"
        except Exception as e:
            return False, str(e)

    @classmethod
    def load_from_file(cls, path) -> Tuple[Optional["Pipeline"], str]:
        try:
            from pathlib import Path
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls.from_dict(data), "Pipeline berhasil dimuat"
        except Exception as e:
            return None, str(e)
