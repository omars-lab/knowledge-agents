# Verifying Responses API Usage

This guide explains how to verify if your agents are using the Responses API.

## Quick Check

### 1. Check Logs

When an agent starts, look for log messages indicating the model type:

```
Agent model configuration: API=responses, ModelClass=OpenAIResponsesModel, SupportsMCPTools=True
```

vs.

```
Agent model configuration: API=chat_completions, ModelClass=LitellmModel, SupportsMCPTools=False
```

### 2. Check Model Instance Type

You can programmatically check if a model instance is using Responses API:

```python
from knowledge_agents.utils.model_utils import is_using_responses_api, get_model_type_info
from knowledge_agents.utils.model_utils import get_default_litellm_model
from knowledge_agents.config.api_config import Settings

settings = Settings()
model = get_default_litellm_model(settings)

# Check if using Responses API
if is_using_responses_api(model):
    print("✅ Using Responses API (OpenAIResponsesModel)")
else:
    print("❌ Using ChatCompletions API (LitellmModel)")

# Get detailed info
info = get_model_type_info(model)
print(f"API Type: {info['api_type']}")
print(f"Model Class: {info['model_class']}")
print(f"Supports MCP Tools: {info['supports_mcp_tools']}")
```

### 3. Check Model Configuration

Check if a model is configured to use Responses API:

```python
from knowledge_agents.config.model_config import is_responses_model, get_model_config

model_name = "gpt-4o"  # or your model name

# Check if model requires Responses API
if is_responses_model(model_name):
    print(f"✅ {model_name} requires Responses API")
    config = get_model_config(model_name)
    print(f"   Model type: {config.get('model_type')}")
    print(f"   Requires Responses API: {config.get('requires_responses_api')}")
else:
    print(f"❌ {model_name} uses ChatCompletions API")
```

## When Responses API is Used

The Responses API is used when:

1. **Explicit flag**: `use_responses_api_for_mcp_tools=True` in settings
2. **Model configuration**: Model has `requires_responses_api: True` in `model_config.py`
3. **Model type**: Model has `model_type: "responses"` in `model_config.py`
4. **Model name pattern**: Model name starts with `lm_studio/gpt` (auto-detected)

## Verification Checklist

- [ ] Check startup logs for "Agent model configuration" message
- [ ] Verify `ModelClass=OpenAIResponsesModel` in logs
- [ ] Verify `API=responses` in logs
- [ ] Verify `SupportsMCPTools=True` if using HostedMCPTool
- [ ] Check that model name matches a Responses API model in config
- [ ] Verify `use_responses_api_for_mcp_tools` setting if using MCP tools

## Common Issues

### Issue: Model shows as ChatCompletions but should be Responses

**Check:**
1. Is `use_responses_api_for_mcp_tools=True` in settings?
2. Is the model configured with `requires_responses_api: True`?
3. Does the model have `model_type: "responses"`?
4. For `lm_studio/gpt*` models, are they being auto-detected?

**Solution:**
- Update model config in `model_config.py`
- Set `use_responses_api_for_mcp_tools=True` in environment or settings
- Restart the service

### Issue: HostedMCPTool not working

**Check:**
1. Is the model using Responses API? (check logs)
2. Is `SupportsMCPTools=True` in logs?
3. Is `HostedMCPTool` being added to agent tools?

**Solution:**
- Ensure `use_responses_api_for_mcp_tools=True`
- Verify model supports Responses API (OpenAI models do, local models may not)
- Check that `tidy-mcp` service is running and accessible

## Debugging

### Enable Debug Logging

Set log level to DEBUG to see detailed model creation logs:

```python
import logging
logging.getLogger("knowledge_agents.utils.model_utils").setLevel(logging.DEBUG)
logging.getLogger("knowledge_agents.agents.note_query_agent").setLevel(logging.DEBUG)
```

### Test Model Creation

```python
from knowledge_agents.utils.model_utils import get_default_litellm_model, get_model_type_info
from knowledge_agents.config.api_config import Settings

settings = Settings()
settings.use_responses_api_for_mcp_tools = True  # Force Responses API

model = get_default_litellm_model(settings)
info = get_model_type_info(model)
print(info)
```

## Summary

- **Responses API**: `OpenAIResponsesModel` class, `API=responses`, supports HostedMCPTool
- **ChatCompletions API**: `LitellmModel` class, `API=chat_completions`, uses LiteLLM proxy

Check logs on startup to see which API is being used.

