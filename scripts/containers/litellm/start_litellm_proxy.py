#!/usr/bin/env python3
"""
Start LiteLLM Proxy Server

PURPOSE: Start the LiteLLM proxy server with LM Studio configuration
SCOPE: Reads config and starts proxy server
"""

import os
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def generate_litellm_config() -> str:
    """
    Generate LiteLLM config file with environment variable substitution.

    Returns:
        Path to temporary config file
    """
    lm_studio_host = os.getenv("LM_STUDIO_HOST", "192.168.1.168")
    lm_studio_port = os.getenv("LM_STUDIO_PORT", "1234")

    # If LM Studio is on host machine, use host.docker.internal
    # This works on Docker Desktop (Mac/Windows) and can be configured on Linux
    if lm_studio_host in ["localhost", "127.0.0.1"]:
        lm_studio_host = "host.docker.internal"

    api_base = f"http://{lm_studio_host}:{lm_studio_port}/v1"

    # Read the template config
    config_path = "/app/config/litellm_config.yaml"
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config_content = f.read()

    # Replace environment variable placeholder
    config_content = config_content.replace("${LM_STUDIO_API_BASE}", api_base)

    # Write to temporary file
    config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    config_file.write(config_content)
    config_file.close()

    return config_file.name


def wait_for_database(max_retries=30, delay=2):
    """Wait for PostgreSQL database to be ready using pg_isready."""
    import subprocess
    import time

    # Use pg_isready command (available in postgresql-client)
    # Database connection details from config
    config_path = "/app/config/litellm_config.yaml"
    if not os.path.exists(config_path):
        print("⚠️  Config file not found, skipping database check")
        return True

    with open(config_path, "r") as f:
        config_content = f.read()

    # Extract database URL (simple parsing)
    db_url = None
    import re

    for line in config_content.split("\n"):
        if "database_url" in line.lower() and ":" in line:
            match = re.search(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(\w+)", line)
            if match:
                user, password, host, port, dbname = match.groups()
                db_url = (host, port, user, dbname)
                break

    if not db_url:
        print("⚠️  Could not extract database URL from config, skipping database check")
        return True

    host, port, user, dbname = db_url
    print(f"🔍 Waiting for database to be ready at {host}:{port}...")

    for i in range(max_retries):
        try:
            # Use pg_isready to check database
            result = subprocess.run(
                ["pg_isready", "-h", host, "-p", port, "-U", user, "-d", dbname],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                print("✅ Database is ready")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            pass  # Continue to retry

        if i < max_retries - 1:
            print(
                f"   Attempt {i+1}/{max_retries}: Database not ready yet, waiting {delay}s..."
            )
            time.sleep(delay)
        else:
            print(f"⚠️  Database not ready after {max_retries} attempts")
            print("   Continuing anyway - LiteLLM will retry on startup")
            return False
    return False


def main():
    """Main entry point."""
    print("🚀 Starting LiteLLM proxy server...")
    print(
        f"📡 LM Studio: http://{os.getenv('LM_STUDIO_HOST', '192.168.1.168')}:{os.getenv('LM_STUDIO_PORT', '1234')}"
    )

    # Wait for database to be ready (LiteLLM needs it for Prisma initialization)
    # Note: docker-compose should ensure database is ready via depends_on,
    # but we check anyway to be safe
    try:
        wait_for_database()
    except Exception as e:
        print(f"⚠️  Error checking database: {e}, continuing anyway")

    # Generate config file
    config_file = generate_litellm_config()
    print(f"📋 Using config: {config_file}")

    # Start litellm proxy
    port = os.getenv("LITELLM_PORT", "4000")
    host = os.getenv("LITELLM_HOST", "0.0.0.0")

    print(f"🌐 Starting proxy on {host}:{port}")

    # Set environment variable for config file
    env = os.environ.copy()
    env["LITELLM_CONFIG_PATH"] = config_file

    # Try different methods to start litellm proxy
    try:
        # Method 1: Try litellm CLI directly
        try:
            # Use litellm with --config to start proxy server
            # LiteLLM will automatically generate Prisma client on first run if database_url is configured
            print(
                "🚀 Starting LiteLLM proxy server (Prisma client will be auto-generated if needed)..."
            )
            # Correct command: litellm --config <file> --port <port> --host <host>
            subprocess.run(
                ["litellm", "--config", config_file, "--port", port, "--host", host],
                check=True,
                env=env,
            )
        except FileNotFoundError:
            # Method 2: Try python -m litellm
            print(
                "🚀 Starting LiteLLM proxy server (Prisma client will be auto-generated if needed)..."
            )
            # Correct command: python -m litellm --config <file> --port <port> --host <host>
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "litellm",
                    "--config",
                    config_file,
                    "--port",
                    port,
                    "--host",
                    host,
                ],
                check=True,
                env=env,
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Method 3: Use litellm programmatically
        try:
            import litellm  # noqa: F401
            import uvicorn
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse
            from litellm import Router  # noqa: F401

            # Load config
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            # Create router
            router = Router(
                model_list=config.get("model_list", []),
                **config.get("router_settings", {}),
            )

            # Create FastAPI app
            app = FastAPI()

            @app.post("/v1/chat/completions")
            async def chat_completions(request: Request):
                data = await request.json()
                response = await router.acompletion(**data)
                return JSONResponse(content=response)

            @app.post("/v1/embeddings")
            async def embeddings(request: Request):
                data = await request.json()
                response = await router.aembedding(**data)
                return JSONResponse(content=response)

            @app.get("/health")
            async def health():
                return {"status": "healthy"}

            uvicorn.run(app, host=host, port=int(port), log_level="info")
        except Exception as e:
            print(f"❌ Error starting proxy: {e}")
            import traceback

            traceback.print_exc()
            os.unlink(config_file)
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down LiteLLM proxy server...")
        os.unlink(config_file)
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        os.unlink(config_file)
        sys.exit(1)


if __name__ == "__main__":
    main()
