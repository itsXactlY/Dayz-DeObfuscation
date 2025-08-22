#!/usr/bin/env python3
"""
ML-Based Code Deobfuscator
Uses various techniques to restore meaningful identifiers from obfuscated code
"""

import re
import json
import pickle
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
import argparse

class CodeDeobfuscator:
    def __init__(self):
        self.identifier_map = {}
        self.context_patterns = {}
        self.api_mappings = {}
        self.load_dayz_api_knowledge()
        
    def load_dayz_api_knowledge(self):
        """Load known DayZ API patterns and common identifiers"""
        # Known DayZ API patterns (you can expand this)
        self.api_mappings = {
            # Game state checks
            r'\.IsMultiplayer\(\)': 'IsMultiplayer',
            r'\.IsClient\(\)': 'IsClient', 
            r'\.IsServer\(\)': 'IsServer',
            r'\.GetMission\(\)': 'GetMission',
            
            # Common return patterns
            r'return\s+1;': 'return_success',
            r'return\s+-1;': 'return_error',
            r'return\s+0;': 'return_false',
            
            # Cast operations
            r'\.Cast\(': 'Cast',
            
            # Common checks
            r'==\s*\w+\)?\s*return\s+-1;': 'null_check_pattern'
        }
        
        # Common DayZ class prefixes and their likely meanings
        self.class_hints = {
            'Player': ['player', 'character', 'survivor'],
            'Mission': ['mission', 'game', 'session'],
            'World': ['world', 'environment', 'game_world'],
            'Item': ['item', 'object', 'entity'],
            'Config': ['config', 'configuration', 'settings'],
            'Manager': ['manager', 'controller', 'handler'],
            'System': ['system', 'subsystem', 'service']
        }

    def analyze_identifier_context(self, code: str) -> Dict[str, Dict[str, int]]:
        """Analyze how identifiers are used to infer their purpose"""
        context_analysis = defaultdict(lambda: defaultdict(int))
        
        # Find all identifiers
        identifiers = re.findall(r'\b[A-Za-z][A-Za-z0-9]{2,}\b', code)
        
        for identifier in identifiers:
            # Check usage patterns
            patterns = [
                (rf'{identifier}\.IsMultiplayer\(\)', 'game_state_checker'),
                (rf'{identifier}\.IsClient\(\)', 'game_state_checker'),
                (rf'{identifier}\.IsServer\(\)', 'game_state_checker'),
                (rf'{identifier}\.Cast\(', 'casting_source'),
                (rf'\.Cast\({identifier}\)', 'casting_target'),
                (rf'{identifier}\s*==\s*null', 'nullable_object'),
                (rf'if\s*\({identifier}\)', 'condition_object'),
                (rf'return\s+{identifier}', 'return_value'),
                (rf'{identifier}\.\w+\(\)', 'method_caller'),
                (rf'ref\s+\w+\s*<.*?>\s*{identifier}', 'generic_container'),
                (rf'static\s+\w+\s+{identifier}\(', 'static_method'),
                (rf'class\s+{identifier}', 'class_name')
            ]
            
            for pattern, context_type in patterns:
                if re.search(pattern, code):
                    context_analysis[identifier][context_type] += 1
        
        return context_analysis

    def infer_identifier_meaning(self, identifier: str, context: Dict[str, int], code: str) -> str:
        """Use ML-like heuristics to infer what an identifier represents"""
        
        # Rule-based inference system
        score_map = defaultdict(float)
        
        # Context-based scoring
        if 'game_state_checker' in context:
            score_map['game_instance'] += 3.0
            score_map['mission'] += 2.0
            
        if 'casting_source' in context:
            score_map['base_object'] += 2.0
            
        if 'casting_target' in context:
            score_map['specific_type'] += 2.0
            
        if 'method_caller' in context:
            score_map['object_instance'] += 1.5
            
        if 'class_name' in context:
            score_map['class'] += 3.0
            
        if 'static_method' in context:
            score_map['utility_function'] += 2.0
            
        if 'return_value' in context:
            score_map['result'] += 1.0
            
        if 'nullable_object' in context:
            score_map['optional_object'] += 1.0
            
        # Pattern-based inference
        if re.search(rf'{identifier}\.Count\(\)|{identifier}\.prWSpdaVXepJJMArnq\(\)', code):
            score_map['collection'] += 2.0
            
        # Length-based heuristics (longer obfuscated names often represent more important things)
        if len(identifier) > 15:
            score_map['important_object'] += 0.5
            
        # Generate meaningful name based on highest scoring category
        if not score_map:
            return f"unknown_{identifier[:3]}"
            
        top_category = max(score_map, key=score_map.get)
        
        name_map = {
            'game_instance': 'game',
            'mission': 'mission',
            'base_object': 'baseObj',
            'specific_type': 'typedObj',
            'object_instance': 'instance',
            'class': 'CustomClass',
            'utility_function': 'UtilFunc',
            'result': 'result',
            'optional_object': 'optionalObj',
            'collection': 'collection',
            'important_object': 'mainObject'
        }
        
        return name_map.get(top_category, f"obj_{identifier[:3]}")

    def build_identifier_map(self, code: str) -> Dict[str, str]:
        """Build a mapping from obfuscated to meaningful identifiers"""
        context_analysis = self.analyze_identifier_context(code)
        identifier_map = {}
        
        # Sort by usage frequency and context richness
        sorted_identifiers = sorted(
            context_analysis.items(),
            key=lambda x: (sum(x[1].values()), len(x[1])),
            reverse=True
        )
        
        used_names = set()
        
        for identifier, context in sorted_identifiers:
            # Skip very short identifiers (likely not obfuscated)
            if len(identifier) < 4:
                continue
                
            meaningful_name = self.infer_identifier_meaning(identifier, context, code)
            
            # Avoid duplicates
            base_name = meaningful_name
            counter = 1
            while meaningful_name in used_names:
                meaningful_name = f"{base_name}_{counter}"
                counter += 1
                
            identifier_map[identifier] = meaningful_name
            used_names.add(meaningful_name)
            
        return identifier_map

    def apply_deobfuscation(self, code: str, identifier_map: Dict[str, str]) -> str:
        """Apply the identifier mapping to deobfuscate code"""
        deobfuscated = code
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_mappings = sorted(identifier_map.items(), key=lambda x: len(x[0]), reverse=True)
        
        for obfuscated, meaningful in sorted_mappings:
            # Use word boundaries to avoid partial matches
            pattern = rf'\b{re.escape(obfuscated)}\b'
            deobfuscated = re.sub(pattern, meaningful, deobfuscated)
            
        return deobfuscated

    def enhance_readability(self, code: str) -> str:
        """Additional readability improvements"""
        enhanced = code
        
        # Add comments for common patterns
        patterns = [
            (r'if\s*\(!.*\.IsMultiplayer\(\)\)', '// Single player check'),
            (r'if\s*\(.*\.IsClient\(\)\)', '// Client-side check'),
            (r'if\s*\(.*\.IsServer\(\)\)', '// Server-side check'),
            (r'return\s+-1;', '// Return error/invalid state'),
            (r'return\s+1;', '// Return success/valid state'),
        ]
        
        for pattern, comment in patterns:
            enhanced = re.sub(f'({pattern})', rf'\1 {comment}', enhanced)
        
        return enhanced

    def deobfuscate_code(self, code: str) -> Tuple[str, Dict[str, str]]:
        """Main deobfuscation method"""
        print("Analyzing code structure...")
        identifier_map = self.build_identifier_map(code)
        
        print(f"Found {len(identifier_map)} obfuscated identifiers")
        
        print("Applying deobfuscation...")
        deobfuscated = self.apply_deobfuscation(code, identifier_map)
        
        print("Enhancing readability...")
        enhanced = self.enhance_readability(deobfuscated)
        
        return enhanced, identifier_map

def process_file(input_path: Path, output_path: Path, show_mapping: bool = False):
    """Process a single file"""
    deobfuscator = CodeDeobfuscator()
    
    try:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            original_code = f.read()
    except:
        with open(input_path, 'r', encoding='latin-1') as f:
            original_code = f.read()
    
    deobfuscated_code, mapping = deobfuscator.deobfuscate_code(original_code)
    
    # Write deobfuscated code
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(deobfuscated_code)
    
    if show_mapping:
        print("\nIdentifier Mappings:")
        print("-" * 40)
        for obf, clean in sorted(mapping.items()):
            print(f"{obf:<20} -> {clean}")
    
    return len(mapping)

def main():
    parser = argparse.ArgumentParser(description='ML-based code deobfuscator for DayZ mods')
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('-o', '--output', help='Output file or directory')
    parser.add_argument('-m', '--show-mapping', action='store_true', help='Show identifier mappings')
    parser.add_argument('-r', '--recursive', action='store_true', help='Process directories recursively')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: {input_path} does not exist")
        return 1
    
    if input_path.is_file():
        # Single file processing
        output_path = Path(args.output) if args.output else input_path.with_suffix('.deobf' + input_path.suffix)
        
        print(f"Deobfuscating: {input_path}")
        mappings_count = process_file(input_path, output_path, args.show_mapping)
        print(f"Completed! Deobfuscated {mappings_count} identifiers")
        print(f"Output saved to: {output_path}")
        
    else:
        # Directory processing
        output_dir = Path(args.output) if args.output else input_path.parent / f"{input_path.name}_deobfuscated"
        output_dir.mkdir(exist_ok=True)
        
        pattern = "**/*.c" if args.recursive else "*.c"
        files = list(input_path.glob(pattern))
        
        if not files:
            print("No .c files found")
            return 1
        
        total_mappings = 0
        for file_path in files:
            rel_path = file_path.relative_to(input_path)
            output_file = output_dir / rel_path
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"Processing: {rel_path}")
            mappings_count = process_file(file_path, output_file)
            total_mappings += mappings_count
        
        print(f"\nCompleted! Processed {len(files)} files")
        print(f"Total identifiers deobfuscated: {total_mappings}")
        print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    exit(main())