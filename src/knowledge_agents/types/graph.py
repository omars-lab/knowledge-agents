"""
Types for graph building operations.
"""
from typing import List, Optional, Dict, Any, Annotated

from pydantic import BaseModel, Field, ConfigDict
from pydantic.json_schema import JsonSchemaValue, WithJsonSchema
from pydantic_core import core_schema


class Entity(BaseModel):
    """Represents an entity extracted from notes."""
    
    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., description="Name of the entity")
    type: str = Field(
        ...,
        description="Type of entity: Person, Project, Topic, Concept, Date, Location, or other relevant type",
    )
    properties: Annotated[
        Dict[str, Any],
        WithJsonSchema({
            'type': 'object',
            'additionalProperties': False,
            'properties': {}
        })
    ] = Field(
        default_factory=dict,
        description="Additional properties for the entity (empty dict by default)",
    )
    
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler
    ) -> JsonSchemaValue:
        """Custom JSON schema generator to enforce strict schema."""
        json_schema = handler(core_schema)
        # Ensure additionalProperties is False for the entire model
        if isinstance(json_schema, dict):
            json_schema['additionalProperties'] = False
            # Also set it for the properties field
            if 'properties' in json_schema and 'properties' in json_schema['properties']:
                json_schema['properties']['properties']['additionalProperties'] = False
        return json_schema


class Relationship(BaseModel):
    """Represents a relationship between entities."""
    
    model_config = ConfigDict(extra='forbid')

    from_entity: str = Field(..., description="Name of the source entity")
    to_entity: str = Field(..., description="Name of the target entity")
    type: str = Field(
        ...,
        description="Type of relationship: RELATED_TO, WORKS_ON, MENTIONS, REFERENCES, or other relevant type",
    )
    properties: Annotated[
        Dict[str, Any],
        WithJsonSchema({
            'type': 'object',
            'additionalProperties': False,
            'properties': {}
        })
    ] = Field(
        default_factory=dict,
        description="Additional properties for the relationship (empty dict by default)",
    )
    
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler
    ) -> JsonSchemaValue:
        """Custom JSON schema generator to enforce strict schema."""
        json_schema = handler(core_schema)
        # Ensure additionalProperties is False for the entire model
        if isinstance(json_schema, dict):
            json_schema['additionalProperties'] = False
            # Also set it for the properties field
            if 'properties' in json_schema and 'properties' in json_schema['properties']:
                json_schema['properties']['properties']['additionalProperties'] = False
        return json_schema


class GraphBuilderAgentOutput(BaseModel):
    """
    Structured output from the GraphBuilderAgent.
    
    This Pydantic model defines the expected output format from the agent,
    forcing structured responses with entities, relationships, and insights.
    """
    
    model_config = ConfigDict(extra='forbid')
    
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler
    ) -> JsonSchemaValue:
        """Custom JSON schema generator to enforce strict schema."""
        json_schema = handler(core_schema)
        # Ensure additionalProperties is False for the entire model
        if isinstance(json_schema, dict):
            json_schema['additionalProperties'] = False
        return json_schema

    entities: List[Entity] = Field(
        default_factory=list,
        description="List of entities extracted from the note",
    )
    relationships: List[Relationship] = Field(
        default_factory=list,
        description="List of relationships between entities",
    )
    insights: List[str] = Field(
        default_factory=list,
        description="Key insights or facts extracted from the note",
    )

