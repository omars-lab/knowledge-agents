# Model Config Eval Report

Results: `sweep_20260324_032915.json`

| Config                         |  conciseness |    non_empty |    Latency |  Overall |
|-------------------------------|--------------|--------------|------------|----------|
| 35b-a3b-t0.5-nothink           |         0.38 |         0.90 |    16773ms |    0.64 |
| 35b-a3b-t0.3-nothink           |         0.38 |         0.90 |    14129ms |    0.64 |
| 35b-a3b-t0.7-nothink           |         0.38 |         0.90 |    15050ms |    0.64 |
| 35b-a3b-t0.5-think             |         0.40 |         0.90 |    16629ms |    0.65 |
| 9b-t0.5-nothink                |         0.41 |         1.00 |    17216ms |    0.71 |

## Per-Config Details

### 35b-a3b-t0.5-nothink
- Cases: 10/10 (0 errors)
- Avg latency: 16773ms
- Avg scores: {
  "conciseness": 0.3769635964379267,
  "non_empty": 0.9,
  "overall": 0.6384817982189633
}

### 35b-a3b-t0.3-nothink
- Cases: 10/10 (0 errors)
- Avg latency: 14129ms
- Avg scores: {
  "conciseness": 0.3798244599239773,
  "non_empty": 0.9,
  "overall": 0.6399122299619886
}

### 35b-a3b-t0.7-nothink
- Cases: 10/10 (0 errors)
- Avg latency: 15050ms
- Avg scores: {
  "conciseness": 0.37992648216564695,
  "non_empty": 0.9,
  "overall": 0.6399632410828235
}

### 35b-a3b-t0.5-think
- Cases: 10/10 (0 errors)
- Avg latency: 16629ms
- Avg scores: {
  "conciseness": 0.3972778803161578,
  "non_empty": 0.9,
  "overall": 0.6486389401580789
}

### 9b-t0.5-nothink
- Cases: 10/10 (0 errors)
- Avg latency: 17216ms
- Avg scores: {
  "conciseness": 0.41348239492275124,
  "non_empty": 1.0,
  "overall": 0.7067411974613756
}
