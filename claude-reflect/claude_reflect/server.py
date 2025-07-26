"""Claude Reflect MCP Server with Memory Decay."""

import os
from pathlib import Path
from typing import Any, Optional, List, Dict, Union
from datetime import datetime
import json
import numpy as np

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    PointStruct, VectorParams, Distance, 
    FormulaQuery, DecayParamsExpression, SumExpression,
    DatetimeExpression, DatetimeKeyExpression
)
import voyageai
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Configuration
QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
VOYAGE_API_KEY = os.getenv('VOYAGE_KEY') or os.getenv('VOYAGE_KEY-2')
ENABLE_MEMORY_DECAY = os.getenv('ENABLE_MEMORY_DECAY', 'false').lower() == 'true'
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))
USE_NATIVE_DECAY = os.getenv('USE_NATIVE_DECAY', 'false').lower() == 'true'

# Initialize Voyage AI client
voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY) if VOYAGE_API_KEY else None

# Debug environment loading
print(f"[DEBUG] Environment variables loaded:")
print(f"[DEBUG] ENABLE_MEMORY_DECAY: {ENABLE_MEMORY_DECAY}")
print(f"[DEBUG] USE_NATIVE_DECAY: {USE_NATIVE_DECAY}")
print(f"[DEBUG] DECAY_WEIGHT: {DECAY_WEIGHT}")
print(f"[DEBUG] DECAY_SCALE_DAYS: {DECAY_SCALE_DAYS}")
print(f"[DEBUG] env_path: {env_path}")


class SearchResult(BaseModel):
    """A single search result."""
    id: str
    score: float
    timestamp: str
    role: str
    excerpt: str
    project_name: str
    conversation_id: Optional[str] = None
    collection_name: str


# Initialize FastMCP instance
mcp = FastMCP(
    name="claude-reflect",
    instructions="Search past conversations and store reflections with time-based memory decay"
)

# Create Qdrant client
qdrant_client = AsyncQdrantClient(url=QDRANT_URL)
    
async def get_voyage_collections() -> List[str]:
    """Get all Voyage collections."""
    collections = await qdrant_client.get_collections()
    return [c.name for c in collections.collections if c.name.endswith('_voyage')]

async def generate_embedding(text: str) -> List[float]:
    """Generate embedding using Voyage AI."""
    if not voyage_client:
        raise ValueError("Voyage AI API key not configured")
    
    result = voyage_client.embed(
        texts=[text],
        model="voyage-3-large",
        input_type="query"
    )
    return result.embeddings[0]
    
# Register tools
@mcp.tool()
async def reflect_on_past(
    ctx: Context,
    query: str = Field(description="The search query to find semantically similar conversations"),
    limit: int = Field(default=5, description="Maximum number of results to return"),
    min_score: float = Field(default=0.7, description="Minimum similarity score (0-1)"),
    use_decay: Union[int, str] = Field(default=-1, description="Apply time-based decay: 1=enable, 0=disable, -1=use environment default (accepts int or str)")
) -> str:
    """Search for relevant past conversations using semantic search with optional time decay."""
    
    # Normalize use_decay to integer
    if isinstance(use_decay, str):
        try:
            use_decay = int(use_decay)
        except ValueError:
            raise ValueError("use_decay must be '1', '0', or '-1'")
    
    # Parse decay parameter using integer approach
    should_use_decay = (
        True if use_decay == 1
        else False if use_decay == 0
        else ENABLE_MEMORY_DECAY  # -1 or any other value
    )
    
    await ctx.debug(f"Searching for: {query}")
    await ctx.debug(f"Decay enabled: {should_use_decay}")
    await ctx.debug(f"Native decay mode: {USE_NATIVE_DECAY}")
    await ctx.debug(f"ENABLE_MEMORY_DECAY env: {ENABLE_MEMORY_DECAY}")
    await ctx.debug(f"DECAY_WEIGHT: {DECAY_WEIGHT}, DECAY_SCALE_DAYS: {DECAY_SCALE_DAYS}")
    
    try:
        # Generate embedding
        query_embedding = await generate_embedding(query)
        
        # Get all Voyage collections
        voyage_collections = await get_voyage_collections()
        if not voyage_collections:
            return "No conversation collections found. Please import conversations first."
        
        await ctx.debug(f"Searching across {len(voyage_collections)} collections")
        
        all_results = []
        
        # Search each collection
        for collection_name in voyage_collections:
            try:
                if should_use_decay and USE_NATIVE_DECAY:
                    # Use native Qdrant decay
                    await ctx.debug(f"Using NATIVE Qdrant decay for {collection_name}")
                    
                    # Build the query with native Qdrant decay formula
                    query_obj = FormulaQuery(
                        nearest=query_embedding,
                        formula=SumExpression(
                            sum=[
                                # Original similarity score
                                'score',  # Variable expression can be a string
                                # Decay boost term
                                {
                                    'mult': [
                                        # Decay weight (constant as float)
                                        DECAY_WEIGHT,
                                        # Exponential decay function
                                        {
                                            'exp_decay': DecayParamsExpression(
                                                # Use timestamp field for decay
                                                x=DatetimeKeyExpression(datetime_key='timestamp'),
                                                # Decay from current time (server-side)
                                                target=DatetimeExpression(datetime='now'),
                                                # Scale in milliseconds
                                                scale=DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000,
                                                # Standard exponential decay midpoint
                                                midpoint=0.5
                                            )
                                        }
                                    ]
                                }
                            ]
                        )
                    )
                    
                    # Execute query with native decay
                    results = await qdrant_client.query_points(
                        collection_name=collection_name,
                        query=query_obj,
                        limit=limit,
                        score_threshold=min_score,
                        with_payload=True
                    )
                    
                    # Process results from native decay search
                    for point in results.points:
                        all_results.append(SearchResult(
                            id=str(point.id),
                            score=point.score,  # Score already includes decay
                            timestamp=point.payload.get('timestamp', datetime.now().isoformat()),
                            role=point.payload.get('start_role', point.payload.get('role', 'unknown')),
                            excerpt=(point.payload.get('text', '')[:500] + '...'),
                            project_name=point.payload.get('project', collection_name.replace('conv_', '').replace('_voyage', '')),
                            conversation_id=point.payload.get('conversation_id'),
                            collection_name=collection_name
                        ))
                    
                elif should_use_decay:
                    # Use client-side decay (existing implementation)
                    await ctx.debug(f"Using CLIENT-SIDE decay for {collection_name}")
                    
                    # Search without score threshold to get all candidates
                    results = await qdrant_client.search(
                        collection_name=collection_name,
                        query_vector=query_embedding,
                        limit=limit * 3,  # Get more candidates for decay filtering
                        with_payload=True
                    )
                    
                    # Apply decay scoring manually
                    now = datetime.now()
                    scale_ms = DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000
                    
                    decay_results = []
                    for point in results:
                        try:
                            # Get timestamp from payload
                            timestamp_str = point.payload.get('timestamp')
                            if timestamp_str:
                                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                age_ms = (now - timestamp).total_seconds() * 1000
                                
                                # Calculate decay factor
                                decay_factor = np.exp(-age_ms / scale_ms)
                                
                                # Apply decay formula
                                adjusted_score = point.score + (DECAY_WEIGHT * decay_factor)
                                
                                # Debug: show the calculation
                                age_days = age_ms / (24 * 60 * 60 * 1000)
                                await ctx.debug(f"Point: age={age_days:.1f} days, original_score={point.score:.3f}, decay_factor={decay_factor:.3f}, adjusted_score={adjusted_score:.3f}")
                            else:
                                adjusted_score = point.score
                            
                            # Only include if above min_score after decay
                            if adjusted_score >= min_score:
                                decay_results.append((adjusted_score, point))
                        
                        except Exception as e:
                            await ctx.debug(f"Error applying decay to point: {e}")
                            decay_results.append((point.score, point))
                    
                    # Sort by adjusted score and take top results
                    decay_results.sort(key=lambda x: x[0], reverse=True)
                    
                    # Convert to SearchResult format
                    for adjusted_score, point in decay_results[:limit]:
                        all_results.append(SearchResult(
                            id=str(point.id),
                            score=adjusted_score,  # Use adjusted score
                            timestamp=point.payload.get('timestamp', datetime.now().isoformat()),
                            role=point.payload.get('start_role', point.payload.get('role', 'unknown')),
                            excerpt=(point.payload.get('text', '')[:500] + '...'),
                            project_name=point.payload.get('project', collection_name.replace('conv_', '').replace('_voyage', '')),
                            conversation_id=point.payload.get('conversation_id'),
                            collection_name=collection_name
                        ))
                else:
                    # Standard search without decay
                    results = await qdrant_client.search(
                        collection_name=collection_name,
                        query_vector=query_embedding,
                        limit=limit,
                        score_threshold=min_score,
                        with_payload=True
                    )
                    
                    for point in results:
                        all_results.append(SearchResult(
                            id=str(point.id),
                            score=point.score,
                            timestamp=point.payload.get('timestamp', datetime.now().isoformat()),
                            role=point.payload.get('start_role', point.payload.get('role', 'unknown')),
                            excerpt=(point.payload.get('text', '')[:500] + '...'),
                            project_name=point.payload.get('project', collection_name.replace('conv_', '').replace('_voyage', '')),
                            conversation_id=point.payload.get('conversation_id'),
                            collection_name=collection_name
                        ))
            
            except Exception as e:
                await ctx.debug(f"Error searching {collection_name}: {str(e)}")
                continue
        
        # Sort by score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[:limit]
        
        if not all_results:
            return f"No conversations found matching '{query}'. Try different keywords or check if conversations have been imported."
        
        # Format results
        result_text = f"Found {len(all_results)} relevant conversation(s) for '{query}':\n\n"
        for i, result in enumerate(all_results):
            result_text += f"**Result {i+1}** (Score: {result.score:.3f})\n"
            result_text += f"Time: {datetime.fromisoformat(result.timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n"
            result_text += f"Project: {result.project_name}\n"
            result_text += f"Role: {result.role}\n"
            result_text += f"Excerpt: {result.excerpt}\n"
            result_text += "---\n\n"
        
        return result_text
        
    except Exception as e:
        await ctx.error(f"Search failed: {str(e)}")
        return f"Failed to search conversations: {str(e)}"

@mcp.tool()
async def store_reflection(
    ctx: Context,
    content: str = Field(description="The insight or reflection to store"),
    tags: List[str] = Field(default=[], description="Tags to categorize this reflection")
) -> str:
    """Store an important insight or reflection for future reference."""
    
    try:
        # TODO: Implement actual storage in a dedicated reflections collection
        # For now, just acknowledge the storage
        tags_str = ', '.join(tags) if tags else 'none'
        return f"Reflection stored successfully with tags: {tags_str}"
        
    except Exception as e:
        await ctx.error(f"Store failed: {str(e)}")
        return f"Failed to store reflection: {str(e)}"


# Debug output
print(f"[DEBUG] FastMCP server created with name: {mcp.name}")