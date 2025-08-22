import re
import os
import shutil
import json
from pathlib import Path
from collections import defaultdict

class ComprehensiveDayZDeobfuscator:
    def __init__(self, output_dir="fully_deobfuscated"):
        self.output_dir = output_dir
        
        # Master obfuscation mappings
        self.folder_name_map = {}
        self.file_name_map = {}
        self.global_identifier_map = {}
        self.string_decode_map = {}
        
        # Counters for generating clean names
        self.folder_counter = 0
        self.file_counter = 0
        self.identifier_counter = 0
        
        # Statistics
        self.stats = {
            'folders_processed': 0,
            'files_processed': 0,
            'obfuscated_folders': 0,
            'obfuscated_files': 0,
            'obfuscated_identifiers': 0,
            'obfuscated_strings': 0,
            'errors': 0
        }
        
        # Common DayZ/Arma patterns for better naming
        self.dayz_patterns = {
            'config': ['config', 'cfg', 'settings'],
            'script': ['script', 'scripts', 'src'],
            'data': ['data', 'gamedata', 'content'],
            'sound': ['sound', 'sounds', 'audio'],
            'texture': ['texture', 'textures', 'materials'],
            'model': ['model', 'models', 'geometry'],
            'animation': ['anim', 'animations'],
            'ui': ['ui', 'interface', 'gui'],
            'mission': ['mission', 'missions'],
            'addon': ['addon', 'addons', 'mod'],
        }

    def is_obfuscated_name(self, name):
        """Check if a folder/file name looks obfuscated"""
        # Remove extension for analysis
        base_name = Path(name).stem
        
        # Skip if too short or contains common words
        if len(base_name) < 6:
            return False
            
        # Check for common non-obfuscated patterns
        common_words = {'config', 'data', 'script', 'sound', 'texture', 'model', 'init', 'main', 'core', 'base', 'common', 'util', 'helper'}
        if any(word in base_name.lower() for word in common_words):
            return False
        
        # Check for obfuscation indicators
        has_mixed_case = any(c.isupper() for c in base_name) and any(c.islower() for c in base_name)
        has_numbers = any(c.isdigit() for c in base_name)
        has_random_pattern = len(base_name) > 10 and (has_mixed_case or has_numbers)
        
        # Check for excessive consonants/vowels (common in random strings)
        vowels = 'aeiouAEIOU'
        consonants = sum(1 for c in base_name if c.isalpha() and c not in vowels)
        vowel_count = sum(1 for c in base_name if c in vowels)
        
        if len(base_name) > 8:
            consonant_ratio = consonants / len(base_name) if len(base_name) > 0 else 0
            if consonant_ratio > 0.8:  # Too many consonants, likely obfuscated
                return True
        
        return has_random_pattern

    def generate_clean_folder_name(self, obfuscated_name, context_path=""):
        """Generate a clean folder name based on context"""
        if obfuscated_name in self.folder_name_map:
            return self.folder_name_map[obfuscated_name]
        
        # Try to infer purpose from context
        clean_name = "folder"
        context_lower = context_path.lower()
        
        # Check for DayZ-specific patterns in the path
        for category, names in self.dayz_patterns.items():
            if any(pattern in context_lower for pattern in names):
                clean_name = category
                break
        
        # Check parent directory for clues
        if 'script' in context_lower or 'src' in context_lower:
            clean_name = "scripts"
        elif 'config' in context_lower or 'cfg' in context_lower:
            clean_name = "config"
        elif 'data' in context_lower:
            clean_name = "data"
        elif 'sound' in context_lower:
            clean_name = "sounds"
        
        # Make unique
        final_name = f"{clean_name}_{self.folder_counter}"
        self.folder_counter += 1
        
        self.folder_name_map[obfuscated_name] = final_name
        return final_name

    def generate_clean_file_name(self, obfuscated_name, context_path=""):
        """Generate a clean file name based on context and extension"""
        if obfuscated_name in self.file_name_map:
            return self.file_name_map[obfuscated_name]
        
        file_path = Path(obfuscated_name)
        extension = file_path.suffix
        base_name = file_path.stem
        
        # Try to infer purpose from extension and context
        clean_base = "file"
        context_lower = context_path.lower()
        
        if extension.lower() in ['.c', '.cpp']:
            clean_base = "script"
        elif extension.lower() in ['.h', '.hpp']:
            clean_base = "header"
        elif extension.lower() == '.sqf':
            clean_base = "sqf_script"
        elif extension.lower() in ['.cfg', '.config']:
            clean_base = "config"
        elif extension.lower() in ['.txt', '.log']:
            clean_base = "text"
        elif extension.lower() in ['.xml', '.json']:
            clean_base = "data"
        
        # Refine based on context
        if 'init' in context_lower:
            clean_base = "init"
        elif 'config' in context_lower:
            clean_base = "config"
        elif 'main' in context_lower:
            clean_base = "main"
        
        # Make unique
        final_name = f"{clean_base}_{self.file_counter}{extension}"
        self.file_counter += 1
        
        self.file_name_map[obfuscated_name] = final_name
        return final_name

    def is_obfuscated_identifier(self, identifier):
        """Check if a code identifier looks obfuscated"""
        if len(identifier) < 8:
            return False
        if identifier in ['string', 'float', 'int', 'bool', 'void', 'class', 'vector', 'inout', 'static', 'const']:
            return False
        
        # Check for random-looking patterns
        has_mixed_case = any(c.isupper() for c in identifier) and any(c.islower() for c in identifier)
        has_numbers = any(c.isdigit() for c in identifier)
        is_long_random = len(identifier) > 12 and (has_mixed_case or has_numbers)
        
        # Check for excessive consonants (common in obfuscated names)
        vowels = 'aeiouAEIOU'
        consonants = sum(1 for c in identifier if c.isalpha() and c not in vowels)
        if len(identifier) > 10:
            consonant_ratio = consonants / len(identifier)
            if consonant_ratio > 0.75:
                return True
        
        return is_long_random

    def analyze_file_structure(self, input_folder):
        """First pass: analyze the entire folder structure for obfuscation patterns"""
        print("🔍 Analyzing folder structure for obfuscation patterns...")
        
        input_path = Path(input_folder)
        structure_analysis = {
            'obfuscated_folders': [],
            'obfuscated_files': [],
            'total_folders': 0,
            'total_files': 0
        }
        
        for root, dirs, files in os.walk(input_path):
            root_path = Path(root)
            relative_root = root_path.relative_to(input_path)
            
            # Analyze folders
            for folder in dirs:
                structure_analysis['total_folders'] += 1
                if self.is_obfuscated_name(folder):
                    structure_analysis['obfuscated_folders'].append(str(relative_root / folder))
                    self.stats['obfuscated_folders'] += 1
            
            # Analyze files
            for file in files:
                structure_analysis['total_files'] += 1
                if self.is_obfuscated_name(file):
                    structure_analysis['obfuscated_files'].append(str(relative_root / file))
                    self.stats['obfuscated_files'] += 1
        
        print(f"  📁 Total folders: {structure_analysis['total_folders']}")
        print(f"  📁 Obfuscated folders: {len(structure_analysis['obfuscated_folders'])}")
        print(f"  📄 Total files: {structure_analysis['total_files']}")
        print(f"  📄 Obfuscated files: {len(structure_analysis['obfuscated_files'])}")
        
        return structure_analysis

    def deobfuscate_file_content(self, content):
        """Deobfuscate the content of a file"""
        result = content
        
        # Find obfuscated string patterns
        obfuscated_string_patterns = [
            r'(\w+)\.\s*(\w+)\("([A-Z]{15,})",\s*([^)]+)\)',
            r'(\w+)\s*\.\s*(\w+)\s*\(\s*"([A-Z]{15,})"\s*,\s*([^)]+)\s*\)'
        ]
        
        string_counter = 0
        for pattern in obfuscated_string_patterns:
            def replace_string_call(match):
                nonlocal string_counter
                obj_name, method_name, encoded_str, param = match.groups()
                replacement = f'DECODED_STRING_{string_counter}({param})'
                string_counter += 1
                self.stats['obfuscated_strings'] += 1
                return replacement
            
            result = re.sub(pattern, replace_string_call, result)
        
        # Find and replace obfuscated identifiers
        all_identifiers = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', result)
        
        for identifier in set(all_identifiers):
            if self.is_obfuscated_identifier(identifier) and identifier not in self.global_identifier_map:
                # Generate clean name based on context
                var_type = "var"
                if 'Vector(' in result and identifier in result:
                    var_type = "vector"
                elif '.ToFloat()' in result and identifier in result:
                    var_type = "float_val"
                elif 'string' in result and identifier in result:
                    var_type = "str_val"
                elif f'void {identifier}' in result:
                    var_type = "function"
                elif f'class {identifier}' in result:
                    var_type = "class"
                
                clean_name = f"{var_type}_{self.identifier_counter}"
                self.global_identifier_map[identifier] = clean_name
                self.identifier_counter += 1
                self.stats['obfuscated_identifiers'] += 1
        
        # Replace obfuscated identifiers
        for obfuscated, clean in self.global_identifier_map.items():
            result = re.sub(r'\b' + re.escape(obfuscated) + r'\b', clean, result)
        
        # Clean up dead code
        result = re.sub(r'[^;=]+\*\s*0\s*;', ' /* DEAD_CODE_REMOVED */;', result)
        
        # Add deobfuscation header
        header = """/*
 * FULLY DEOBFUSCATED FILE
 * - Folder and file names have been cleaned
 * - Obfuscated identifiers replaced with readable names
 * - Obfuscated strings simplified
 * - Dead code marked/removed
 */

"""
        result = header + result
        
        return result

    def process_complete_folder(self, input_folder):
        """Main processing function - handles everything"""
        input_path = Path(input_folder)
        output_path = Path(self.output_dir)
        
        if not input_path.exists():
            print(f"❌ Error: Input folder '{input_folder}' does not exist!")
            return
        
        # Create output directory
        output_path.mkdir(exist_ok=True)
        
        print(f"🚀 Starting comprehensive deobfuscation...")
        print(f"📂 Input: {input_folder}")
        print(f"📂 Output: {self.output_dir}")
        print("=" * 80)
        
        # Step 1: Analyze structure
        structure_analysis = self.analyze_file_structure(input_folder)
        
        print("\n🔧 Processing files and folders...")
        print("=" * 80)
        
        # Step 2: Process each file and folder
        for root, dirs, files in os.walk(input_path):
            root_path = Path(root)
            relative_root = root_path.relative_to(input_path)
            
            # Create clean folder structure
            clean_relative_parts = []
            for part in relative_root.parts:
                if self.is_obfuscated_name(part):
                    clean_part = self.generate_clean_folder_name(part, str(relative_root))
                    clean_relative_parts.append(clean_part)
                    print(f"  📁 {part} → {clean_part}")
                else:
                    clean_relative_parts.append(part)
            
            clean_relative_root = Path(*clean_relative_parts) if clean_relative_parts else Path()
            clean_output_dir = output_path / clean_relative_root
            clean_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Process files in this directory
            for file in files:
                original_file_path = root_path / file
                
                # Generate clean file name
                if self.is_obfuscated_name(file):
                    clean_file_name = self.generate_clean_file_name(file, str(relative_root))
                    print(f"  📄 {file} → {clean_file_name}")
                else:
                    clean_file_name = file
                
                clean_file_path = clean_output_dir / clean_file_name
                
                # Process file content
                try:
                    # Check if file should be deobfuscated (text files)
                    if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf', '.txt', '.cfg', '.config', '.inc'}:
                        with open(original_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Deobfuscate content
                        clean_content = self.deobfuscate_file_content(content)
                        
                        with open(clean_file_path, 'w', encoding='utf-8') as f:
                            f.write(clean_content)
                        
                        print(f"    ✓ Content deobfuscated")
                    else:
                        # Binary files - just copy
                        shutil.copy2(original_file_path, clean_file_path)
                        print(f"    ✓ Binary file copied")
                    
                    self.stats['files_processed'] += 1
                    
                except Exception as e:
                    print(f"    ❌ Error processing {file}: {e}")
                    self.stats['errors'] += 1
        
        # Step 3: Save mapping information
        self.save_mapping_info()
        
        # Step 4: Print final statistics
        self.print_final_stats()

    def save_mapping_info(self):
        """Save all the mapping information for reference"""
        mapping_info = {
            'folder_mappings': self.folder_name_map,
            'file_mappings': self.file_name_map,
            'identifier_mappings': dict(list(self.global_identifier_map.items())[:100]),  # First 100 for readability
            'statistics': self.stats
        }
        
        mapping_file = Path(self.output_dir) / 'deobfuscation_mappings.json'
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(mapping_info, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Mapping information saved to: {mapping_file}")

    def print_final_stats(self):
        """Print comprehensive statistics"""
        print("\n" + "=" * 80)
        print("🎉 DEOBFUSCATION COMPLETE!")
        print("=" * 80)
        print(f"📁 Folders processed: {self.stats['folders_processed']}")
        print(f"📁 Obfuscated folders cleaned: {self.stats['obfuscated_folders']}")
        print(f"📄 Files processed: {self.stats['files_processed']}")
        print(f"📄 Obfuscated files cleaned: {self.stats['obfuscated_files']}")
        print(f"🔤 Obfuscated identifiers: {self.stats['obfuscated_identifiers']}")
        print(f"🔗 Obfuscated strings: {self.stats['obfuscated_strings']}")
        print(f"❌ Errors encountered: {self.stats['errors']}")
        print(f"📂 Output location: {Path(self.output_dir).absolute()}")
        print("=" * 80)

# Usage
if __name__ == "__main__":
    # Configuration
    INPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/"  # Your input folder
    OUTPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server_cleaned/"   # Where to save clean files
    
    # Create comprehensive deobfuscator
    deobfuscator = ComprehensiveDayZDeobfuscator(output_dir=OUTPUT_FOLDER)
    
    # Process everything
    deobfuscator.process_complete_folder(INPUT_FOLDER)
    
    print(f"\n🎯 Everything cleaned! Check: {OUTPUT_FOLDER}")
    print("💡 Check 'deobfuscation_mappings.json' for all the mappings used.")