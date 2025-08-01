"""Claude Reflect MCP Server with Memory Decay."""

import os
import asyncio
from pathlib import Path
from typing import Any, Optional, List, Dict, Union
from datetime import datetime, timezone
import json
import numpy as np
import hashlib
import time

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    PointStruct, VectorParams, Distance
)

# Try to import newer Qdrant API for native decay
try:
    from qdrant_client.models import (
        Query, Formula, Expression, MultExpression,
        ExpDecayExpression, DecayParamsExpression,
        SearchRequest, NamedQuery
    )
    NATIVE_DECAY_AVAILABLE = True
except ImportError:
    # Fall back to older API
    from qdrant_client.models import (
        FormulaQuery, DecayParamsExpression, SumExpression,
        DatetimeExpression, DatetimeKeyExpression
    )
    NATIVE_DECAY_AVAILABLE = False
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

# Embedding configuration
PREFER_LOCAL_EMBEDDINGS = os.getenv('PREFER_LOCAL_EMBEDDINGS', 'false').lower() == 'true'
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')

# Initialize Voyage AI client (only if not using local embeddings)
voyage_client = None
if not PREFER_LOCAL_EMBEDDINGS and VOYAGE_API_KEY:
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)

# Initialize local embedding model if needed
local_embedding_model = None
if PREFER_LOCAL_EMBEDDINGS or not VOYAGE_API_KEY:
    try:
        from fastembed import TextEmbedding
        local_embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
        print(f"[DEBUG] Initialized local embedding model: {EMBEDDING_MODEL}")
    except ImportError:
        print("[ERROR] FastEmbed not available. Install with: pip install fastembed")
        raise

# Debug environment loading
print(f"[DEBUG] Environment variables loaded:")
print(f"[DEBUG] ENABLE_MEMORY_DECAY: {ENABLE_MEMORY_DECAY}")
print(f"[DEBUG] USE_NATIVE_DECAY: {USE_NATIVE_DECAY}")
print(f"[DEBUG] DECAY_WEIGHT: {DECAY_WEIGHT}")
print(f"[DEBUG] DECAY_SCALE_DAYS: {DECAY_SCALE_DAYS}")
print(f"[DEBUG] PREFER_LOCAL_EMBEDDINGS: {PREFER_LOCAL_EMBEDDINGS}")
print(f"[DEBUG] EMBEDDING_MODEL: {EMBEDDING_MODEL}")
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
    raw_payload: Optional[Dict[str, Any]] = None  # Full Qdrant payload when debug mode enabled


# Initialize FastMCP instance
mcp = FastMCP(
    name="claude-self-reflect",
    instructions="Search past conversations and store reflections with time-based memory decay"
)

# Create Qdrant client
qdrant_client = AsyncQdrantClient(url=QDRANT_URL)
    
async def get_all_collections() -> List[str]:
    """Get all collections (both Voyage and local)."""
    collections = await qdrant_client.get_collections()
    # Support both _voyage and _local collections, plus reflections
    return [c.name for c in collections.collections 
            if c.name.endswith('_voyage') or c.name.endswith('_local') or c.name.startswith('reflections')]

async def generate_embedding(text: str) -> List[float]:
    """Generate embedding using configured provider."""
    if PREFER_LOCAL_EMBEDDINGS or not voyage_client:
        # Use local embeddings
        if not local_embedding_model:
            raise ValueError("Local embedding model not initialized")
        
        # Run in executor since fastembed is synchronous
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: list(local_embedding_model.embed([text]))
        )
        return embeddings[0].tolist()
    else:
        # Use Voyage AI
        result = voyage_client.embed(
            texts=[text],
            model="voyage-3-large",
            input_type="query"
        )
        return result.embeddings[0]

def get_embedding_dimension() -> int:
    """Get the dimension of embeddings based on the provider."""
    if PREFER_LOCAL_EMBEDDINGS or not voyage_client:
        # all-MiniLM-L6-v2 produces 384-dimensional embeddings
        return 384
    else:
        # voyage-3-large produces 1024-dimensional embeddings
        return 1024

def get_collection_suffix() -> str:
    """Get the collection suffix based on embedding provider."""
    if PREFER_LOCAL_EMBEDDINGS or not voyage_client:
        return "_local"
    else:
        return "_voyage"
    
# Register tools
@mcp.tool()
async def reflect_on_past(
    ctx: Context,
    query: str = Field(description="The search query to find semantically similar conversations"),
    limit: int = Field(default=5, description="Maximum number of results to return"),
    min_score: float = Field(default=0.7, description="Minimum similarity score (0-1)"),
    use_decay: Union[int, str] = Field(default=-1, description="Apply time-based decay: 1=enable, 0=disable, -1=use environment default (accepts int or str)"),
    project: Optional[str] = Field(default=None, description="Search specific project only. If not provided, searches current project based on working directory. Use 'all' to search across all projects."),
    include_raw: bool = Field(default=False, description="Include raw Qdrant payload data for debugging (increases response size)"),
    response_format: str = Field(default="xml", description="Response format: 'xml' or 'markdown'"),
    brief: bool = Field(default=False, description="Brief mode: returns minimal information for faster response")
) -> str:
    """Search for relevant past conversations using semantic search with optional time decay."""
    
    # Start timing
    start_time = time.time()
    timing_info = {}
    
    # Normalize use_decay to integer
    timing_info['param_parsing_start'] = time.time()
    if isinstance(use_decay, str):
        try:
            use_decay = int(use_decay)
        except ValueError:
            raise ValueError("use_decay must be '1', '0', or '-1'")
    timing_info['param_parsing_end'] = time.time()
    
    # Parse decay parameter using integer approach
    should_use_decay = (
        True if use_decay == 1
        else False if use_decay == 0
        else ENABLE_MEMORY_DECAY  # -1 or any other value
    )
    
    # Determine project scope
    target_project = project
    if project is None:
        # Try to detect current project from working directory
        cwd = os.getcwd()
        # Extract project name from path (e.g., /Users/.../projects/project-name)
        path_parts = Path(cwd).parts
        if 'projects' in path_parts:
            idx = path_parts.index('projects')
            if idx + 1 < len(path_parts):
                target_project = path_parts[idx + 1]
        elif '.claude' in path_parts:
            # If we're in a .claude directory, go up to find project
            for i, part in enumerate(path_parts):
                if part == '.claude' and i > 0:
                    target_project = path_parts[i - 1]
                    break
        
        # If still no project detected, use the last directory name
        if target_project is None:
            target_project = Path(cwd).name
    
    # For project matching, we need to handle the dash-encoded format
    # Convert folder name to the format used in stored data
    if target_project != 'all':
        # The stored format uses full path with dashes, so we need to construct it
        # For now, let's try to match based on the end of the project name
        pass  # We'll handle this differently in the filtering logic
    
    await ctx.debug(f"Searching for: {query}")
    await ctx.debug(f"Project scope: {target_project if target_project != 'all' else 'all projects'}")
    await ctx.debug(f"Decay enabled: {should_use_decay}")
    await ctx.debug(f"Native decay mode: {USE_NATIVE_DECAY}")
    await ctx.debug(f"ENABLE_MEMORY_DECAY env: {ENABLE_MEMORY_DECAY}")
    await ctx.debug(f"DECAY_WEIGHT: {DECAY_WEIGHT}, DECAY_SCALE_DAYS: {DECAY_SCALE_DAYS}")
    
    try:
        # Generate embedding
        timing_info['embedding_start'] = time.time()
        query_embedding = await generate_embedding(query)
        timing_info['embedding_end'] = time.time()
        
        # Get all collections
        timing_info['get_collections_start'] = time.time()
        all_collections = await get_all_collections()
        timing_info['get_collections_end'] = time.time()
        
        if not all_collections:
            return "No conversation collections found. Please import conversations first."
        
        # Filter collections by project if not searching all
        project_collections = []  # Define at this scope for later use
        if target_project != 'all':
            # Generate the collection name pattern for this project
            project_hash = hashlib.md5(target_project.encode()).hexdigest()[:8]
            project_collections = [
                c for c in all_collections 
                if c.startswith(f"conv_{project_hash}_")
            ]
            
            if not project_collections:
                # Try to find collections with project metadata
                # Fall back to searching all collections but filtering by project metadata
                await ctx.debug(f"No collections found for project hash {project_hash}, will filter by metadata")
                collections_to_search = all_collections
            else:
                await ctx.debug(f"Found {len(project_collections)} collections for project {target_project}")
                collections_to_search = project_collections
        else:
            collections_to_search = all_collections
        
        await ctx.debug(f"Searching across {len(collections_to_search)} collections")
        await ctx.debug(f"Using {'local' if PREFER_LOCAL_EMBEDDINGS or not voyage_client else 'Voyage AI'} embeddings")
        
        all_results = []
        
        # Search each collection
        timing_info['search_all_start'] = time.time()
        collection_timings = []
        
        # Report initial progress
        await ctx.report_progress(progress=0, total=len(collections_to_search))
        
        for idx, collection_name in enumerate(collections_to_search):
            collection_timing = {'name': collection_name, 'start': time.time()}
            
            # Report progress before searching each collection
            await ctx.report_progress(
                progress=idx, 
                total=len(collections_to_search),
                message=f"Searching {collection_name}"
            )
            
            try:
                if should_use_decay and USE_NATIVE_DECAY and NATIVE_DECAY_AVAILABLE:
                    # Use native Qdrant decay with newer API
                    await ctx.debug(f"Using NATIVE Qdrant decay (new API) for {collection_name}")
                    
                    # Build the query with native Qdrant decay formula using newer API
                    query_obj = Query(
                        nearest=query_embedding,
                        formula=Formula(
                            sum=[
                                # Original similarity score
                                Expression(variable="score"),
                                # Decay boost term
                                Expression(
                                    mult=MultExpression(
                                        mult=[
                                            # Decay weight
                                            Expression(constant=DECAY_WEIGHT),
                                            # Exponential decay function
                                            Expression(
                                                exp_decay=DecayParamsExpression(
                                                    # Use timestamp field for decay
                                                    x=Expression(datetime_key="timestamp"),
                                                    # Decay from current time (server-side)
                                                    target=Expression(datetime="now"),
                                                    # Scale in milliseconds
                                                    scale=DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000,
                                                    # Standard exponential decay midpoint
                                                    midpoint=0.5
                                                )
                                            )
                                        ]
                                    )
                                )
                            ]
                        )
                    )
                    
                    # Execute query with native decay (new API)
                    results = await qdrant_client.query_points(
                        collection_name=collection_name,
                        query=query_obj,
                        limit=limit,
                        score_threshold=min_score,
                        with_payload=True
                    )
                elif should_use_decay and USE_NATIVE_DECAY and not NATIVE_DECAY_AVAILABLE:
                    # Use native Qdrant decay with older API
                    await ctx.debug(f"Using NATIVE Qdrant decay (legacy API) for {collection_name}")
                    
                    # Build the query with native Qdrant decay formula using older API
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
                        # Clean timestamp for proper parsing
                        raw_timestamp = point.payload.get('timestamp', datetime.now().isoformat())
                        clean_timestamp = raw_timestamp.replace('Z', '+00:00') if raw_timestamp.endswith('Z') else raw_timestamp
                        
                        # Check project filter if we're searching all collections but want specific project
                        point_project = point.payload.get('project', collection_name.replace('conv_', '').replace('_voyage', '').replace('_local', ''))
                        
                        # Handle project matching - check if the target project name appears at the end of the stored project path
                        if target_project != 'all' and not project_collections:
                            # The stored project name is like "-Users-ramakrishnanannaswamy-projects-ShopifyMCPMockShop"
                            # We want to match just "ShopifyMCPMockShop"
                            if not point_project.endswith(f"-{target_project}") and point_project != target_project:
                                continue  # Skip results from other projects
                            
                        all_results.append(SearchResult(
                            id=str(point.id),
                            score=point.score,  # Score already includes decay
                            timestamp=clean_timestamp,
                            role=point.payload.get('start_role', point.payload.get('role', 'unknown')),
                            excerpt=(point.payload.get('text', '')[:350] + '...' if len(point.payload.get('text', '')) > 350 else point.payload.get('text', '')),
                            project_name=point_project,
                            conversation_id=point.payload.get('conversation_id'),
                            collection_name=collection_name,
                            raw_payload=point.payload if include_raw else None
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
                    now = datetime.now(timezone.utc)
                    scale_ms = DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000
                    
                    decay_results = []
                    for point in results:
                        try:
                            # Get timestamp from payload
                            timestamp_str = point.payload.get('timestamp')
                            if timestamp_str:
                                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                # Ensure timestamp is timezone-aware
                                if timestamp.tzinfo is None:
                                    timestamp = timestamp.replace(tzinfo=timezone.utc)
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
                        # Clean timestamp for proper parsing
                        raw_timestamp = point.payload.get('timestamp', datetime.now().isoformat())
                        clean_timestamp = raw_timestamp.replace('Z', '+00:00') if raw_timestamp.endswith('Z') else raw_timestamp
                        
                        # Check project filter if we're searching all collections but want specific project
                        point_project = point.payload.get('project', collection_name.replace('conv_', '').replace('_voyage', '').replace('_local', ''))
                        
                        # Handle project matching - check if the target project name appears at the end of the stored project path
                        if target_project != 'all' and not project_collections:
                            # The stored project name is like "-Users-ramakrishnanannaswamy-projects-ShopifyMCPMockShop"
                            # We want to match just "ShopifyMCPMockShop"
                            if not point_project.endswith(f"-{target_project}") and point_project != target_project:
                                continue  # Skip results from other projects
                            
                        all_results.append(SearchResult(
                            id=str(point.id),
                            score=adjusted_score,  # Use adjusted score
                            timestamp=clean_timestamp,
                            role=point.payload.get('start_role', point.payload.get('role', 'unknown')),
                            excerpt=(point.payload.get('text', '')[:350] + '...' if len(point.payload.get('text', '')) > 350 else point.payload.get('text', '')),
                            project_name=point_project,
                            conversation_id=point.payload.get('conversation_id'),
                            collection_name=collection_name,
                            raw_payload=point.payload if include_raw else None
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
                        # Clean timestamp for proper parsing
                        raw_timestamp = point.payload.get('timestamp', datetime.now().isoformat())
                        clean_timestamp = raw_timestamp.replace('Z', '+00:00') if raw_timestamp.endswith('Z') else raw_timestamp
                        
                        # Check project filter if we're searching all collections but want specific project
                        point_project = point.payload.get('project', collection_name.replace('conv_', '').replace('_voyage', '').replace('_local', ''))
                        
                        # Handle project matching - check if the target project name appears at the end of the stored project path
                        if target_project != 'all' and not project_collections:
                            # The stored project name is like "-Users-ramakrishnanannaswamy-projects-ShopifyMCPMockShop"
                            # We want to match just "ShopifyMCPMockShop"
                            if not point_project.endswith(f"-{target_project}") and point_project != target_project:
                                continue  # Skip results from other projects
                            
                        all_results.append(SearchResult(
                            id=str(point.id),
                            score=point.score,
                            timestamp=clean_timestamp,
                            role=point.payload.get('start_role', point.payload.get('role', 'unknown')),
                            excerpt=(point.payload.get('text', '')[:350] + '...' if len(point.payload.get('text', '')) > 350 else point.payload.get('text', '')),
                            project_name=point_project,
                            conversation_id=point.payload.get('conversation_id'),
                            collection_name=collection_name,
                            raw_payload=point.payload if include_raw else None
                        ))
            
            except Exception as e:
                await ctx.debug(f"Error searching {collection_name}: {str(e)}")
                collection_timing['error'] = str(e)
            
            collection_timing['end'] = time.time()
            collection_timings.append(collection_timing)
        
        timing_info['search_all_end'] = time.time()
        
        # Report completion of search phase
        await ctx.report_progress(
            progress=len(collections_to_search), 
            total=len(collections_to_search),
            message="Search complete, processing results"
        )
        
        # Sort by score and limit
        timing_info['sort_start'] = time.time()
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[:limit]
        timing_info['sort_end'] = time.time()
        
        if not all_results:
            return f"No conversations found matching '{query}'. Try different keywords or check if conversations have been imported."
        
        # Format results based on response_format
        timing_info['format_start'] = time.time()
        
        if response_format == "xml":
            # XML format (compact tags for performance)
            result_text = "<search>\n"
            result_text += f"  <meta>\n"
            result_text += f"    <q>{query}</q>\n"
            result_text += f"    <scope>{target_project if target_project != 'all' else 'all'}</scope>\n"
            result_text += f"    <count>{len(all_results)}</count>\n"
            if all_results:
                result_text += f"    <range>{all_results[-1].score:.3f}-{all_results[0].score:.3f}</range>\n"
            result_text += f"    <embed>{'local' if PREFER_LOCAL_EMBEDDINGS or not voyage_client else 'voyage'}</embed>\n"
            
            # Add timing metadata
            total_time = time.time() - start_time
            result_text += f"    <perf>\n"
            result_text += f"      <ttl>{int(total_time * 1000)}</ttl>\n"
            result_text += f"      <emb>{int((timing_info.get('embedding_end', 0) - timing_info.get('embedding_start', 0)) * 1000)}</emb>\n"
            result_text += f"      <srch>{int((timing_info.get('search_all_end', 0) - timing_info.get('search_all_start', 0)) * 1000)}</srch>\n"
            result_text += f"      <cols>{len(collections_to_search)}</cols>\n"
            result_text += f"    </perf>\n"
            result_text += f"  </meta>\n"
            
            result_text += "  <results>\n"
            for i, result in enumerate(all_results):
                result_text += f'    <r rank="{i+1}">\n'
                result_text += f"      <s>{result.score:.3f}</s>\n"
                result_text += f"      <p>{result.project_name}</p>\n"
                
                # Calculate relative time
                timestamp_clean = result.timestamp.replace('Z', '+00:00') if result.timestamp.endswith('Z') else result.timestamp
                timestamp_dt = datetime.fromisoformat(timestamp_clean)
                # Ensure both datetimes are timezone-aware
                if timestamp_dt.tzinfo is None:
                    timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                days_ago = (now - timestamp_dt).days
                if days_ago == 0:
                    time_str = "today"
                elif days_ago == 1:
                    time_str = "yesterday"
                else:
                    time_str = f"{days_ago}d"
                result_text += f"      <t>{time_str}</t>\n"
                
                if not brief:
                    # Extract title from first line of excerpt
                    excerpt_lines = result.excerpt.split('\n')
                    title = excerpt_lines[0][:80] + "..." if len(excerpt_lines[0]) > 80 else excerpt_lines[0]
                    result_text += f"      <title>{title}</title>\n"
                    
                    # Key finding - summarize the main point
                    key_finding = result.excerpt[:100] + "..." if len(result.excerpt) > 100 else result.excerpt
                    result_text += f"      <key-finding>{key_finding.strip()}</key-finding>\n"
                
                # Always include excerpt, but shorter in brief mode
                if brief:
                    brief_excerpt = result.excerpt[:100] + "..." if len(result.excerpt) > 100 else result.excerpt
                    result_text += f"      <excerpt>{brief_excerpt.strip()}</excerpt>\n"
                else:
                    result_text += f"      <excerpt><![CDATA[{result.excerpt}]]></excerpt>\n"
                
                if result.conversation_id:
                    result_text += f"      <cid>{result.conversation_id}</cid>\n"
                
                # Include raw data if requested
                if include_raw and result.raw_payload:
                    result_text += "      <raw>\n"
                    result_text += f"        <txt><![CDATA[{result.raw_payload.get('text', '')}]]></txt>\n"
                    result_text += f"        <id>{result.id}</id>\n"
                    result_text += f"        <dist>{1 - result.score:.3f}</dist>\n"
                    result_text += "        <meta>\n"
                    for key, value in result.raw_payload.items():
                        if key != 'text':
                            result_text += f"          <{key}>{value}</{key}>\n"
                    result_text += "        </meta>\n"
                    result_text += "      </raw>\n"
                
                result_text += "    </r>\n"
            result_text += "  </results>\n"
            result_text += "</search>"
            
        else:
            # Markdown format (original)
            result_text = f"Found {len(all_results)} relevant conversation(s) for '{query}':\n\n"
            for i, result in enumerate(all_results):
                result_text += f"**Result {i+1}** (Score: {result.score:.3f})\n"
                # Handle timezone suffix 'Z' properly
                timestamp_clean = result.timestamp.replace('Z', '+00:00') if result.timestamp.endswith('Z') else result.timestamp
                result_text += f"Time: {datetime.fromisoformat(timestamp_clean).strftime('%Y-%m-%d %H:%M:%S')}\n"
                result_text += f"Project: {result.project_name}\n"
                result_text += f"Role: {result.role}\n"
                result_text += f"Excerpt: {result.excerpt}\n"
                result_text += "---\n\n"
        
        timing_info['format_end'] = time.time()
        
        # Log detailed timing breakdown
        await ctx.debug(f"\n=== TIMING BREAKDOWN ===")
        await ctx.debug(f"Total time: {(time.time() - start_time) * 1000:.1f}ms")
        await ctx.debug(f"Embedding generation: {(timing_info.get('embedding_end', 0) - timing_info.get('embedding_start', 0)) * 1000:.1f}ms")
        await ctx.debug(f"Get collections: {(timing_info.get('get_collections_end', 0) - timing_info.get('get_collections_start', 0)) * 1000:.1f}ms")
        await ctx.debug(f"Search all collections: {(timing_info.get('search_all_end', 0) - timing_info.get('search_all_start', 0)) * 1000:.1f}ms")
        await ctx.debug(f"Sorting results: {(timing_info.get('sort_end', 0) - timing_info.get('sort_start', 0)) * 1000:.1f}ms")
        await ctx.debug(f"Formatting output: {(timing_info.get('format_end', 0) - timing_info.get('format_start', 0)) * 1000:.1f}ms")
        
        # Log per-collection timings
        await ctx.debug(f"\n=== PER-COLLECTION TIMINGS ===")
        for ct in collection_timings:
            duration = (ct.get('end', 0) - ct.get('start', 0)) * 1000
            status = "ERROR" if 'error' in ct else "OK"
            await ctx.debug(f"{ct['name']}: {duration:.1f}ms ({status})")
        
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
        # Create reflections collection name
        collection_name = f"reflections{get_collection_suffix()}"
        
        # Ensure collection exists
        try:
            collection_info = await qdrant_client.get_collection(collection_name)
        except:
            # Create collection if it doesn't exist
            await qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=get_embedding_dimension(),
                    distance=Distance.COSINE
                )
            )
            await ctx.debug(f"Created reflections collection: {collection_name}")
        
        # Generate embedding for the reflection
        embedding = await generate_embedding(content)
        
        # Create point with metadata
        point_id = datetime.now().timestamp()
        point = PointStruct(
            id=int(point_id),
            vector=embedding,
            payload={
                "text": content,
                "tags": tags,
                "timestamp": datetime.now().isoformat(),
                "type": "reflection",
                "role": "user_reflection"
            }
        )
        
        # Store in Qdrant
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[point]
        )
        
        tags_str = ', '.join(tags) if tags else 'none'
        return f"Reflection stored successfully with tags: {tags_str}"
        
    except Exception as e:
        await ctx.error(f"Store failed: {str(e)}")
        return f"Failed to store reflection: {str(e)}"


@mcp.tool()
async def quick_search(
    ctx: Context,
    query: str = Field(description="The search query to find semantically similar conversations"),
    min_score: float = Field(default=0.7, description="Minimum similarity score (0-1)"),
    project: Optional[str] = Field(default=None, description="Search specific project only. If not provided, searches current project based on working directory. Use 'all' to search across all projects.")
) -> str:
    """Quick search that returns only the count and top result for fast overview."""
    try:
        # Leverage reflect_on_past with optimized parameters
        result = await reflect_on_past(
            ctx=ctx,
            query=query,
            limit=1,  # Only get the top result
            min_score=min_score,
            project=project,
            response_format="xml",
            brief=True,  # Use brief mode for minimal response
            include_raw=False
        )
        
        # Parse and reformat for quick overview
        import re
        
        # Extract count from metadata
        count_match = re.search(r'<tc>(\d+)</tc>', result)
        total_count = count_match.group(1) if count_match else "0"
        
        # Extract top result
        score_match = re.search(r'<s>([\d.]+)</s>', result)
        project_match = re.search(r'<p>([^<]+)</p>', result)
        title_match = re.search(r'<t>([^<]+)</t>', result)
        
        if score_match and project_match and title_match:
            return f"""<quick_search>
<total_matches>{total_count}</total_matches>
<top_result>
<score>{score_match.group(1)}</score>
<project>{project_match.group(1)}</project>
<title>{title_match.group(1)}</title>
</top_result>
</quick_search>"""
        else:
            return f"""<quick_search>
<total_matches>{total_count}</total_matches>
<message>No relevant matches found</message>
</quick_search>"""
    except Exception as e:
        await ctx.error(f"Quick search failed: {str(e)}")
        return f"<quick_search><error>{str(e)}</error></quick_search>"


@mcp.tool()
async def search_summary(
    ctx: Context,
    query: str = Field(description="The search query to find semantically similar conversations"),
    project: Optional[str] = Field(default=None, description="Search specific project only. If not provided, searches current project based on working directory. Use 'all' to search across all projects.")
) -> str:
    """Get aggregated insights from search results without individual result details."""
    # Get more results for better summary
    result = await reflect_on_past(
        ctx=ctx,
        query=query,
        limit=10,  # Get more results for analysis
        min_score=0.6,  # Lower threshold for broader context
        project=project,
        response_format="xml",
        brief=False,  # Get full excerpts for analysis
        include_raw=False
    )
    
    # Parse results for summary generation
    import re
    from collections import Counter
    
    # Extract all projects
    projects = re.findall(r'<p>([^<]+)</p>', result)
    project_counts = Counter(projects)
    
    # Extract scores for statistics
    scores = [float(s) for s in re.findall(r'<s>([\d.]+)</s>', result)]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Extract themes from titles and excerpts
    titles = re.findall(r'<t>([^<]+)</t>', result)
    excerpts = re.findall(r'<e>([^<]+)</e>', result)
    
    # Extract metadata
    count_match = re.search(r'<tc>(\d+)</tc>', result)
    total_count = count_match.group(1) if count_match else "0"
    
    # Generate summary
    summary = f"""<search_summary>
<total_matches>{total_count}</total_matches>
<searched_projects>{len(project_counts)}</searched_projects>
<average_relevance>{avg_score:.2f}</average_relevance>
<project_distribution>"""
    
    for proj, count in project_counts.most_common(3):
        summary += f"\n  <project name='{proj}' matches='{count}'/>"
    
    summary += f"""
</project_distribution>
<common_themes>"""
    
    # Simple theme extraction from titles
    theme_words = []
    for title in titles[:5]:  # Top 5 results
        words = [w.lower() for w in title.split() if len(w) > 4]
        theme_words.extend(words)
    
    theme_counts = Counter(theme_words)
    for theme, count in theme_counts.most_common(5):
        if count > 1:  # Only show repeated themes
            summary += f"\n  <theme>{theme}</theme>"
    
    summary += """
</common_themes>
</search_summary>"""
    
    return summary


@mcp.tool()
async def get_more_results(
    ctx: Context,
    query: str = Field(description="The original search query"),
    offset: int = Field(default=3, description="Number of results to skip (for pagination)"),
    limit: int = Field(default=3, description="Number of additional results to return"),
    min_score: float = Field(default=0.7, description="Minimum similarity score (0-1)"),
    project: Optional[str] = Field(default=None, description="Search specific project only")
) -> str:
    """Get additional search results after an initial search (pagination support)."""
    # Note: Since Qdrant doesn't support true offset in our current implementation,
    # we'll fetch offset+limit results and slice
    total_limit = offset + limit
    
    # Get the larger result set
    result = await reflect_on_past(
        ctx=ctx,
        query=query,
        limit=total_limit,
        min_score=min_score,
        project=project,
        response_format="xml",
        brief=False,
        include_raw=False
    )
    
    # Parse and extract only the additional results
    import re
    
    # Find all result blocks
    result_pattern = r'<r>.*?</r>'
    all_results = re.findall(result_pattern, result, re.DOTALL)
    
    # Get only the results after offset
    additional_results = all_results[offset:offset+limit] if len(all_results) > offset else []
    
    if not additional_results:
        return """<more_results>
<message>No additional results found</message>
</more_results>"""
    
    # Reconstruct response with only additional results
    response = f"""<more_results>
<offset>{offset}</offset>
<count>{len(additional_results)}</count>
<results>
{''.join(additional_results)}
</results>
</more_results>"""
    
    return response


# Debug output
print(f"[DEBUG] FastMCP server created with name: {mcp.name}")

# Run the server
if __name__ == "__main__":
    mcp.run()
