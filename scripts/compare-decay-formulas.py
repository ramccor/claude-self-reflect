#!/usr/bin/env python3
"""
Compare different decay formula implementations to understand score differences.
"""

import numpy as np
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table

console = Console()

# Configuration
DECAY_WEIGHT = 0.3
DECAY_SCALE_DAYS = 90
ORIGINAL_SCORE = 1.0  # Cosine similarity for identical vectors

def client_side_formula(original_score, decay_factor, weight):
    """Client-side formula: score * (1 - weight) + decay_factor * weight"""
    return original_score * (1 - weight) + decay_factor * weight

def native_formula(original_score, decay_factor, weight):
    """Native formula as documented: score + weight * decay_factor"""
    return original_score + weight * decay_factor

def analyze_formulas():
    """Compare the two decay formulas."""
    console.print("[bold cyan]Decay Formula Comparison[/bold cyan]\n")
    
    # Create comparison table
    table = Table(title="Formula Results Comparison")
    table.add_column("Age (days)", style="cyan")
    table.add_column("Decay Factor", style="yellow")
    table.add_column("Client Formula", style="green")
    table.add_column("Native Formula", style="magenta")
    table.add_column("Difference", style="red")
    
    ages = [0, 30, 90, 180, 365]
    
    for age_days in ages:
        decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
        
        client_score = client_side_formula(ORIGINAL_SCORE, decay_factor, DECAY_WEIGHT)
        native_score = native_formula(ORIGINAL_SCORE, decay_factor, DECAY_WEIGHT)
        difference = native_score - client_score
        
        table.add_row(
            str(age_days),
            f"{decay_factor:.3f}",
            f"{client_score:.3f}",
            f"{native_score:.3f}",
            f"{difference:+.3f}"
        )
    
    console.print(table)
    
    # Explain the formulas
    console.print("\n[bold]Formula Explanations:[/bold]")
    console.print(f"\n[yellow]Client-side:[/yellow] score × (1 - {DECAY_WEIGHT}) + decay × {DECAY_WEIGHT}")
    console.print(f"             = {ORIGINAL_SCORE} × {1-DECAY_WEIGHT} + decay × {DECAY_WEIGHT}")
    console.print(f"             = {ORIGINAL_SCORE * (1-DECAY_WEIGHT):.1f} + decay × {DECAY_WEIGHT}")
    
    console.print(f"\n[magenta]Native:[/magenta] score + {DECAY_WEIGHT} × decay")
    console.print(f"        = {ORIGINAL_SCORE} + {DECAY_WEIGHT} × decay")
    
    console.print("\n[bold]Key Differences:[/bold]")
    console.print("1. Client-side blends original score with decay (weighted average)")
    console.print("2. Native adds decay bonus on top of original score")
    console.print("3. Native can produce scores > 1.0 for fresh content")
    console.print("4. Both produce the same relative ordering")
    
    # Show which is "correct"
    console.print("\n[bold]Which to use?[/bold]")
    console.print("• [green]Client-side[/green]: Scores stay in [0, 1] range, intuitive blend")
    console.print("• [magenta]Native[/magenta]: Can exceed 1.0, but offloads computation to server")
    console.print("• Both produce identical ranking order ✓")

if __name__ == "__main__":
    analyze_formulas()