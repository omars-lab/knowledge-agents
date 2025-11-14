#!/usr/bin/env python3
"""
Canary Monitoring Service

PURPOSE: Continuous monitoring of the agentic API with random payloads
SCOPE: Random workflow descriptions, guardrail validation, system health monitoring

This service runs continuously and:
- Generates random valid/invalid workflow descriptions
- Tests the /api/v1/analyze endpoint
- Validates guardrail effectiveness
- Monitors system health and performance
- Logs results for monitoring and alerting
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Configure logging using centralized config
from knowledge_agents.config.logging_config import setup_logging

# Set log level via environment variable if needed
if os.getenv("CANARY_DEBUG", "false").lower() == "true":
    os.environ["LOG_LEVEL"] = "DEBUG"

setup_logging()
logger = logging.getLogger(__name__)


class CanaryMonitor:
    """Continuous canary monitoring service"""

    def __init__(self, api_url: str = "http://agentic-api:8000", interval: int = 30):
        self.api_url = api_url
        self.interval = interval
        self.session: Optional[aiohttp.ClientSession] = None

        # Valid apps and actions from bootstrap data
        self.valid_apps = [
            "Gmail",
            "Slack",
            "Google Sheets",
            "Trello",
            "Salesforce",
            "HubSpot",
            "Knowledge",
        ]

        self.valid_actions = {
            "Gmail": ["send_email", "read_email", "search_emails", "delete_email"],
            "Slack": [
                "send_message",
                "read_messages",
                "send_notification",
                "create_channel",
            ],
            "Google Sheets": [
                "create_spreadsheet",
                "read_data",
                "write_data",
                "update_cell",
            ],
            "Trello": ["create_card", "move_card", "add_comment", "create_board"],
            "Salesforce": [
                "create_lead",
                "update_contact",
                "create_opportunity",
                "send_email",
            ],
            "HubSpot": [
                "create_contact",
                "update_contact",
                "create_deal",
                "log_activity",
            ],
            "Knowledge": [
                "trigger_workflow",
                "create_workflow",
                "test_workflow",
                "pause_workflow",
            ],
        }

        self.invalid_apps = ["NonExistentApp", "FakeApp", "MadeUpApp", "UnknownApp"]
        self.invalid_actions = [
            "invalid_action",
            "fake_action",
            "unknown_action",
            "bad_action",
        ]

        # Workflow templates
        self.workflow_templates = [
            "When {trigger}, {action} using {app}",
            "If {condition}, then {action} with {app}",
            "Whenever {event} happens, {action} via {app}",
            "When a {entity} is {action_verb}, {action} using {app}",
            "If {condition} occurs, {action} through {app}",
            "When {trigger_event}, automatically {action} with {app}",
        ]

        self.triggers = [
            "a new lead is created",
            "a deal is closed",
            "a task is completed",
            "a message is received",
            "a file is uploaded",
            "a user signs up",
            "an order is placed",
            "a payment is processed",
            "a meeting is scheduled",
        ]

        self.conditions = [
            "a customer places an order",
            "a lead score increases",
            "a deadline approaches",
            "a status changes",
            "a threshold is reached",
            "a condition is met",
        ]

        self.entities = [
            "lead",
            "contact",
            "deal",
            "task",
            "message",
            "file",
            "user",
            "order",
            "payment",
        ]

        self.action_verbs = [
            "created",
            "updated",
            "closed",
            "completed",
            "received",
            "uploaded",
            "signed up",
        ]

    async def start(self):
        """Start the canary monitoring service"""
        logger.info(
            f"🐦 Starting canary monitoring service (interval: {self.interval}s)"
        )

        async with aiohttp.ClientSession() as session:
            self.session = session

            while True:
                try:
                    await self._run_canary_cycle()
                except Exception as e:
                    logger.error(f"❌ Canary cycle failed: {e}")

                await asyncio.sleep(self.interval)

    async def _run_canary_cycle(self):
        """Run a single canary monitoring cycle"""
        logger.info("🔄 Running canary monitoring cycle...")

        try:
            # Test valid workflow
            await self._test_valid_workflow()

            # Test invalid workflow
            await self._test_invalid_workflow()

            # Test edge case
            await self._test_edge_case()

            logger.info("✅ Canary cycle completed")
        except Exception as e:
            logger.error(f"❌ Canary cycle failed: {e}")
            logger.exception("Full traceback:")

    async def _test_valid_workflow(self):
        """Test with a random valid workflow"""
        description = self._generate_valid_workflow()
        logger.debug(f"🧪 Testing valid workflow: {description}")

        try:
            response = await self._make_request(description)
            if response:
                logger.debug(f"📊 Response data: {response}")

                # Check for workflow detection at the top level of response
                if response.get("workflow_step_detected", False):
                    logger.info(f"✅ Valid workflow succeeded: {description[:50]}...")
                elif response.get("ambiguity_detected", False):
                    logger.info(f"⚠️ Valid workflow ambiguous: {description[:50]}...")
                else:
                    logger.warning(
                        f"❌ Valid workflow failed unexpectedly: {description[:50]}..."
                    )
                    logger.debug(f"🔍 Full response: {response}")
            else:
                logger.error(f"❌ Valid workflow test failed: No response received")
        except Exception as e:
            logger.error(f"❌ Valid workflow test failed: {e}")
            logger.exception("Full traceback:")

    async def _test_invalid_workflow(self):
        """Test with a random invalid workflow"""
        description = self._generate_invalid_workflow()
        logger.debug(f"🧪 Testing invalid workflow: {description}")

        try:
            response = await self._make_request(description)
            if response:
                logger.debug(f"📊 Response data: {response}")

                # Check if guardrails were tripped (any guardrail failure)
                guardrails_tripped = response.get("guardrails_tripped", [])
                workflow_detected = response.get("workflow_step_detected", False)

                if not workflow_detected and guardrails_tripped:
                    logger.info(
                        f"✅ Invalid workflow correctly rejected: {description[:50]}..."
                    )
                elif not workflow_detected and not guardrails_tripped:
                    logger.info(
                        f"✅ Invalid workflow rejected (no guardrails needed): {description[:50]}..."
                    )
                else:
                    logger.warning(
                        f"❌ Invalid workflow not rejected: {description[:50]}..."
                    )
                    logger.debug(
                        f"🔍 Guardrails tripped: {guardrails_tripped}, Workflow detected: {workflow_detected}"
                    )
            else:
                logger.error(f"❌ Invalid workflow test failed: No response received")
        except Exception as e:
            logger.error(f"❌ Invalid workflow test failed: {e}")
            logger.exception("Full traceback:")

    async def _test_edge_case(self):
        """Test with an edge case scenario"""
        edge_cases = [
            "",  # Empty input
            "What's the weather?",  # Non-workflow
            "Use NonExistentApp to send an email",  # Invalid app
            "Use Gmail to invalid_action",  # Invalid action
        ]

        description = random.choice(edge_cases)
        logger.debug(f"🧪 Testing edge case: '{description}'")

        try:
            response = await self._make_request(description)
            if response:
                logger.debug(f"📊 Edge case response: {response}")
                logger.info(
                    f"✅ Edge case handled: {description[:50]}... -> {response.get('workflow_step_detected', False)}"
                )
            else:
                logger.error(f"❌ Edge case test failed: No response received")
        except Exception as e:
            logger.error(f"❌ Edge case test failed: {e}")
            logger.exception("Full traceback:")

    async def _make_request(self, description: str) -> Optional[Dict[str, Any]]:
        """Make a request to the API"""
        logger.debug(f"🌐 Making API request to {self.api_url}/api/v1/analyze")
        logger.debug(f"📝 Request payload: {{'description': '{description}'}}")

        try:
            async with self.session.post(
                f"{self.api_url}/api/v1/analyze",
                json={"description": description},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                logger.debug(f"📡 Response status: {response.status}")

                if response.status == 200:
                    response_data = await response.json()
                    logger.debug(f"📊 Response data: {response_data}")
                    return response_data
                else:
                    response_text = await response.text()
                    logger.error(f"❌ API request failed with status {response.status}")
                    logger.error(f"📄 Response body: {response_text}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"❌ API request timed out after 30 seconds")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"❌ API request client error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ API request failed: {e}")
            logger.exception("Full traceback:")
            return None

    def _generate_valid_workflow(self) -> str:
        """Generate a random valid workflow description"""
        template = random.choice(self.workflow_templates)
        app = random.choice(self.valid_apps)
        action = random.choice(self.valid_actions[app])

        if "{trigger}" in template:
            trigger = random.choice(self.triggers)
            return template.format(trigger=trigger, action=action, app=app)
        elif "{condition}" in template:
            condition = random.choice(self.conditions)
            return template.format(condition=condition, action=action, app=app)
        elif "{entity}" in template:
            entity = random.choice(self.entities)
            action_verb = random.choice(self.action_verbs)
            return template.format(
                entity=entity, action_verb=action_verb, action=action, app=app
            )
        elif "{trigger_event}" in template:
            trigger_event = random.choice(self.triggers)
            return template.format(trigger_event=trigger_event, action=action, app=app)
        elif "{event}" in template:
            event = random.choice(self.triggers)
            return template.format(event=event, action=action, app=app)
        else:
            return template.format(action=action, app=app)

    def _generate_invalid_workflow(self) -> str:
        """Generate a random invalid workflow description"""
        invalid_type = random.choice(
            [
                "non_workflow",
                "invalid_app",
                "invalid_action",
                "private_app",
                "ambiguous",
            ]
        )

        if invalid_type == "non_workflow":
            return random.choice(
                [
                    "What's the weather like today?",
                    "I want to order pizza",
                    "How do I cook pasta?",
                    "Tell me a joke",
                    "What time is it?",
                ]
            )
        elif invalid_type == "invalid_app":
            app = random.choice(self.invalid_apps)
            action = random.choice(["send_email", "create_contact", "send_message"])
            return f"When a new lead is created in {app}, {action}"
        elif invalid_type == "invalid_action":
            app = random.choice(self.valid_apps)
            action = random.choice(self.invalid_actions)
            return f"Use {app} to {action}"
        elif invalid_type == "private_app":
            return "Use Private App to send an email"
        elif invalid_type == "ambiguous":
            return random.choice(
                [
                    "When a new lead is created, send an email",
                    "Add a row to my sheet",
                    "Send a message when I'm feeling slack",
                ]
            )


async def main():
    """Main entry point"""
    api_url = "http://agentic-api:8000"
    interval = int(os.environ.get("CANARY_INTERVAL", "30"))  # Default 30 seconds

    monitor = CanaryMonitor(api_url=api_url, interval=interval)
    await monitor.start()


if __name__ == "__main__":
    import os

    asyncio.run(main())
