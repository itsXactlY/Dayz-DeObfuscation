import re
import os
import hashlib

class DayZDeobfuscator:
    def __init__(self):
        # Common DayZ/Arma variable patterns to help identify what obfuscated vars might represent
        self.common_patterns = {
            'Vector': ['position', 'rotation', 'scale', 'direction'],
            'ToFloat': ['value', 'amount', 'distance', 'time', 'damage'],
            'String': ['name', 'path', 'id', 'type']
        }
        
        # Track obfuscated identifiers and try to give them meaningful names
        self.identifier_map = {}
        self.string_decode_map = {}
        
    def analyze_obfuscated_strings(self, content):
        """Extract and analyze obfuscated string patterns"""
        # Find all obfuscated string calls
        pattern = r'SfFuxbdumezDa91W\.\s*Ns7IynOBl5RX6MyZ\("([A-Z]+)",\s*([^)]+)\)'
        matches = re.findall(pattern, content)
        
        print(f"Found {len(matches)} obfuscated string calls:")
        for i, (encoded_str, param) in enumerate(matches):
            print(f"  {i+1}: {encoded_str[:20]}... -> {param}")
        
        return matches
    
    def generate_readable_names(self, content):
        """Generate more readable variable names based on context"""
        # Find all obfuscated identifiers
        obfuscated_vars = re.findall(r'\b[A-Za-z][A-Za-z0-9_]{10,}\b', content)
        obfuscated_vars = list(set(obfuscated_vars))  # Remove duplicates
        
        for i, var in enumerate(obfuscated_vars):
            if var not in self.identifier_map:
                # Try to infer purpose from context
                if 'Vector' in content and var in content:
                    self.identifier_map[var] = f"vector_{i}"
                elif '.ToFloat()' in content and var in content:
                    self.identifier_map[var] = f"float_value_{i}"
                elif 'SfFuxbdumezDa91W' in var:
                    self.identifier_map[var] = "decoder_instance"
                elif 'Ns7IynOBl5RX6MyZ' in var:
                    self.identifier_map[var] = "decode_method"
                else:
                    self.identifier_map[var] = f"var_{i}"
    
    def deobfuscate_content(self, content):
        """Main deobfuscation logic"""
        result = content
        
        # Replace obfuscated identifiers with readable names
        for obfuscated, readable in self.identifier_map.items():
            result = re.sub(r'\b' + re.escape(obfuscated) + r'\b', readable, result)
        
        # Clean up the decoder calls - replace with comments showing what they were
        def replace_decoder_call(match):
            encoded_str = match.group(1)
            param = match.group(2)
            return f"/* DECODED_STRING_{len(encoded_str)} */ \"DECODED_VALUE\""
        
        result = re.sub(
            r'decoder_instance\.\s*decode_method\("([A-Z]+)",\s*([^)]+)\)',
            replace_decoder_call,
            result
        )
        
        # Remove dead code (operations multiplied by 0)
        result = re.sub(r'[^;]+\*0;', '/* DEAD_CODE_REMOVED */;', result)
        
        # Add comments explaining hash operations
        result = re.sub(
            r'(\([^)]+\.Hash\(\)[^;]+;)',
            r'/* HASH_OPERATION */ \1',
            result
        )
        
        return result
    
    def process_file(self, file_path):
        """Process a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            print(f"\nProcessing: {file_path}")
            
            # Analyze the obfuscation
            self.analyze_obfuscated_strings(content)
            self.generate_readable_names(content)
            
            # Deobfuscate
            deobfuscated = self.deobfuscate_content(content)
            
            # Save deobfuscated version
            output_path = file_path.replace('.', '_deobfuscated.')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(deobfuscated)
            
            print(f"Saved deobfuscated version: {output_path}")
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    def process_folder(self, folder_path):
        """Process all relevant files in a folder"""
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(('.c', '.cpp', '.h', '.hpp', '.sqf')):
                    file_path = os.path.join(root, file)
                    self.process_file(file_path)

# Usage
if __name__ == "__main__":
    deobfuscator = DayZDeobfuscator()
    
    # Process a single file
    # deobfuscator.process_file("path/to/your/obfuscated_file.c")
    
    # Or process entire folder
    # deobfuscator.process_folder("path/to/your/pbo_extracted_folder")
    
    # For testing with your sample
    sample_code = """
    void GA91UCDQYUVawLMs_(inout string GA91UCDQYUVawLMs, T4QPEBrB2xOEx7Qc HBxPZfXX0BhgSqUF) {
        XwNVHEpPn99kw7kp = SfFuxbdumezDa91W. Ns7IynOBl5RX6MyZ("HCOJJAGJHPOKCHJEIEPCCIGNHJDLGJPOBGIGNLFHOFIO", HBxPZfXX0BhgSqUF).ToFloat();
        X4J54X5KqlZcrCSi = (-547234341 - GA91UCDQYUVawLMs.Substring(35, 8).Hash() * 1983144419 ) ^ -1899935677 + GA91UCDQYUVawLMs.Replace("50", "05")*0;
    }
    """
    
    deobfuscator.generate_readable_names(sample_code)
    print("\nSample deobfuscated:")
    print(deobfuscator.deobfuscate_content(sample_code))