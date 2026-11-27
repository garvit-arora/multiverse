"""Behavioural fingerprinting, normalization, similarity metrics, and NetworkX graph builder."""
from __future__ import annotations

import hashlib
import re
from typing import Any

import networkx as nx
import numpy as np
import rfc8785
from sklearn.metrics import jaccard_score

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")
HEX_ID_RE = re.compile(r"\b[0-9a-fA-F]{16,64}\b")


def normalize_string(val: str) -> str:
    val = UUID_RE.sub("<UUID>", val)
    val = ISO_TS_RE.sub("<TIMESTAMP>", val)
    val = HEX_ID_RE.sub("<HEX_ID>", val)
    return val.strip()


def normalize_observation(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize non-deterministic fields into a canonical behaviour representation."""
    routes = sorted({normalize_string(str(r)) for r in raw.get("routes_visited", [])})
    components = sorted({normalize_string(str(c)) for c in raw.get("visible_components", [])})
    api_ops = sorted({normalize_string(str(a)) for a in raw.get("api_operations", [])})
    status_classes = sorted({str(s) for s in raw.get("http_status_classes", [])})
    business_events = [normalize_string(str(e)) for e in raw.get("business_events", [])]
    outcome = str(raw.get("outcome", "unknown"))

    return {
        "routes_visited": routes,
        "visible_components": components,
        "api_operations": api_ops,
        "http_status_classes": status_classes,
        "business_events": business_events,
        "outcome": outcome,
    }


def compute_fingerprint(normalized_behaviour: dict[str, Any]) -> str:
    canonical = rfc8785.dumps(normalized_behaviour)
    return hashlib.sha256(canonical).hexdigest()


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)


def compute_behaviour_similarity(summary_a: dict[str, Any], summary_b: dict[str, Any]) -> dict[str, Any]:
    """Compute multi-dimensional similarity between two observed behaviour summaries."""
    comp_a = set(summary_a.get("visible_components", []))
    comp_b = set(summary_b.get("visible_components", []))
    api_a = set(summary_a.get("api_operations", []))
    api_b = set(summary_b.get("api_operations", []))
    evt_a = set(summary_a.get("business_events", []))
    evt_b = set(summary_b.get("business_events", []))

    vocab = sorted(comp_a | comp_b | api_a | api_b | evt_a | evt_b)
    if vocab:
        vec_a = np.array([1 if t in (comp_a | api_a | evt_a) else 0 for t in vocab])
        vec_b = np.array([1 if t in (comp_b | api_b | evt_b) else 0 for t in vocab])
        sk_jaccard = float(jaccard_score(vec_a, vec_b))
        euclidean_dist = float(np.linalg.norm(vec_a - vec_b) / np.sqrt(len(vocab)))
    else:
        sk_jaccard = 1.0
        euclidean_dist = 0.0

    outcome_match = 1.0 if summary_a.get("outcome") == summary_b.get("outcome") else 0.0
    overall = 0.5 * sk_jaccard + 0.3 * (1.0 - euclidean_dist) + 0.2 * outcome_match

    return {
        "overall_similarity": round(overall, 4),
        "jaccard_similarity": round(sk_jaccard, 4),
        "normalized_vector_distance": round(euclidean_dist, 4),
        "outcome_match": bool(outcome_match),
        "component_diff": {
            "only_a": sorted(comp_a - comp_b),
            "only_b": sorted(comp_b - comp_a),
        },
        "api_diff": {
            "only_a": sorted(api_a - api_b),
            "only_b": sorted(api_a ^ api_b),
        },
    }


def build_behaviour_graph(
    behaviours: list[dict[str, Any]],
    observed_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a NetworkX graph of discovered behaviours with 3D/2D deterministic coordinates and analytics."""
    g = nx.Graph()
    for idx, b in enumerate(behaviours):
        g.add_node(
            b["id"],
            fingerprint=b["fingerprint"],
            config_count=b.get("config_count", 1),
            summary=b.get("summary", {}),
            index=idx,
        )

    for edge in observed_edges:
        src = edge["from_behaviour_id"]
        dst = edge["to_behaviour_id"]
        if g.has_node(src) and g.has_node(dst) and src != dst:
            g.add_edge(
                src,
                dst,
                relationship_type=edge.get("relationship_type", "observed_delta"),
                flag_delta=edge.get("flag_delta", {}),
                inferred=edge.get("relationship_type") == "inferred_similarity",
            )

    # Add clearly-labelled inferred similarity edges for disconnected components if >= 2 nodes
    node_ids = list(g.nodes)
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            u, v = node_ids[i], node_ids[j]
            if not g.has_edge(u, v):
                sim = compute_behaviour_similarity(
                    g.nodes[u].get("summary", {}),
                    g.nodes[v].get("summary", {}),
                )["overall_similarity"]
                if sim >= 0.45:
                    g.add_edge(u, v, relationship_type="inferred_similarity", similarity=sim, inferred=True)

    # Connected component clusters
    clusters: dict[str, int] = {}
    for cluster_idx, comp in enumerate(nx.connected_components(g)):
        for nid in comp:
            clusters[nid] = cluster_idx

    # Deterministic 3D & 2D layout using NetworkX spring_layout
    if len(g.nodes) > 0:
        pos_3d = nx.spring_layout(g, dim=3, seed=42, scale=12.0)
        pos_2d = nx.spring_layout(g, dim=2, seed=42, scale=300.0)
    else:
        pos_3d = {}
        pos_2d = {}

    nodes_out = []
    for nid, attrs in g.nodes(data=True):
        p3 = pos_3d.get(nid, [0.0, 0.0, 0.0])
        p2 = pos_2d.get(nid, [0.0, 0.0])
        nodes_out.append({
            "id": nid,
            "fingerprint": attrs["fingerprint"],
            "config_count": attrs["config_count"],
            "cluster_id": clusters.get(nid, 0),
            "summary": attrs["summary"],
            "position_3d": [round(float(p3[0]), 3), round(float(p3[1]), 3), round(float(p3[2]), 3)],
            "position_2d": [round(float(p2[0]), 2), round(float(p2[1]), 2)],
        })

    edges_out = []
    for u, v, attrs in g.edges(data=True):
        edges_out.append({
            "source": u,
            "target": v,
            "relationship_type": attrs.get("relationship_type", "observed_delta"),
            "inferred": bool(attrs.get("inferred", False)),
            "flag_delta": attrs.get("flag_delta", {}),
            "similarity": attrs.get("similarity"),
        })

    return {
        "nodes": nodes_out,
        "edges": edges_out,
        "cluster_count": len(set(clusters.values())),
    }
