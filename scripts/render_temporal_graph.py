#!/usr/bin/env python3
"""
Render a temporal knowledge graph as SVG — shows facts from a date range.

Usage:
    python scripts/render_temporal_graph.py --start 2026-03-17 --end 2026-03-24
    python scripts/render_temporal_graph.py --start 2026-03-01 --end 2026-03-31 --output build/graphs/march.svg
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import graphviz
except ImportError:
    print("Error: pip install graphviz && brew install graphviz")
    sys.exit(1)

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from knowledge_agents.claude_agent.link_resolver import get_color, resolve_link

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "knowledge123"


def query_temporal_graph(driver, start_dt, end_dt, limit=60):
    """Query facts created in a date range with their entities."""
    with driver.session(database="neo4j") as s:
        records = []

        # Facts (RELATES_TO edges) created in range
        r = s.run("""
            MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
            WHERE r.created_at >= $start AND r.created_at <= $end
            RETURN a.name AS from_name,
                   COALESCE(head([l IN labels(a) WHERE l <> 'Entity']), 'Entity') AS from_type,
                   r.name AS rel_type,
                   r.fact AS fact,
                   b.name AS to_name,
                   COALESCE(head([l IN labels(b) WHERE l <> 'Entity']), 'Entity') AS to_type,
                   toString(r.created_at) AS created_at
            ORDER BY r.created_at DESC
            LIMIT $limit
        """, start=start_dt, end=end_dt, limit=limit)

        for rec in r:
            records.append(dict(rec))

        # Also get episodes (source provenance) from this period
        r = s.run("""
            MATCH (ep:Episodic)-[:MENTIONS]->(e:Entity)
            WHERE ep.created_at >= $start AND ep.created_at <= $end
            RETURN ep.name AS from_name,
                   'Episode' AS from_type,
                   'MENTIONS' AS rel_type,
                   '' AS fact,
                   e.name AS to_name,
                   COALESCE(head([l IN labels(e) WHERE l <> 'Entity']), 'Entity') AS to_type,
                   toString(ep.created_at) AS created_at
            LIMIT $limit
        """, start=start_dt, end=end_dt, limit=limit)

        for rec in r:
            records.append(dict(rec))

        return records


def render_temporal_svg(records, output_path, start_str, end_str, fmt="svg"):
    """Render temporal graph with fact labels on edges."""

    def _safe(s):
        return str(s).replace("\\", "").replace('"', "'").replace("\n", " ").replace("\r", "")[:60]

    dot = graphviz.Digraph(
        name="temporal_knowledge",
        format=fmt,
        engine="dot",
        graph_attr={
            "rankdir": "LR",
            "overlap": "false",
            "splines": "true",
            "bgcolor": "white",
            "fontname": "Helvetica",
            "label": f"Knowledge Changelog: {start_str} → {end_str}  ({len(records)} facts)",
            "labelloc": "t",
            "fontsize": "16",
        },
        node_attr={
            "shape": "box",
            "style": "rounded,filled",
            "fontname": "Helvetica",
            "fontsize": "10",
            "margin": "0.15,0.08",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "7",
            "color": "#555555",
            "fontcolor": "#333333",
        },
    )

    # Collect nodes
    nodes = {}
    for r in records:
        if r.get("from_name"):
            nodes[r["from_name"]] = r.get("from_type", "Entity")
        if r.get("to_name"):
            nodes[r["to_name"]] = r.get("to_type", "Entity")

    # Add nodes
    for name, node_type in nodes.items():
        color = get_color(node_type)
        safe_name = _safe(name)

        if node_type == "Episode":
            dot.node(safe_name, label=f"📄 {safe_name}", fillcolor="#E8F5E9", shape="note", style="filled", fontsize="9")
        else:
            label = f"{safe_name}\n({node_type})" if node_type != "Entity" else safe_name
            dot.node(safe_name, label=label, fillcolor=color)

    # Add edges with fact labels
    for r in records:
        if r.get("from_name") and r.get("to_name"):
            fact = r.get("fact", "")
            rel = r.get("rel_type", "RELATES_TO")

            # Truncate long facts for edge label
            if fact and len(fact) > 50:
                label = f"{rel}\n{fact[:50]}..."
            elif fact:
                label = f"{rel}\n{fact}"
            else:
                label = rel

            dot.edge(_safe(r["from_name"]), _safe(r["to_name"]), label=label)

    # Render
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = dot.render(str(output.with_suffix("")), cleanup=True)
    print(f"Temporal graph: {rendered} ({len(nodes)} nodes, {len(records)} edges)")
    return rendered


def main():
    parser = argparse.ArgumentParser(description="Render temporal knowledge graph")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default="build/graphs/temporal.svg")
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()

    start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(args.end).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    records = query_temporal_graph(driver, start_dt, end_dt, args.limit)
    driver.close()

    if not records:
        print(f"No facts found between {args.start} and {args.end}")
        return

    render_temporal_svg(records, args.output, args.start, args.end)


if __name__ == "__main__":
    main()
