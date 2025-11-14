# Model Onboarding Guide

This guide explains how to add and configure new models in the knowledge-agents system.

## Table of Contents

- [Model Types](#model-types)
- [Adding a New Model](#adding-a-new-model)
- [Model Configuration Fields](#model-configuration-fields)
- [Examples](#examples)
- [Testing Your Model](#testing-your-model)

## Model Types

The system supports three types of models:

### 1. **Completion Models** (`model_type: "completion"`)
- Uses **ChatCompletions API** via LiteLLM proxy
- Connects to local models (e.g., LM Studio) or remote providers
- **Use when**: You want to use local/self-hosted models or models via LiteLLM proxy
- **Example**: `lm_studio/qwen3-coder-30b`, `lm_studio/gpt-oss-20b`

### 2. **Embedding Models** (`model_type: "embedding"`)
- Uses **Embeddings API** via LiteLLM proxy
- Generates vector embeddings for semantic search
- **Use when**: You need to create embeddings for RAG/semantic search
- **Example**: `text-embedding-nomic-embed-text-v1.5`, `text-embedding-qwen3-embedding-8b`

### 3. **Responses Models** (`model_type: "responses"`)
- Uses **OpenAI Responses API** (native, not via proxy)
- Supports `HostedMCPTool` and advanced agent features
- **Use when**: You need MCP tool support or want to use OpenAI models directly
- **Example**: `gpt-4o`, `gpt-4`, `gpt-4-turbo`
- **Note**: Models starting with `lm_studio/gpt` are automatically treated as responses models

## Adding a New Model

### Step 1: Add Model to LiteLLM Config

**For completion and embedding models**, add your model to `config/litellm_config.yaml`:

```yaml
model_list:
  # Your Model Name - Brief description
  # USE WHEN: When to use this model
  # Best for: What this model is best for
  - model_name: your-model-name
    litellm_params:
      model: actual/model/name
      api_base: ${LM_STUDIO_API_BASE}  # or your provider's API base
      api_key: "your-api-key"  # or "lm-studio" for LM Studio
```

**Note**: Models are automatically loaded from `litellm_config.yaml`. The system will:
- Auto-detect model type (completion vs embedding) based on model name
- Extract descriptions from YAML comments
- Configure appropriate API types

### Step 2: Add Responses API Model (if needed)

**For Responses API models** (OpenAI native, supports HostedMCPTool), add to `src/knowledge_agents/config/model_config.py`:

```yaml
model_list:
  - model_name: your-model-name
    litellm_params:
      model: actual/model/name
      api_base: ${LM_STUDIO_API_BASE}  # or your provider's API base
      api_key: "your-api-key"  # or "lm-studio" for LM Studio
```

```python
RESPONSES_API_MODELS: Dict[str, Dict[str, Any]] = {
    # ... existing models ...
    "gpt-4o-mini": {
        "openai_model": "gpt-4o-mini",
        "description": "GPT-4o Mini - Smaller, faster version of GPT-4o",
        "use_when": "Fast responses with GPT-4o quality, when HostedMCPTool is needed",
        "best_for": "Cost-effective production applications with MCP tools",
        "model_type": "responses",
        "api_type": "responses",
        "requires_responses_api": True,
        "requires_openai_api": True,
    },
}
```

**Note**: Responses API models are NOT in `litellm_config.yaml` because they use OpenAI API directly, not via LiteLLM proxy.

### Step 3: Update Settings (if needed)

If you want to set your model as the default, update environment variables or `config/env.example`:

```bash
# For completion models
LITELLM_PROXY_COMPLETION_MODEL=your-model-name

# For embedding models
LITELLM_PROXY_EMBEDDING_MODEL=your-model-name

# For responses models
OPENAI_RESPONSES_MODEL=your-model-name
USE_RESPONSES_API_FOR_MCP_TOOLS=true
```

## Model Configuration Fields

### Required Fields

- **`model_type`**: One of `"completion"`, `"embedding"`, or `"responses"`
- **`description`**: Human-readable description of the model
- **`use_when`**: When to use this model
- **`best_for`**: What this model excels at

### API-Specific Fields

#### For Completion/Embedding Models (LiteLLM Proxy)

- **`litellm_model`**: The actual model identifier used by LiteLLM
- **`api_type`**: `"chat_completions"` or `"embeddings"`
- **`requires_responses_api`**: `False` (default)

#### For Responses Models (OpenAI Native)

- **`openai_model`**: The OpenAI model identifier (e.g., `"gpt-4o"`)
- **`api_type`**: `"responses"`
- **`requires_responses_api`**: `True`
- **`requires_openai_api`**: `True` (must use OpenAI API directly)

### Optional Fields

- **`requires_responses_api`**: Auto-enables Responses API for this model
- **`requires_openai_api`**: Indicates model must use OpenAI API (not proxy)

## Examples

### Example 1: Adding a Local LM Studio Model

**In `config/litellm_config.yaml`:**
```yaml
model_list:
  # My Custom Model - Custom local model
  # USE WHEN: Custom tasks, local development
  # Best for: Local testing and development
  - model_name: lm_studio/my-custom-model
    litellm_params:
      model: lm_studio/my/custom-model
      api_base: ${LM_STUDIO_API_BASE}
      api_key: "lm-studio"
```

**That's it!** The model will be automatically loaded and available. No need to edit `model_config.py`.

### Example 2: Adding an OpenAI Responses Model

```python
"gpt-4o-mini": {
    "openai_model": "gpt-4o-mini",
    "description": "GPT-4o Mini - Smaller, faster version of GPT-4o",
    "use_when": "Fast responses with GPT-4o quality, when HostedMCPTool is needed",
    "best_for": "Cost-effective production applications with MCP tools",
    "model_type": "responses",
    "api_type": "responses",
    "requires_responses_api": True,
    "requires_openai_api": True,
}
```

### Example 3: Adding an Embedding Model

**In `config/litellm_config.yaml`:**
```yaml
model_list:
  # OpenAI Text Embedding 3 Small - Efficient embeddings
  # USE WHEN: Generating embeddings for semantic search
  # Best for: Vector databases, RAG systems, cost-effective embeddings
  - model_name: text-embedding-3-small
    litellm_params:
      model: text-embedding-3-small
      api_base: https://api.openai.com/v1
      api_key: ${OPENAI_API_KEY}
```

**That's it!** The model will be automatically detected as an embedding model (based on "embedding" in the name).

### Example 4: LM Studio GPT Model (Auto-Treated as Responses)

Models starting with `lm_studio/gpt` are automatically treated as responses models:

**In `config/litellm_config.yaml`:**
```yaml
model_list:
  # GPT-4 via LM Studio - Local GPT-4 access
  # USE WHEN: Local GPT-4 access
  # Best for: Local development with GPT-4
  - model_name: lm_studio/gpt-4
    litellm_params:
      model: lm_studio/openai/gpt-4
      api_base: ${LM_STUDIO_API_BASE}
      api_key: "lm-studio"
```

**Note**: This model will be auto-detected as a responses model by `is_responses_model()` function, even though it's loaded from `litellm_config.yaml`.

## Testing Your Model

### 1. Test Model Configuration

```python
from knowledge_agents.config.model_config import get_model_config, is_responses_model

# Check if model is configured
config = get_model_config("your-model-name")
print(config)

# Check if it requires Responses API
if is_responses_model("your-model-name"):
    print("Model requires Responses API")
```

### 2. Test Model Loading

```python
from knowledge_agents.utils.model_utils import get_default_litellm_model
from knowledge_agents.config.api_config import Settings

settings = Settings()
model = get_default_litellm_model(settings, model="your-model-name")
print(f"Model type: {type(model)}")
```

### 3. Test API Call

Use the test script:

```bash
# For completion models
python scripts/call_litellm_model.py --model your-model-name --prompt "Hello"

# For embedding models
python scripts/call_litellm_model.py --model your-model-name --embedding "Hello world"
```

### 4. Integration Test

Run the integration tests:

```bash
make test-note-query-validate
```

## Common Issues

### Issue: Model not found

**Solution**: Ensure model name matches exactly in both `model_config.py` and `litellm_config.yaml`

### Issue: Responses API not working

**Solution**: 
- Check `requires_responses_api: True` in model config
- Ensure `requires_openai_api: True` for OpenAI models
- Verify OpenAI API key is set correctly

### Issue: Model works but HostedMCPTool fails

**Solution**: 
- Ensure model has `model_type: "responses"` and `requires_responses_api: True`
- Check that `use_responses_api_for_mcp_tools=True` in settings
- Verify model supports Responses API (OpenAI models do, local models may not)

## Quick Reference

| Model Type | API Type | Proxy? | MCP Tools? | Config File |
|------------|----------|--------|------------|-------------|
| Completion | ChatCompletions | Yes | No | `config/litellm_config.yaml` |
| Embedding | Embeddings | Yes | No | `config/litellm_config.yaml` |
| Responses | Responses | No* | Yes | `src/knowledge_agents/config/model_config.py` |

*Responses models use OpenAI API directly, not via proxy (unless using `lm_studio/gpt*` which may use proxy)

## Key Points

1. **Completion and Embedding Models**: Add to `config/litellm_config.yaml` only
   - Models are automatically loaded from YAML
   - Model type is auto-detected based on name (embedding models have "embedding" in name)
   - No need to edit `model_config.py`

2. **Responses API Models**: Add to `src/knowledge_agents/config/model_config.py` in `RESPONSES_API_MODELS`
   - These use OpenAI API directly (not LiteLLM proxy)
   - Required for HostedMCPTool support

3. **Model Detection**:
   - Models with "embedding" or "embed" in name → embedding model
   - Models starting with "lm_studio/gpt" → treated as responses model
   - All other models → completion model

## Next Steps

After adding your model:

1. ✅ Add model to `config/litellm_config.yaml` (completion/embedding) OR `model_config.py` (responses)
2. ✅ Restart services to reload config
3. ✅ Test model loading: `python -c "from knowledge_agents.config.model_config import list_models; print(list_models())"`
4. ✅ Test API calls
5. ✅ Run integration tests
6. ✅ Update documentation if model has special requirements

For questions or issues, see `DEVELOPMENT.md` or check existing model configurations for reference.

