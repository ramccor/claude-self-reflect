#!/usr/bin/env python3
"""
Test Qdrant server version and capabilities.
"""

import asyncio
import httpx
from rich.console import Console

console = Console()

async def check_qdrant_version():
    """Check current Qdrant version and capabilities."""
    qdrant_url = "http://localhost:6333"
    
    console.print("[cyan]Checking Qdrant server version...[/cyan]")
    
    try:
        async with httpx.AsyncClient() as client:
            # Get server info
            response = await client.get(f"{qdrant_url}/")
            if response.status_code == 200:
                info = response.json()
                version = info.get('version', 'unknown')
                console.print(f"[yellow]Current Qdrant version: {version}[/yellow]")
                
                if version == "1.14.1":
                    console.print("[red]✗ Running older version that doesn't support datetime expressions[/red]")
                    console.print("\n[bold]To upgrade to 1.15.1:[/bold]")
                    console.print("1. Stop current Qdrant: docker-compose down")
                    console.print("2. Update docker-compose.yaml to use qdrant/qdrant:v1.15.1")
                    console.print("3. Start updated Qdrant: docker-compose up -d")
                elif version.startswith("1.15"):
                    console.print("[green]✓ Running version 1.15.x which should support datetime expressions![/green]")
                else:
                    console.print(f"[yellow]Running version {version}[/yellow]")
            else:
                console.print(f"[red]Failed to get server info: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Error connecting to Qdrant: {e}[/red]")
        console.print("\nMake sure Qdrant is running on port 6333")

if __name__ == "__main__":
    asyncio.run(check_qdrant_version())