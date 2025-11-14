#!/usr/bin/env python3
"""
Generate a simple Prometheus dashboard URL with two key metrics:

1. Total workflow agent invocations every 5 minutes
2. Percentage of requests that tripped guardrails vs didn't trip guardrails in 5-minute windows

This dashboard focuses on the two most important operational metrics for monitoring
the agentic workflow system's usage and guardrail effectiveness.
"""

import sys
import urllib.parse
import webbrowser


def generate_simple_dashboard_url():
    """Generate a simple Prometheus dashboard URL with two key metrics."""

    # Base Prometheus URL
    base_url = "http://localhost:9090/graph"

    # Panel 1: Total workflow agent invocations every 5 minutes
    panel1_query = "sum(increase(workflow_analysis_total[5m]))"
    panel1_title = "Workflow Agent Invocations (5min)"

    # Panel 2: Guardrail trip percentage in 5-minute windows
    # This shows the percentage of requests that tripped any guardrail vs those that didn't
    panel2_query = 'sum(increase(guardrails_total{result="failed"}[5m])) / sum(increase(workflow_analysis_total[5m])) * 100'
    panel2_title = "Guardrail Trip Percentage (5min)"

    # Panel 3: Guardrail breakdown by type as percentage (5-minute windows)
    panel3_query = 'sum by (guardrail_type) (increase(guardrails_total{result="failed"}[5m])) / sum(increase(workflow_analysis_total[5m])) * 100'
    panel3_title = "Guardrail Trip Percentage by Type (5min)"

    # Panel 4: Requests that didn't trip guardrails (5-minute windows)
    panel4_query = '(sum(increase(workflow_analysis_total[5m])) - sum(increase(guardrails_total{result="failed"}[5m]))) / sum(increase(workflow_analysis_total[5m])) * 100'
    panel4_title = "Requests Without Guardrail Trips (5min)"

    # Create dashboard configuration
    dashboard_config = {
        "panels": [
            {
                "title": panel1_title,
                "expr": panel1_query,
                "type": "graph",
                "yAxis": {"label": "Total Invocations"},
            },
            {
                "title": panel2_title,
                "expr": panel2_query,
                "type": "graph",
                "yAxis": {"label": "Percentage", "max": 100},
            },
            {
                "title": panel3_title,
                "expr": panel3_query,
                "type": "graph",
                "yAxis": {"label": "Trip Count"},
            },
            {
                "title": panel4_title,
                "expr": panel4_query,
                "type": "graph",
                "yAxis": {"label": "Success Rate %", "max": 100},
            },
        ],
        "refresh": "5m",
        "timeRange": "1h",
    }

    # Generate the dashboard URL with multiple panels
    # Panel 1: Workflow Agent Invocations
    panel1_url = f"g0.expr={urllib.parse.quote(panel1_query)}&g0.tab=0"

    # Panel 2: Guardrail Trip Percentage
    panel2_url = f"g1.expr={urllib.parse.quote(panel2_query)}&g1.tab=0"

    # Panel 3: Guardrail Breakdown by Type
    panel3_url = f"g2.expr={urllib.parse.quote(panel3_query)}&g2.tab=0"

    # Panel 4: Workflow Success Rate
    panel4_url = f"g3.expr={urllib.parse.quote(panel4_query)}&g3.tab=0"

    # Common parameters for all panels
    common_params = "g0.range_input=1h&g0.step_input=5m&g1.range_input=1h&g1.step_input=5m&g2.range_input=1h&g2.step_input=5m&g3.range_input=1h&g3.step_input=5m"

    # Generate the complete dashboard URL
    dashboard_url = f"{base_url}?{panel1_url}&{panel2_url}&{panel3_url}&{panel4_url}&{common_params}"

    return dashboard_url, dashboard_config


def main():
    """Generate and display the simple dashboard URL."""
    # Check for --open flag
    open_browser = "--open" in sys.argv

    print("🔍 Generating Simple Prometheus Dashboard...")
    print("=" * 60)

    dashboard_url, config = generate_simple_dashboard_url()

    print("📊 SIMPLE DASHBOARD METRICS (4 PANELS):")
    print("=" * 60)
    print("Panel 1: 🤖 Workflow Agent Invocations (5min)")
    print("   - Shows total workflow analysis requests every 5 minutes")
    print("   - Query: sum(increase(workflow_analysis_total[5m]))")
    print()

    print("Panel 2: 🛡️ Guardrail Trip Percentage (5min)")
    print("   - Shows percentage of requests that tripped ANY guardrail")
    print(
        '   - Query: sum(increase(guardrails_total{result="failed"}[5m])) / sum(increase(workflow_analysis_total[5m])) * 100'
    )
    print()

    print("Panel 3: 🔍 Guardrail Trip Percentage by Type (5min)")
    print("   - Shows PERCENTAGE of requests that tripped each SPECIFIC guardrail type")
    print(
        "   - Breakdown by guardrail_type: describes_workflow_step, mentions_existing_app, etc."
    )
    print(
        "   - Each line shows what % of total requests tripped that specific guardrail"
    )
    print(
        '   - Query: sum by (guardrail_type) (increase(guardrails_total{result="failed"}[5m])) / sum(increase(workflow_analysis_total[5m])) * 100'
    )
    print()

    print("Panel 4: ✅ Requests Without Guardrail Trips (5min)")
    print("   - Shows percentage of requests that DIDN'T trip any guardrails")
    print("   - This is the complement of Panel 2 (100% - guardrail trip percentage)")
    print(
        '   - Query: (sum(increase(workflow_analysis_total[5m])) - sum(increase(guardrails_total{result="failed"}[5m]))) / sum(increase(workflow_analysis_total[5m])) * 100'
    )
    print()

    print("🌐 DASHBOARD URL:")
    print("=" * 60)
    print(dashboard_url)
    print()

    print("📋 DASHBOARD FEATURES:")
    print("=" * 60)
    print("• 4 separate panels showing different aspects of system health")
    print("• 5-minute time windows for operational monitoring")
    print("• Panel 2 + Panel 4 = 100% (guardrail trips + no guardrail trips)")
    print(
        "• Panel 3 shows PERCENTAGE breakdown by guardrail type (the key metric you wanted)"
    )
    print("• All metrics show percentages for easy comparison and understanding")
    print("• Focus on workflow agent usage and guardrail effectiveness")
    print("• Real-time monitoring of system health")
    print("• Simple, focused metrics for operational teams")
    print()

    if open_browser:
        print("🚀 OPENING DASHBOARD IN BROWSER:")
        print("=" * 60)
        print(f"Opening: {dashboard_url}")
        webbrowser.open(dashboard_url)
        print("✅ Dashboard opened in browser!")
    else:
        print("🚀 TO OPEN DASHBOARD:")
        print("=" * 60)
        print("1. Ensure Prometheus is running: make open-prometheus")
        print("2. Copy the URL above and paste in your browser")
        print("3. Or run: make open-simple-dashboard")
        print()


if __name__ == "__main__":
    main()
