import re
import os
import shutil
from pathlib import Path

class DayZDeobfuscator:
    def __init__(self, output_dir="deobfuscated_output"):
        self.output_dir = output_dir
        # Common DayZ/Arma variable patterns to help identify what obfuscated vars might represent
        self.common_patterns = {
            'Vector': ['position', 'rotation', 'scale', 'direction'],
            'ToFloat': ['value', 'amount', 'distance', 'time', 'damage'],
            'String': ['name', 'path', 'id', 'type']
        }
        
        # Global identifier mapping to maintain consistency across files
        self.global_identifier_map = {}
        self.identifier_counter = 0
        
        # Statistics
        self.processed_files = 0
        self.skipped_files = 0
        self.total_obfuscated_strings = 0
        
    def is_obfuscated_identifier(self, identifier):
        """Check if an identifier looks obfuscated"""
        # Skip common keywords and short identifiers
        if len(identifier) < 8:
            return False
        if identifier in ['string', 'float', 'int', 'bool', 'void', 'class', 'vector', 'inout']:
            return False
        
        # Check for random-looking patterns
        has_mixed_case = any(c.isupper() for c in identifier) and any(c.islower() for c in identifier)
        has_numbers = any(c.isdigit() for c in identifier)
        is_long_random = len(identifier) > 12 and (has_mixed_case or has_numbers)
        
        return is_long_random

    def analyze_obfuscated_strings(self, content):
        """Extract and analyze obfuscated string patterns"""
        # Find all obfuscated string calls with various spacing patterns
        patterns = [
            r'(\w+)\.\s*(\w+)\("([A-Z]{20,})",\s*([^)]+)\)',  # Main pattern
            r'(\w+)\s*\.\s*(\w+)\s*\(\s*"([A-Z]{20,})"\s*,\s*([^)]+)\s*\)'  # With more spaces
        ]
        
        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            all_matches.extend(matches)
        
        self.total_obfuscated_strings += len(all_matches)
        return all_matches

    def generate_readable_names(self, content):
        """Generate more readable variable names based on context"""
        # Find all potential obfuscated identifiers
        all_identifiers = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', content)
        
        for identifier in set(all_identifiers):
            if self.is_obfuscated_identifier(identifier) and identifier not in self.global_identifier_map:
                # Try to infer purpose from context
                context_lines = [line for line in content.split('\n') if identifier in line]
                
                var_type = "var"
                if any('Vector(' in line for line in context_lines):
                    var_type = "vector"
                elif any('.ToFloat()' in line for line in context_lines):
                    var_type = "float_val"
                elif any('string' in line for line in context_lines):
                    var_type = "str_val"
                elif any('void ' in line and '(' in line for line in context_lines):
                    var_type = "function"
                elif any('class ' in line for line in context_lines):
                    var_type = "class"
                elif identifier.endswith('_'):
                    var_type = "method"
                
                self.global_identifier_map[identifier] = f"{var_type}_{self.identifier_counter}"
                self.identifier_counter += 1

    def clean_dead_code(self, content):
        """Remove obvious dead code patterns"""
        # Remove operations multiplied by 0
        content = re.sub(r'[^;=]+\*\s*0\s*;', ' /* DEAD_CODE_REMOVED */;', content)
        
        # Remove empty operations that don't affect anything
        content = re.sub(r'\+\s*[^;]*\*\s*0', ' /* + DEAD_CODE_REMOVED */', content)
        
        return content

    def deobfuscate_content(self, content):
        """Main deobfuscation logic"""
        result = content
        
        # First pass: identify obfuscated strings and replace them
        obfuscated_calls = self.analyze_obfuscated_strings(result)
        
        call_counter = 0
        for obj_name, method_name, encoded_str, param in obfuscated_calls:
            # Replace the entire obfuscated call with a placeholder
            old_pattern = f'{obj_name}.{method_name}("{encoded_str}", {param})'
            new_replacement = f'DECODED_STRING_{call_counter}({param})'
            result = result.replace(old_pattern, new_replacement)
            call_counter += 1
        
        # Generate readable names for remaining obfuscated identifiers
        self.generate_readable_names(result)
        
        # Replace obfuscated identifiers with readable names
        for obfuscated, readable in self.global_identifier_map.items():
            # Use word boundaries to avoid partial replacements
            result = re.sub(r'\b' + re.escape(obfuscated) + r'\b', readable, result)
        
        # Clean up dead code
        result = self.clean_dead_code(result)
        
        # Add header comment
        header = """/*
 * DEOBFUSCATED FILE
 * Original obfuscated identifiers have been replaced with readable names
 * Obfuscated string calls have been simplified
 * Dead code has been marked or removed
 */

"""
        result = header + result
        
        return result

    def should_process_file(self, file_path):
        """Determine if a file should be processed based on extension and content"""
        # Check file extension
        valid_extensions = {'.c', '.cpp', '.h', '.hpp', '.sqf', '.inc', '.txt'}
        if not any(file_path.suffix.lower() == ext for ext in valid_extensions):
            return False
        
        # Check if file contains obfuscated patterns
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Look for signs of obfuscation
            has_long_identifiers = bool(re.search(r'\b[A-Za-z0-9_]{15,}\b', content))
            has_obfuscated_strings = bool(re.search(r'"[A-Z]{20,}"', content))
            
            return has_long_identifiers or has_obfuscated_strings
            
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return False

    def process_file(self, input_path, relative_path):
        """Process a single file"""
        try:
            with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Create output directory structure
            output_file_path = Path(self.output_dir) / relative_path
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"Processing: {relative_path}")
            
            # Deobfuscate
            deobfuscated = self.deobfuscate_content(content)
            
            # Save deobfuscated version
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(deobfuscated)
            
            self.processed_files += 1
            print(f"  ✓ Saved to: {output_file_path}")
            
        except Exception as e:
            print(f"  ✗ Error processing {input_path}: {e}")
            self.skipped_files += 1

    def copy_non_obfuscated_file(self, input_path, relative_path):
        """Copy files that don't need deobfuscation"""
        try:
            output_file_path = Path(self.output_dir) / relative_path
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, output_file_path)
            print(f"Copied (no obfuscation): {relative_path}")
        except Exception as e:
            print(f"Error copying {input_path}: {e}")

    def process_folder(self, input_folder):
        """Process all files in a folder recursively"""
        input_path = Path(input_folder)
        output_path = Path(self.output_dir)
        
        if not input_path.exists():
            print(f"Error: Input folder '{input_folder}' does not exist!")
            return
        
        # Create output directory
        output_path.mkdir(exist_ok=True)
        
        print(f"Processing folder: {input_folder}")
        print(f"Output directory: {self.output_dir}")
        print("=" * 60)
        
        # Walk through all files
        all_files = []
        for root, dirs, files in os.walk(input_path):
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(input_path)
                all_files.append((file_path, relative_path))
        
        print(f"Found {len(all_files)} files to examine")
        print("=" * 60)
        
        # Process each file
        for file_path, relative_path in all_files:
            if self.should_process_file(file_path):
                self.process_file(file_path, relative_path)
            else:
                # Copy non-obfuscated files as-is
                self.copy_non_obfuscated_file(file_path, relative_path)
        
        # Print statistics
        print("=" * 60)
        print("PROCESSING COMPLETE!")
        print(f"Files processed (deobfuscated): {self.processed_files}")
        print(f"Files copied (clean): {len(all_files) - self.processed_files - self.skipped_files}")
        print(f"Files skipped (errors): {self.skipped_files}")
        print(f"Total obfuscated strings found: {self.total_obfuscated_strings}")
        print(f"Unique obfuscated identifiers: {len(self.global_identifier_map)}")
        print(f"Output saved to: {Path(self.output_dir).absolute()}")

# Usage
if __name__ == "__main__":
    # Configuration
    INPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/"  # Your input folder
    OUTPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server_cleaned/"   # Where to save clean files
    
    # Create deobfuscator instance
    deobfuscator = DayZDeobfuscator(output_dir=OUTPUT_FOLDER)
    
    # Process the entire folder
    deobfuscator.process_folder(INPUT_FOLDER)
    
    print(f"\n🎉 All done! Check your clean files in: {OUTPUT_FOLDER}")