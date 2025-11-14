# Prometheus Dashboard Queries

## Pre-configured Queries for Live Monitoring

## 🎯 **Business Intelligence Queries**

### **Workflow Analysis Performance**
1. **Analysis Success Rate**
   ```
   rate(workflow_analysis_total{status="success"}[5m]) / rate(workflow_analysis_total[5m])
   ```

2. **Average Analysis Duration**
   ```
   rate(workflow_analysis_duration_seconds_sum[5m]) / rate(workflow_analysis_duration_seconds_count[5m])
   ```

3. **Cost Per Analysis**
   ```
   rate(workflow_analysis_cost_usd_sum[1h]) / rate(workflow_analysis_total{status="success"}[1h])
   ```

4. **Apps Discovered Per Analysis**
   ```
   rate(workflow_analysis_apps_found_sum[5m]) / rate(workflow_analysis_total{status="success"}[5m])
   ```

5. **Actions Discovered Per Analysis**
   ```
   rate(workflow_analysis_actions_found_sum[5m]) / rate(workflow_analysis_total{status="success"}[5m])
   ```

### **Guardrails Quality Metrics**
6. **Guardrail Trip Rate by Type**
   ```
   rate(guardrails_trip_total[5m])
   ```

7. **Overall Guardrail Trip Rate**
   ```
   sum(rate(guardrails_trip_total[5m])) / sum(rate(guardrails_total[5m]))
   ```

8. **Guardrail Processing Performance**
   ```
   rate(guardrails_processing_duration_seconds_sum[5m]) / rate(guardrails_processing_duration_seconds_count[5m])
   ```

9. **Most Problematic Guardrail**
   ```
   topk(1, rate(guardrails_trip_total[1h]))
   ```

### **Judge Agent Quality Metrics**
10. **Judge Score Distribution**
    ```
    rate(judge_score_distribution[5m])
    ```

11. **Quality Pass Rate**
    ```
    rate(judge_score_distribution{score="pass"}[5m]) / rate(judge_score_distribution[5m])
    ```

12. **Quality Improvement Rate**
    ```
    rate(quality_improvement_rate[1h])
    ```

13. **Judge Processing Performance**
    ```
    rate(judge_processing_duration_seconds_sum[5m]) / rate(judge_processing_duration_seconds_count[5m])
    ```

### **Cost & Efficiency Metrics**
14. **Token Usage Efficiency**
    ```
    rate(workflow_analysis_output_tokens_sum[1h]) / rate(workflow_analysis_input_tokens_sum[1h])
    ```

15. **Cost Per Token**
    ```
    rate(workflow_analysis_cost_usd_sum[1h]) / (rate(workflow_analysis_input_tokens_sum[1h]) + rate(workflow_analysis_output_tokens_sum[1h]))
    ```

16. **Analysis Volume Growth**
    ```
    rate(workflow_analysis_total[1h])
    ```

### **System Health & Reliability**
17. **Overall System Success Rate**
    ```
    (rate(workflow_analysis_total{status="success"}[5m]) + rate(judge_score_distribution{score="pass"}[5m])) / 2
    ```

18. **Quality Trend (7-day)**
    ```
    rate(quality_score_distribution{score="pass"}[7d])
    ```

19. **Guardrail Effectiveness**
    ```
    rate(guardrails_total{result="passed"}[5m]) / rate(guardrails_total[5m])
    ```

20. **Error Rate by Component**
    ```
    rate(workflow_analysis_total{status="error"}[5m]) / rate(workflow_analysis_total[5m])
    ```

## 📊 **Operational Monitoring Queries**

### 📊 **Service Health & Availability**

1. **Service Status**
   ```
   up{job="agentic-api"}
   ```

2. **HTTP Request Rate** (from canary traffic)
   ```
   rate(http_requests_total[5m])
   ```

3. **HTTP Request Count**
   ```
   http_requests_total
   ```

### 🗄️ **Database Monitoring**

4. **Database Connection Success Rate**
   ```
   rate(database_connections_total{status="success"}[5m])
   ```

5. **Database Connection Failure Rate**
   ```
   rate(database_connections_total{status="failure"}[5m])
   ```

6. **Database Connection Duration (95th percentile)**
   ```
   histogram_quantile(0.95, rate(database_connection_duration_seconds_bucket[5m]))
   ```

7. **Database Connection Duration (50th percentile)**
   ```
   histogram_quantile(0.50, rate(database_connection_duration_seconds_bucket[5m]))
   ```

8. **Total Database Connections**
   ```
   database_connections_total
   ```

### 🚀 **Service Metrics**

9. **Service Start Count**
   ```
   service_starts_total
   ```

10. **Service Health Status**
    ```
    knowledge_agents:service_health
    ```

### 📈 **Aggregated Metrics (from recording rules)**

11. **HTTP Requests Per Second**
    ```
    knowledge_agents:http_requests_per_second
    ```

12. **Database Success Rate**
    ```
    knowledge_agents:db_connection_success_rate
    ```

13. **Database Failure Rate**
    ```
    knowledge_agents:db_connection_failure_rate
    ```

14. **Database Duration P95**
    ```
    knowledge_agents:db_connection_duration_p95
    ```

## 🎯 **Quick Dashboard Setup**

1. **Go to Prometheus** (http://localhost:9090)
2. **Click "Graph" tab**
3. **Paste any query above** into the query box
4. **Click "Execute"** to see the graph
5. **Set time range** to "Last 5 minutes" for real-time view

## 🚨 **Alerting Rules**

The following alerts are configured:
- **AgenticAPIDown**: Service is down for >1 minute
- **HighDatabaseFailureRate**: >10% failure rate for >2 minutes  
- **SlowDatabaseConnections**: 95th percentile >1 second for >3 minutes
- **NoHTTPRequests**: No requests for >2 minutes (canary down)

## 📊 **Recommended Dashboard Layout**

Create multiple browser tabs with these queries:
- Tab 1: `up{job="agentic-api"}` (Service Health)
- Tab 2: `rate(http_requests_total[5m])` (Request Rate)
- Tab 3: `rate(database_connections_total{status="success"}[5m])` (DB Success)
- Tab 4: `histogram_quantile(0.95, rate(database_connection_duration_seconds_bucket[5m]))` (DB Duration)
