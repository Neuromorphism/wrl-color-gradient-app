#!/usr/bin/env python3
"""
WRL Color Gradient App - Apply cylindrical color gradients to VRML files.
"""

import argparse
import sys
import math
from pathlib import Path
from typing import List, Tuple, Dict
import re


class WRLColorGradient:
    """Apply color gradients to WRL/VRML files using cylindrical coordinates."""
    
    def __init__(self, color_outside: Tuple[int, int, int] = (255, 0, 0),
                 color_inside: Tuple[int, int, int] = (0, 0, 255)):
        """
        Initialize the gradient applier.
        
        Args:
            color_outside: RGB tuple for exterior color (default: red)
            color_inside: RGB tuple for interior color (default: blue)
        """
        self.color_outside = color_outside
        self.color_inside = color_inside
        self.vertices = []
        self.vertex_colors = {}
        self.wrl_content = ""
        
    def parse_hex_color(self, hex_color: str) -> Tuple[int, int, int]:
        """Parse hex color string to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            raise ValueError(f"Invalid hex color: {hex_color}")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_normalized(self, rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Convert RGB (0-255) to normalized (0-1) values."""
        return tuple(c / 255.0 for c in rgb)
    
    def normalized_to_rgb(self, normalized: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """Convert normalized (0-1) values to RGB (0-255)."""
        return tuple(int(c * 255) for c in normalized)
    
    def interpolate_color(self, t: float) -> Tuple[float, float, float]:
        """
        Interpolate between outside and inside colors.
        
        Args:
            t: Interpolation parameter (0 = outside color, 1 = inside color)
            
        Returns:
            Normalized RGB tuple (0-1 range)
        """
        t = max(0, min(1, t))  # Clamp to [0, 1]
        outside_norm = self.rgb_to_normalized(self.color_outside)
        inside_norm = self.rgb_to_normalized(self.color_inside)
        
        interpolated = tuple(
            outside_norm[i] * (1 - t) + inside_norm[i] * t
            for i in range(3)
        )
        return interpolated
    
    def load_wrl(self, filepath: str) -> None:
        """Load WRL file content."""
        with open(filepath, 'r') as f:
            self.wrl_content = f.read()
    
    def extract_vertices(self) -> List[Tuple[float, float, float]]:
        """Extract vertex coordinates from WRL file."""
        vertices = []
        
        # Pattern to match coordinate arrays in WRL files
        # Looks for "point [" followed by coordinates
        point_pattern = r'point\s*\[\s*([\d\s\.\-eE,]+?)\s*\]'
        matches = re.finditer(point_pattern, self.wrl_content, re.IGNORECASE)
        
        for match in matches:
            coords_str = match.group(1)
            # Split by comma or whitespace and parse floats
            coords = re.findall(r'-?\d+\.?\d*(?:[eE]-?\d+)?', coords_str)
            
            # Group into triplets (x, y, z)
            for i in range(0, len(coords) - 2, 3):
                try:
                    x = float(coords[i])
                    y = float(coords[i + 1])
                    z = float(coords[i + 2])
                    vertices.append((x, y, z))
                except (ValueError, IndexError):
                    continue
        
        self.vertices = vertices
        return vertices
    
    def calculate_cylindrical_radius(self, vertex: Tuple[float, float, float]) -> float:
        """
        Calculate radial distance from Z axis in cylindrical coordinates.
        
        Args:
            vertex: (x, y, z) coordinates
            
        Returns:
            Radial distance from Z axis (sqrt(x^2 + y^2))
        """
        x, y, z = vertex
        return math.sqrt(x**2 + y**2)
    
    def calculate_gradient_colors(self) -> Dict[int, Tuple[float, float, float]]:
        """
        Calculate interpolated colors for all vertices based on radial distance.
        
        Returns:
            Dictionary mapping vertex index to normalized RGB color tuple
        """
        if not self.vertices:
            raise ValueError("No vertices loaded. Call extract_vertices() first.")
        
        # Find min and max radial distances
        radii = [self.calculate_cylindrical_radius(v) for v in self.vertices]
        min_radius = min(radii) if radii else 0
        max_radius = max(radii) if radii else 1
        
        # Avoid division by zero
        radius_range = max_radius - min_radius if max_radius > min_radius else 1
        
        colors = {}
        for idx, (vertex, radius) in enumerate(zip(self.vertices, radii)):
            # Normalize radius to [0, 1] where 0 = center, 1 = exterior
            # Invert so that exterior (max_radius) = 0 (outside color)
            # and center (min_radius) = 1 (inside color)
            normalized_distance = (radius - min_radius) / radius_range
            t = 1 - normalized_distance  # Invert: exterior -> inside
            
            interpolated_color = self.interpolate_color(t)
            colors[idx] = interpolated_color
        
        self.vertex_colors = colors
        return colors
    
    def apply_colors_to_wrl(self) -> str:
        """
        Apply calculated colors to the WRL file by adding or updating color information.
        
        Returns:
            Modified WRL content with color information
        """
        if not self.vertex_colors:
            raise ValueError("No colors calculated. Call calculate_gradient_colors() first.")
        
        modified_content = self.wrl_content
        
        # Convert colors to WRL format (0-1 range)
        color_string = "color [\n"
        for idx in sorted(self.vertex_colors.keys()):
            r, g, b = self.vertex_colors[idx]
            color_string += f"  {r:.4f} {g:.4f} {b:.4f}\n"
        color_string += "]"
        
        # Find the appropriate IndexedFaceSet or similar geometry node
        # and insert color information
        geometry_pattern = r'(IndexedFaceSet\s*\{[^}]*?)(coordIndex|normalIndex)'
        
        def add_color(match):
            return match.group(1) + f"  {color_string}\n    " + match.group(2)
        
        modified_content = re.sub(geometry_pattern, add_color, modified_content, flags=re.DOTALL)
        
        return modified_content
    
    def save_wrl(self, output_filepath: str, content: str) -> None:
        """Save modified WRL file."""
        Path(output_filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(output_filepath, 'w') as f:
            f.write(content)
        print(f"✓ Saved colored WRL to: {output_filepath}")
    
    def process_file(self, input_filepath: str, output_filepath: str = None) -> str:
        """
        Process a WRL file end-to-end.
        
        Args:
            input_filepath: Path to input WRL file
            output_filepath: Path for output WRL file (optional)
            
        Returns:
            Modified WRL content
        """
        if output_filepath is None:
            base = Path(input_filepath).stem
            ext = Path(input_filepath).suffix
            output_filepath = f"{base}_colored{ext}"
        
        print(f"Loading WRL file: {input_filepath}")
        self.load_wrl(input_filepath)
        
        print("Extracting vertices...")
        vertices = self.extract_vertices()
        print(f"  Found {len(vertices)} vertices")
        
        if not vertices:
            raise ValueError("No vertices found in WRL file. Check file format.")
        
        print("Calculating color gradients (cylindrical coordinates)...")
        self.calculate_gradient_colors()
        
        print("Applying colors to geometry...")
        modified_content = self.apply_colors_to_wrl()
        
        self.save_wrl(output_filepath, modified_content)
        
        return output_filepath


def hex_color(value: str) -> Tuple[int, int, int]:
    """Argument parser for hex color."""
    try:
        value = value.lstrip('#')
        if len(value) != 6:
            raise ValueError()
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    except:
        raise argparse.ArgumentTypeError(f"Invalid hex color: {value}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Apply a cylindrical color gradient to WRL/VRML files. "
                    "Colors grade from exterior (red) to interior (blue) based on "
                    "radial distance from the Z axis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wrl-color-gradient input.wrl
  wrl-color-gradient input.wrl -o output.wrl
  wrl-color-gradient input.wrl --outside FF0000 --inside 0000FF
  wrl-color-gradient input.wrl --outside #00FF00 --inside #FF00FF
"""
    )
    
    parser.add_argument(
        'input',
        help='Input WRL/VRML file'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output WRL file (default: input_colored.wrl)',
        default=None
    )
    
    parser.add_argument(
        '--outside',
        type=hex_color,
        default=(255, 0, 0),
        help='Hex color for exterior (default: FF0000 - red)'
    )
    
    parser.add_argument(
        '--inside',
        type=hex_color,
        default=(0, 0, 255),
        help='Hex color for interior (default: 0000FF - blue)'
    )
    
    args = parser.parse_args()
    
    try:
        # Check if input file exists
        if not Path(args.input).exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        
        # Create processor with specified colors
        processor = WRLColorGradient(
            color_outside=args.outside,
            color_inside=args.inside
        )
        
        # Process the file
        output_file = processor.process_file(args.input, args.output)
        print(f"\n✓ Processing complete!")
        print(f"  Input:  {args.input}")
        print(f"  Output: {output_file}")
        print(f"  Color gradient: {args.outside} (outside) → {args.inside} (inside)")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()