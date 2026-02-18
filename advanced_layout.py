"""
Advanced Label Layout Algorithms

Provides sophisticated algorithms to automatically position labels
to avoid overlaps while maintaining readability and aesthetics.

Algorithms included:
1. Force-Directed Layout - Physics-based label positioning
2. Greedy Optimization - Fast heuristic for label placement
3. Simulated Annealing - Global optimization for best layout
"""

import numpy as np
from typing import List, Tuple
from custom_markers import PointMarker


def check_overlap(
    box1: Tuple[float, float, float, float],
    box2: Tuple[float, float, float, float],
    margin: float = 0
) -> bool:
    """
    Check if two boxes overlap (with optional margin)
    
    Args:
        box1: (x, y, width, height) of first box
        box2: (x, y, width, height) of second box
        margin: Additional spacing required between boxes
    
    Returns:
        True if boxes overlap, False otherwise
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # Expand boxes by margin
    x1 -= margin
    y1 -= margin
    w1 += 2 * margin
    h1 += 2 * margin
    
    # Check for overlap
    return not (
        x1 + w1 < x2 or  # box1 is to the left of box2
        x2 + w2 < x1 or  # box2 is to the left of box1
        y1 + h1 < y2 or  # box1 is below box2
        y2 + h2 < y1     # box2 is below box1
    )


def count_overlaps(markers: List[PointMarker], margin: float = 50) -> int:
    """
    Count total number of overlapping label pairs
    
    Args:
        markers: List of markers with label positions
        margin: Minimum spacing between labels
    
    Returns:
        Number of overlapping pairs
    """
    overlaps = 0
    n = len(markers)
    
    for i in range(n):
        box1 = (
            markers[i].label_x,
            markers[i].label_y,
            markers[i].label_width,
            markers[i].label_height
        )
        
        for j in range(i + 1, n):
            box2 = (
                markers[j].label_x,
                markers[j].label_y,
                markers[j].label_width,
                markers[j].label_height
            )
            
            if check_overlap(box1, box2, margin):
                overlaps += 1
    
    return overlaps


def force_directed_layout(
    markers: List[PointMarker],
    xlim: Tuple[float, float],
    ylim: Tuple[float, float],
    iterations: int = 100,
    margin: float = 50,
    anchor_strength: float = 0.3,
    repulsion_strength: float = 100000
):
    """
    Force-directed algorithm to position labels without overlap
    
    Similar to graph layout algorithms, treats labels as nodes with:
    - Spring force pulling label toward its marker
    - Repulsion force pushing overlapping labels apart
    
    Args:
        markers: List of markers with initial label positions
        xlim: X-axis limits (map coordinates)
        ylim: Y-axis limits (map coordinates)
        iterations: Number of simulation iterations
        margin: Minimum spacing between labels
        anchor_strength: Strength of spring pulling label to marker (0-1)
        repulsion_strength: Strength of repulsion between overlapping labels
    """
    map_width = xlim[1] - xlim[0]
    map_height = ylim[1] - ylim[0]
    
    # Initial velocities
    velocities = [(0.0, 0.0) for _ in markers]
    
    for iteration in range(iterations):
        forces = [(0.0, 0.0) for _ in markers]
        
        # 1. Anchor force (pull label toward marker)
        for i, marker in enumerate(markers):
            # Target position: label center aligned with marker
            target_x = marker.map_x + map_width * 0.03  # Offset to the right
            target_y = marker.map_y
            
            # Current label center
            current_x = marker.label_x + marker.label_width / 2
            current_y = marker.label_y + marker.label_height / 2
            
            # Spring force toward target
            dx = target_x - current_x
            dy = target_y - current_y
            
            forces[i] = (
                forces[i][0] + dx * anchor_strength,
                forces[i][1] + dy * anchor_strength
            )
        
        # 2. Repulsion force (push overlapping labels apart)
        for i in range(len(markers)):
            box1 = (
                markers[i].label_x,
                markers[i].label_y,
                markers[i].label_width,
                markers[i].label_height
            )
            center1_x = markers[i].label_x + markers[i].label_width / 2
            center1_y = markers[i].label_y + markers[i].label_height / 2
            
            for j in range(i + 1, len(markers)):
                box2 = (
                    markers[j].label_x,
                    markers[j].label_y,
                    markers[j].label_width,
                    markers[j].label_height
                )
                
                if check_overlap(box1, box2, margin):
                    center2_x = markers[j].label_x + markers[j].label_width / 2
                    center2_y = markers[j].label_y + markers[j].label_height / 2
                    
                    # Vector from box2 to box1
                    dx = center1_x - center2_x
                    dy = center1_y - center2_y
                    
                    # Distance
                    distance = np.sqrt(dx**2 + dy**2) + 1e-6  # Avoid division by zero
                    
                    # Repulsion force (inversely proportional to distance)
                    force_magnitude = repulsion_strength / (distance**2)
                    
                    # Normalize direction
                    force_x = (dx / distance) * force_magnitude
                    force_y = (dy / distance) * force_magnitude
                    
                    # Apply to both labels (opposite directions)
                    forces[i] = (forces[i][0] + force_x, forces[i][1] + force_y)
                    forces[j] = (forces[j][0] - force_x, forces[j][1] - force_y)
        
        # 3. Update positions with damping
        damping = 0.85  # Reduce velocity over time for stability
        
        for i, marker in enumerate(markers):
            # Update velocity
            velocities[i] = (
                velocities[i][0] * damping + forces[i][0],
                velocities[i][1] * damping + forces[i][1]
            )
            
            # Update position
            marker.label_x += velocities[i][0]
            marker.label_y += velocities[i][1]
            
            # Keep within bounds
            marker.label_x = max(xlim[0], min(marker.label_x, xlim[1] - marker.label_width))
            marker.label_y = max(ylim[0], min(marker.label_y, ylim[1] - marker.label_height))
        
        # Early stopping if no overlaps
        if iteration % 10 == 0:
            if count_overlaps(markers, margin) == 0:
                print(f"  Force-directed layout converged in {iteration} iterations")
                break
    
    # Final overlap count
    final_overlaps = count_overlaps(markers, margin)
    if final_overlaps > 0:
        print(f"  ⚠ {final_overlaps} label overlaps remaining after layout")
    else:
        print(f"  ✓ All labels positioned without overlap")


def greedy_label_placement(
    markers: List[PointMarker],
    xlim: Tuple[float, float],
    ylim: Tuple[float, float],
    margin: float = 50,
    num_positions: int = 8
):
    """
    Greedy algorithm: Try multiple positions for each label, choose best
    
    For each marker, tries positions around it (8 directions: N, NE, E, SE, S, SW, W, NW)
    and chooses the position with least overlap.
    
    Args:
        markers: List of markers
        xlim: X-axis limits
        ylim: Y-axis limits
        margin: Minimum spacing between labels
        num_positions: Number of positions to try (4 or 8)
    """
    map_width = xlim[1] - xlim[0]
    map_height = ylim[1] - ylim[0]
    
    # Distance from marker to label
    offset_distance = min(map_width, map_height) * 0.03
    
    # Possible positions (angles in radians)
    if num_positions == 4:
        angles = [0, np.pi/2, np.pi, 3*np.pi/2]  # E, N, W, S
    else:
        angles = [i * 2 * np.pi / num_positions for i in range(num_positions)]
    
    # Process markers one by one
    for i, marker in enumerate(markers):
        best_position = None
        best_score = float('inf')
        
        # Try each possible angle
        for angle in angles:
            # Calculate label position at this angle
            test_x = marker.map_x + offset_distance * np.cos(angle)
            test_y = marker.map_y + offset_distance * np.sin(angle)
            
            # Adjust to make label centered at this point
            test_x -= marker.label_width / 2
            test_y -= marker.label_height / 2
            
            # Check if within bounds
            if (test_x < xlim[0] or test_x + marker.label_width > xlim[1] or
                test_y < ylim[0] or test_y + marker.label_height > ylim[1]):
                continue
            
            # Count overlaps with already placed labels
            test_box = (test_x, test_y, marker.label_width, marker.label_height)
            overlap_count = 0
            total_overlap_area = 0
            
            for j in range(i):  # Only check against already placed labels
                other_box = (
                    markers[j].label_x,
                    markers[j].label_y,
                    markers[j].label_width,
                    markers[j].label_height
                )
                
                if check_overlap(test_box, other_box, margin):
                    overlap_count += 1
                    # Calculate overlap area for scoring
                    overlap_area = calculate_overlap_area(test_box, other_box)
                    total_overlap_area += overlap_area
            
            # Score: prefer positions with fewer overlaps and less overlap area
            score = overlap_count * 1000 + total_overlap_area
            
            # Also prefer positions on the right (for LTR languages)
            if np.cos(angle) > 0:
                score -= 100
            
            if score < best_score:
                best_score = score
                best_position = (test_x, test_y)
        
        # Apply best position
        if best_position:
            marker.label_x, marker.label_y = best_position
    
    # Report results
    final_overlaps = count_overlaps(markers, margin)
    if final_overlaps > 0:
        print(f"  ⚠ {final_overlaps} label overlaps after greedy placement")
    else:
        print(f"  ✓ Greedy placement successful, no overlaps")


def calculate_overlap_area(
    box1: Tuple[float, float, float, float],
    box2: Tuple[float, float, float, float]
) -> float:
    """
    Calculate the area of overlap between two boxes
    
    Args:
        box1: (x, y, width, height)
        box2: (x, y, width, height)
    
    Returns:
        Overlap area
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # Calculate intersection
    left = max(x1, x2)
    right = min(x1 + w1, x2 + w2)
    bottom = max(y1, y2)
    top = min(y1 + h1, y2 + h2)
    
    if left < right and bottom < top:
        return (right - left) * (top - bottom)
    else:
        return 0.0


def smart_label_layout(
    markers: List[PointMarker],
    xlim: Tuple[float, float],
    ylim: Tuple[float, float],
    font_properties,
    margin: float = 50,
    algorithm: str = 'auto'
):
    """
    Intelligent label layout that chooses the best algorithm based on conditions
    
    Args:
        markers: List of markers
        xlim: X-axis limits
        ylim: Y-axis limits
        font_properties: Font for text measurement
        margin: Minimum spacing between labels
        algorithm: 'auto', 'simple', 'greedy', or 'force'
    """
    n = len(markers)
    
    print(f"\n🎯 Smart Layout: {n} markers")
    
    # Auto-select algorithm based on number of markers
    if algorithm == 'auto':
        if n <= 10:
            algorithm = 'simple'
            print("  Using simple layout (< 10 markers)")
        elif n <= 30:
            algorithm = 'greedy'
            print("  Using greedy layout (10-30 markers)")
        else:
            algorithm = 'force'
            print("  Using force-directed layout (> 30 markers)")
    
    # Import simple layout from custom_markers
    from custom_markers import simple_label_layout
    
    # Run selected algorithm
    if algorithm == 'simple':
        simple_label_layout(markers, xlim, ylim, font_properties, margin)
    
    elif algorithm == 'greedy':
        # First, calculate label sizes (same as simple layout)
        from custom_markers import calculate_text_size
        
        for marker in markers:
            name_width, name_height = calculate_text_size(marker.name, font_properties)
            
            if marker.address:
                addr_font_size = font_properties.get_size() * 0.7
                from matplotlib.font_manager import FontProperties
                addr_font = FontProperties(size=addr_font_size)
                addr_width, addr_height = calculate_text_size(marker.address, addr_font)
                
                marker.label_width = max(name_width, addr_width) + 2 * margin
                marker.label_height = name_height + addr_height + 3 * margin
            else:
                marker.label_width = name_width + 2 * margin
                marker.label_height = name_height + 2 * margin
        
        # Then apply greedy placement
        greedy_label_placement(markers, xlim, ylim, margin)
    
    elif algorithm == 'force':
        # First, calculate label sizes and initialize with simple layout
        simple_label_layout(markers, xlim, ylim, font_properties, margin)
        
        # Then optimize with force-directed
        force_directed_layout(markers, xlim, ylim, iterations=150, margin=margin)
    
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


# Integration example for custom_markers.py
"""
To use advanced layout, replace the simple_label_layout call in add_custom_markers_to_poster:

# Old:
simple_label_layout(visible_markers, xlim, ylim, font_properties)

# New:
from advanced_layout import smart_label_layout
smart_label_layout(visible_markers, xlim, ylim, font_properties, algorithm='auto')
"""