#!/usr/bin/env python3
"""
Render a knowledge graph as SVG from Neo4j.

Usage:
    python scripts/render_graph.py --query "MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50"
    python scripts/render_graph.py --entity "machine learning"
    python scripts/render_graph.py --all --limit 100

Options:
    --query CYPHER    Execute a custom Cypher query
    --entity NAME     Show all connections for a specific entity
    --all             Show the entire graph (with --limit)
    --limit N         Max nodes to render (default: 50)
    --output PATH     Output file path (default: build/graphs/knowledge-graph.svg)
    --format FMT      Output format: svg, png, pdf (default: svg)
    --neo4j-uri URI   Neo4j connection (default: bolt://localhost:7687)
    --neo4j-user USER Neo4j username (default: neo4j)
    --neo4j-pass PASS Neo4j password (default: knowledge123)
    --neo4j-db DB     Neo4j database (default: neo4j)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import graphviz
except ImportError:
    print("Error: graphviz package required. Install: pip install graphviz")
    print("Also need system graphviz: brew install graphviz")
    sys.exit(1)

from neo4j import GraphDatabase

# Add project src to path for link_resolver import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from knowledge_agents.claude_agent.link_resolver import (
    NODE_SCHEMA,
    get_color,
    get_shape,
    resolve_link,
)


def query_neo4j(driver, database, cypher):
    """Execute a Cypher query and return records."""
    with driver.session(database=database) as session:
        result = session.run(cypher)
        return [dict(record) for record in result]


def build_entity_graph(driver, database, entity_name, limit=50):
    """Get all connections for a specific entity (supports Graphiti + legacy)."""
    cypher = f"""
    MATCH (e:Entity {{name: '{entity_name}'}})-[r]-(connected)
    RETURN e.name AS from_name,
           COALESCE(head([l IN labels(e) WHERE l <> 'Entity']), 'Entity') AS from_type,
           type(r) AS rel_type,
           CASE WHEN connected:Entity THEN connected.name
                WHEN connected:Note THEN connected.file_path
                WHEN connected:Episodic THEN connected.name
                ELSE 'unknown' END AS to_name,
           CASE WHEN connected:Note THEN 'Note'
                WHEN connected:Episodic THEN 'Episode'
                ELSE COALESCE(head([l IN labels(connected) WHERE l <> 'Entity']), 'Entity') END AS to_type,
           properties(e) AS from_props,
           properties(connected) AS to_props
    LIMIT {limit}
    """
    return query_neo4j(driver, database, cypher)


def build_all_graph(driver, database, limit=50):
    """Get the full graph — supports both Graphiti and legacy schemas."""
    # Graphiti schema: Entity nodes with RELATES_TO edges + Episodic MENTIONS
    cypher = f"""
    MATCH (n)-[r]->(m)
    WHERE (n:Entity OR n:Note OR n:Episodic) AND (m:Entity OR m:Note OR m:Episodic)
    AND type(r) IN ['RELATES_TO', 'MENTIONS', 'CONTAINS', 'HAS_SECTION', 'HAS_MEMBER']
    RETURN
        CASE WHEN n:Note THEN n.file_path
             WHEN n:Episodic THEN n.name
             ELSE n.name END AS from_name,
        CASE WHEN n:Note THEN 'Note'
             WHEN n:Episodic THEN 'Episode'
             ELSE COALESCE(head([l IN labels(n) WHERE l <> 'Entity']), 'Entity') END AS from_type,
        type(r) AS rel_type,
        CASE WHEN m:Note THEN m.file_path
             WHEN m:Episodic THEN m.name
             ELSE m.name END AS to_name,
        CASE WHEN m:Note THEN 'Note'
             WHEN m:Episodic THEN 'Episode'
             ELSE COALESCE(head([l IN labels(m) WHERE l <> 'Entity']), 'Entity') END AS to_type,
        properties(n) AS from_props,
        properties(m) AS to_props
    LIMIT {limit}
    """
    return query_neo4j(driver, database, cypher)


def build_custom_graph(driver, database, cypher_query):
    """Execute a custom Cypher query for graph data."""
    records = query_neo4j(driver, database, cypher_query)
    # Try to normalize records into from/to/rel format
    normalized = []
    for record in records:
        keys = list(record.keys())
        if len(keys) >= 3:
            normalized.append({
                "from_name": str(record[keys[0]]),
                "from_type": str(record.get(keys[1], "Entity")) if len(keys) > 3 else "Entity",
                "rel_type": str(record[keys[-3 if len(keys) > 3 else 1]]),
                "to_name": str(record[keys[-2 if len(keys) > 3 else 2]]),
                "to_type": str(record.get(keys[-1], "Entity")) if len(keys) > 3 else "Entity",
            })
        elif len(keys) >= 1:
            # Single column — just list entities
            normalized.append({
                "from_name": str(record[keys[0]]),
                "from_type": str(record.get(keys[1], "Entity")) if len(keys) > 1 else "Entity",
                "rel_type": "",
                "to_name": "",
                "to_type": "",
            })
    return normalized


def render_svg(records, output_path, fmt="svg", title=None):
    """Render graph records as SVG using graphviz."""
    dot = graphviz.Digraph(
        name="knowledge_graph",
        format=fmt,
        engine="neato",
        graph_attr={
            "overlap": "false",
            "splines": "true",
            "bgcolor": "white",
            "fontname": "Helvetica",
            "label": title or f"Knowledge Graph ({len(records)} edges)",
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
            "fontsize": "8",
            "color": "#888888",
            "fontcolor": "#555555",
        },
    )

    # Collect unique nodes with their properties for link resolution
    nodes: dict[str, dict] = {}  # name → {type, props}
    for r in records:
        if r.get("from_name"):
            props = dict(r.get("from_props", {}) or {})
            props["name"] = r["from_name"]
            if r.get("from_type") == "Note":
                props["file_path"] = r["from_name"]
            nodes[r["from_name"]] = {"type": r.get("from_type", "Entity"), "props": props}
        if r.get("to_name"):
            props = dict(r.get("to_props", {}) or {})
            props["name"] = r["to_name"]
            if r.get("to_type") == "Note":
                props["file_path"] = r["to_name"]
            nodes[r["to_name"]] = {"type": r.get("to_type", "Entity"), "props": props}

    # Add nodes with schema-driven colors, shapes, and links
    for name, info in nodes.items():
        node_type = info["type"]
        props = info["props"]
        color = get_color(node_type)
        shape = get_shape(node_type)
        url = resolve_link(node_type, props)

        if node_type == "Note":
            short_name = Path(name).stem
            label = f"\U0001f4c4 {short_name}"
            attrs = {
                "label": label,
                "fillcolor": color,
                "shape": shape,
                "style": "filled",
                "fontsize": "11",
                "penwidth": "2",
                "color": "#B8860B",
                "tooltip": name,
            }
        else:
            label = f"{name}\n({node_type})" if node_type and node_type != "Entity" else name
            attrs = {
                "label": label,
                "fillcolor": color,
                "shape": shape,
                "style": "rounded,filled",
            }

        if url:
            attrs["URL"] = url
            attrs["target"] = "_blank"

        dot.node(name, **attrs)

    # Add edges
    for r in records:
        if r.get("from_name") and r.get("to_name") and r.get("rel_type"):
            dot.edge(r["from_name"], r["to_name"], label=r["rel_type"])

    # Render
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # graphviz renders to output_path.svg, we want just output_path
    rendered = dot.render(str(output.with_suffix("")), cleanup=True)
    print(f"Graph rendered: {rendered} ({len(nodes)} nodes, {len(records)} edges)")
    return rendered


def main():
    parser = argparse.ArgumentParser(description="Render knowledge graph as SVG")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", help="Custom Cypher query")
    group.add_argument("--entity", help="Show connections for a specific entity")
    group.add_argument("--all", action="store_true", help="Show entire graph")

    parser.add_argument("--limit", type=int, default=50, help="Max edges (default: 50)")
    parser.add_argument("--output", default="build/graphs/knowledge-graph.svg", help="Output file path")
    parser.add_argument("--format", default="svg", choices=["svg", "png", "pdf"], help="Output format")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-pass", default="knowledge123")
    parser.add_argument("--neo4j-db", default="neo4j")
    parser.add_argument("--title", help="Graph title")

    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_pass))

    try:
        driver.verify_connectivity()
    except Exception as e:
        print(f"Error: Cannot connect to Neo4j at {args.neo4j_uri}: {e}")
        sys.exit(1)

    if args.entity:
        records = build_entity_graph(driver, args.neo4j_db, args.entity, args.limit)
        title = args.title or f"Connections: {args.entity}"
    elif args.all:
        records = build_all_graph(driver, args.neo4j_db, args.limit)
        title = args.title or "Full Knowledge Graph"
    else:
        records = build_custom_graph(driver, args.neo4j_db, args.query)
        title = args.title or "Custom Query Result"

    driver.close()

    if not records:
        print("No data returned. The knowledge graph may be empty.")
        print("Build it first: /knowledge read some notes and build a knowledge graph")
        sys.exit(0)

    render_svg(records, args.output, args.format, title)


if __name__ == "__main__":
    main()
