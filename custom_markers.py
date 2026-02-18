#!/usr/bin/env python3
"""
Enhanced Map Poster Generator with Custom Point Markers

Extends the original map poster generator to support:
- Custom point markers from my_custom_points.json
- Label boxes with location names and addresses
- Leader lines connecting markers to labels
- Automatic layout optimization to avoid overlaps
- Multilingual font support (Chinese, Japanese, etc.)
"""

import json
import os
from pathlib import Path
from typing import List, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from shapely.geometry import Point as ShapelyPoint
import osmnx as ox
import numpy as np


class PointMarker:
    """Represents a single point marker with its label"""
    
    def __init__(self, name: str, lat: float, lng: float, address: str = ""):
        self.name = name
        self.lat = lat
        self.lng = lng
        self.address = address
        self.map_x: Optional[float] = None  # Projected X coordinate
        self.map_y: Optional[float] = None  # Projected Y coordinate
        self.label_x: Optional[float] = None  # Label box position
        self.label_y: Optional[float] = None
        self.label_width: Optional[float] = None
        self.label_height: Optional[float] = None


def load_custom_points(json_path: str) -> List[PointMarker]:
    """
    Load custom points from my_custom_points.json
    
    Args:
        json_path: Path to the JSON file
    
    Returns:
        List of PointMarker objects
    """
    if not os.path.exists(json_path):
        print(f"⚠ Custom points file not found: {json_path}")
        return []
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    markers = []
    for item in data:
        marker = PointMarker(
            name=item.get('name', 'Unknown'),
            lat=item['lat'],
            lng=item['lng'],
            address=item.get('address', '')
        )
        markers.append(marker)
    
    print(f"✓ Loaded {len(markers)} custom points")
    return markers


def project_points(markers: List[PointMarker], target_crs: str):
    """
    Project lat/lng coordinates to map coordinate system
    
    Args:
        markers: List of PointMarker objects
        target_crs: Target CRS (from the graph)
    """
    for marker in markers:
        point = ShapelyPoint(marker.lng, marker.lat)
        projected = ox.projection.project_geometry(
            point,
            crs="EPSG:4326",
            to_crs=target_crs
        )[0]
        marker.map_x = projected.x
        marker.map_y = projected.y


def calculate_text_size(text: str, font_properties: FontProperties, dpi: float = 72) -> Tuple[float, float]:
    """
    Calculate the rendered size of text in data coordinates
    
    Args:
        text: Text to measure
        font_properties: Font properties
        dpi: DPI for rendering
    
    Returns:
        (width, height) in points
    """
    # Create a temporary text path to measure size
    path = TextPath((0, 0), text, size=font_properties.get_size(), prop=font_properties)
    bbox = path.get_extents()
    
    # Return width and height
    return bbox.width, bbox.height


def simple_label_layout(
    markers: List[PointMarker],
    xlim: Tuple[float, float],
    ylim: Tuple[float, float],
    font_properties: FontProperties,
    padding: float = 50
):
    """
    Simple label layout algorithm - places labels to the right of points
    
    This is a basic version. For advanced layout, use force-directed or optimization algorithms.
    
    Args:
        markers: List of PointMarker objects with map coordinates
        xlim: X-axis limits (map coordinates)
        ylim: Y-axis limits (map coordinates)
        font_properties: Font for text measurement
        padding: Padding around text inside label box
    """
    map_width = xlim[1] - xlim[0]
    map_height = ylim[1] - ylim[0]
    
    for marker in markers:
        # Measure text size
        name_width, name_height = calculate_text_size(marker.name, font_properties)
        
        if marker.address:
            addr_width, addr_height = calculate_text_size(marker.address, font_properties)
            # Label contains both name and address
            label_width = max(name_width, addr_width) + 2 * padding
            label_height = name_height + addr_height + 3 * padding
        else:
            # Label contains only name
            label_width = name_width + 2 * padding
            label_height = name_height + 2 * padding
        
        # Store label dimensions
        marker.label_width = label_width
        marker.label_height = label_height
        
        # Simple positioning: place label to the right of point
        # Add some offset to avoid overlap with the marker
        offset_x = map_width * 0.02  # 2% of map width
        offset_y = 0
        
        # Calculate label position (bottom-left corner)
        marker.label_x = marker.map_x + offset_x
        marker.label_y = marker.map_y - label_height / 2 + offset_y
        
        # Ensure label stays within bounds
        if marker.label_x + label_width > xlim[1]:
            # Place on left if doesn't fit on right
            marker.label_x = marker.map_x - offset_x - label_width
        
        if marker.label_y < ylim[0]:
            marker.label_y = ylim[0]
        elif marker.label_y + label_height > ylim[1]:
            marker.label_y = ylim[1] - label_height


def draw_marker_and_label(
    ax,
    marker: PointMarker,
    marker_color: str = '#FAA95F',  # Orange color from the Tokyo map
    marker_size: float = 100,
    label_bg_color: str = '#FFFFFF',
    label_border_color: str = '#FAA95F',
    label_alpha: float = 0.9,
    text_color: str = '#333333',
    font_properties: FontProperties = None,
    line_color: str = '#FAA95F',
    line_width: float = 1.0,
):
    """
    Draw a single marker with its label and leader line
    
    Args:
        ax: Matplotlib axes
        marker: PointMarker object with all coordinates calculated
        marker_color: Color for the point marker
        marker_size: Size of the marker point
        label_bg_color: Background color of the label box
        label_border_color: Border color of the label box
        label_alpha: Transparency of the label box
        text_color: Color of the text
        font_properties: Font for the text
        line_color: Color of the leader line
        line_width: Width of the leader line
    """
    # 1. Draw marker point
    ax.scatter(
        marker.map_x,
        marker.map_y,
        s=marker_size,
        c=marker_color,
        zorder=12,  # Above gradients
        edgecolors='white',
        linewidths=1.5
    )
    
    # 2. Draw leader line from marker to label
    # Line connects from marker point to the closest edge of label box
    label_center_x = marker.label_x + marker.label_width / 2
    label_center_y = marker.label_y + marker.label_height / 2
    
    # Determine which edge of the label box is closest to the marker
    if marker.label_x > marker.map_x:
        # Label is to the right
        line_end_x = marker.label_x
        line_end_y = label_center_y
    else:
        # Label is to the left
        line_end_x = marker.label_x + marker.label_width
        line_end_y = label_center_y
    
    ax.plot(
        [marker.map_x, line_end_x],
        [marker.map_y, line_end_y],
        color=line_color,
        linewidth=line_width,
        zorder=11,
        alpha=0.7
    )
    
    # 3. Draw label box
    label_rect = mpatches.FancyBboxPatch(
        (marker.label_x, marker.label_y),
        marker.label_width,
        marker.label_height,
        boxstyle="round,pad=0.01",
        facecolor=label_bg_color,
        edgecolor=label_border_color,
        linewidth=1.5,
        alpha=label_alpha,
        zorder=11
    )
    ax.add_patch(label_rect)
    
    # 4. Draw text inside label
    if font_properties is None:
        font_properties = FontProperties(size=10)
    
    # Position text: centered horizontally, with padding vertically
    text_x = marker.label_x + marker.label_width / 2
    
    if marker.address:
        # Two lines: name and address
        name_y = marker.label_y + marker.label_height * 0.65
        addr_y = marker.label_y + marker.label_height * 0.3
        
        # Name (larger, bold)
        ax.text(
            text_x,
            name_y,
            marker.name,
            ha='center',
            va='center',
            fontproperties=font_properties,
            color=text_color,
            zorder=12,
            weight='bold'
        )
        
        # Address (smaller, lighter)
        addr_font = FontProperties(
            fname=font_properties.get_file() if hasattr(font_properties, 'get_file') else None,
            size=font_properties.get_size() * 0.7
        )
        ax.text(
            text_x,
            addr_y,
            marker.address,
            ha='center',
            va='center',
            fontproperties=addr_font,
            color=text_color,
            alpha=0.7,
            zorder=12
        )
    else:
        # Single line: name only
        text_y = marker.label_y + marker.label_height / 2
        ax.text(
            text_x,
            text_y,
            marker.name,
            ha='center',
            va='center',
            fontproperties=font_properties,
            color=text_color,
            zorder=12,
            weight='bold'
        )


def add_custom_markers_to_poster(
    ax,
    g_proj,
    custom_points_json: str,
    font_properties: FontProperties = None,
    marker_config: dict = None
):
    """
    Add custom point markers with labels to an existing map poster
    
    This function should be called after the map has been drawn but before saving.
    
    Args:
        ax: Matplotlib axes with the map already drawn
        g_proj: Projected graph (for getting CRS)
        custom_points_json: Path to my_custom_points.json
        font_properties: Font for labels (defaults to system font)
        marker_config: Optional dict with styling configuration
    """
    # Default marker configuration
    if marker_config is None:
        marker_config = {
            'marker_color': '#FAA95F',  # Orange
            'marker_size': 100,
            'label_bg_color': '#FFFFFF',
            'label_border_color': '#FAA95F',
            'label_alpha': 0.9,
            'text_color': '#333333',
            'line_color': '#FAA95F',
            'line_width': 1.0,
        }
    
    # Load and project points
    markers = load_custom_points(custom_points_json)
    if not markers:
        return
    
    # Project coordinates
    target_crs = g_proj.graph['crs']
    project_points(markers, target_crs)
    
    # Filter markers that are within the current view
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    
    visible_markers = [
        m for m in markers
        if xlim[0] <= m.map_x <= xlim[1] and ylim[0] <= m.map_y <= ylim[1]
    ]
    
    if not visible_markers:
        print("⚠ No markers visible in current map view")
        return
    
    print(f"✓ {len(visible_markers)} markers visible in map")
    
    # Calculate label positions
    if font_properties is None:
        font_properties = FontProperties(size=10)
    
    simple_label_layout(visible_markers, xlim, ylim, font_properties)
    
    # Draw all markers and labels
    for marker in visible_markers:
        draw_marker_and_label(
            ax,
            marker,
            font_properties=font_properties,
            **marker_config
        )
    
    print(f"✓ Drew {len(visible_markers)} markers with labels")


# Example integration code (to be added to create_map_poster.py)
"""
To integrate this into create_map_poster.py:

1. Import this module at the top:
   from custom_markers import add_custom_markers_to_poster

2. In the create_poster() function, after drawing the roads but before adding text:
   
   # After ox.plot_graph(...) and gradient fades
   # Before the final text labels
   
   # Add custom markers if JSON file exists
   custom_points_path = "my_custom_points.json"
   if os.path.exists(custom_points_path):
       marker_config = {
           'marker_color': THEME.get('marker_color', '#FAA95F'),
           'label_bg_color': THEME.get('label_bg_color', '#FFFFFF'),
           'label_border_color': THEME.get('label_border_color', THEME['text']),
           'text_color': THEME['text'],
           'line_color': THEME.get('line_color', THEME['text']),
       }
       
       add_custom_markers_to_poster(
           ax,
           g_proj,
           custom_points_path,
           font_properties=font_main_adjusted,  # or any other font
           marker_config=marker_config
       )
"""

if __name__ == "__main__":
    print("Custom Markers Module")
    print("=" * 50)
    print("This module provides functionality to add custom point markers")
    print("to map posters generated by create_map_poster.py")
    print()
    print("To use:")
    print("1. Place your my_custom_points.json in the same directory")
    print("2. Import and call add_custom_markers_to_poster() in create_poster()")
    print("=" * 50)