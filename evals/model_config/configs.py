"""
Model configuration matrix for eval sweeps.

Each config defines a set of parameters to test against the summarization dataset.
The runner iterates over all configs × all test cases.
"""

SUMMARIZATION_CONFIGS = [
    # Baseline (current production config)
    {
        "name": "35b-a3b-t0.5-nothink",
        "model": "qwen3.5-35b-a3b",
        "temperature": 0.5,
        "enable_thinking": False,
        "max_tokens": 2000,
    },
    # Temperature sweep
    {
        "name": "35b-a3b-t0.3-nothink",
        "model": "qwen3.5-35b-a3b",
        "temperature": 0.3,
        "enable_thinking": False,
        "max_tokens": 2000,
    },
    {
        "name": "35b-a3b-t0.7-nothink",
        "model": "qwen3.5-35b-a3b",
        "temperature": 0.7,
        "enable_thinking": False,
        "max_tokens": 2000,
    },
    # Thinking mode comparison
    {
        "name": "35b-a3b-t0.5-think",
        "model": "qwen3.5-35b-a3b",
        "temperature": 0.5,
        "enable_thinking": True,
        "max_tokens": 4000,
    },
    # Model comparison (requires qwen3.5-9b loaded on LM Studio)
    {
        "name": "9b-t0.5-nothink",
        "model": "qwen3.5-9b",
        "temperature": 0.5,
        "enable_thinking": False,
        "max_tokens": 2000,
    },
]

LM_STUDIO_URL = "http://mac-studio.local:1234/v1"
LM_STUDIO_KEY = "lm-studio"
