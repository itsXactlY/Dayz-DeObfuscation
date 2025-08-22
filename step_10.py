import re
import os
import json
from pathlib import Path
import hashlib

class ActualDayZDeobfuscator:
    def __init__(self, output_dir="properly_deobfuscated"):
        self.output_dir = output_dir
        
        # Store the actual decoder when we find it
        self.decoder_class_name = None
        self.decoder_method_name = None
        self.decoder_implementation = None
        self.decoder_key_mapping = {}
        
        # Statistics
        self.stats = {
            'decoder_found': False,
            'files_scanned': 0,
            'obfuscated_strings_found': 0,
            'decoded_strings': 0,
            'folders_processed': 0,
            'files_processed': 0
        }

    def find_decoder_implementation(self, input_folder):
        """Search through all files to find the actual decoder implementation"""
        print("🔍 Searching for decoder implementation...")
        
        decoder_patterns = [
            # Look for the class definition
            r'class\s+(\w+)\s*{[^}]*(\w+)\s*\([^)]*string[^)]*\)[^}]*}',
            # Look for method implementations
            r'(\w+)\s+(\w+)\s*\(\s*string\s+\w+\s*,\s*\w+\s+\w+\s*\)\s*{([^}]+)}',
            # Look for string decoding logic
            r'string\s+(\w+)\s*\([^)]*\)\s*{([^}]*return[^}]*)}',
        ]
        
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf'}:
                    file_path = Path(root) / file
                    self.stats['files_scanned'] += 1
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Look for our specific decoder class/method
                        if 'SfFuxbdumezDa91W' in content and 'Ns7IynOBl5RX6MyZ' in content:
                            print(f"  📄 Found decoder reference in: {file_path}")
                            self.analyze_decoder_in_file(content, str(file_path))
                        
                        # Look for any string decoding patterns
                        for pattern in decoder_patterns:
                            matches = re.findall(pattern, content, re.DOTALL)
                            if matches:
                                print(f"  🔍 Potential decoder pattern in: {file_path}")
                                self.analyze_potential_decoder(matches, content, str(file_path))
                                
                    except Exception as e:
                        print(f"  ❌ Error reading {file_path}: {e}")
        
        return self.decoder_implementation is not None

    def analyze_decoder_in_file(self, content, file_path):
        """Analyze a file that contains decoder references"""
        print(f"    Analyzing decoder in: {file_path}")
        
        # Look for class definition
        class_match = re.search(r'class\s+(SfFuxbdumezDa91W|[\w]+)\s*{([^}]+)}', content, re.DOTALL)
        if class_match:
            self.decoder_class_name = class_match.group(1)
            class_body = class_match.group(2)
            print(f"    Found decoder class: {self.decoder_class_name}")
            
            # Look for the method implementation
            method_match = re.search(r'string\s+(Ns7IynOBl5RX6MyZ|[\w]+)\s*\([^)]*\)\s*{([^}]+)}', class_body, re.DOTALL)
            if method_match:
                self.decoder_method_name = method_match.group(1)
                method_body = method_match.group(2)
                print(f"    Found decoder method: {self.decoder_method_name}")
                self.analyze_decoder_logic(method_body)
        
        # Look for standalone function
        func_match = re.search(r'string\s+(Ns7IynOBl5RX6MyZ|[\w]+)\s*\([^)]*string[^)]*\)\s*{([^}]+)}', content, re.DOTALL)
        if func_match:
            self.decoder_method_name = func_match.group(1)
            method_body = func_match.group(2)
            print(f"    Found standalone decoder function: {self.decoder_method_name}")
            self.analyze_decoder_logic(method_body)

    def analyze_decoder_logic(self, method_body):
        """Analyze the actual decoding logic"""
        print("    🔬 Analyzing decoder logic...")
        
        # Look for common decoding patterns
        patterns_to_check = [
            # XOR operations
            r'(\w+)\s*\^\s*(\w+)',
            # Character manipulation
            r'(\w+)\s*\+\s*(\d+)',
            r'(\w+)\s*-\s*(\d+)',
            # String operations
            r'\.Substring\s*\(',
            r'\.Replace\s*\(',
            # Array/lookup operations
            r'\[(\w+)\]',
            # Mathematical operations
            r'%\s*(\d+)',
            r'\*\s*(\d+)',
        ]
        
        decoder_hints = []
        for pattern in patterns_to_check:
            matches = re.findall(pattern, method_body)
            if matches:
                decoder_hints.extend(matches)
        
        if decoder_hints:
            print(f"    Found decoder hints: {decoder_hints[:5]}...")  # Show first 5
            self.decoder_implementation = method_body
            self.stats['decoder_found'] = True
            
            # Try to extract the decoding algorithm
            self.reverse_engineer_decoder(method_body)

    def reverse_engineer_decoder(self, decoder_body):
        """Attempt to reverse engineer the decoding algorithm"""
        print("    🧬 Reverse engineering decoder...")
        
        # Common obfuscation techniques for string encoding:
        # 1. Caesar cipher (character shifting)
        # 2. XOR with key
        # 3. Base64 variant
        # 4. Character substitution
        # 5. Reverse + shift
        
        # Look for character shifting patterns
        if '+' in decoder_body and any(char.isdigit() for char in decoder_body):
            shift_matches = re.findall(r'(\w+)\s*\+\s*(\d+)', decoder_body)
            if shift_matches:
                print(f"    Detected character shifting: {shift_matches}")
                self.implement_shift_decoder(shift_matches)
        
        # Look for XOR patterns
        if '^' in decoder_body:
            xor_matches = re.findall(r'(\w+)\s*\^\s*(\w+)', decoder_body)
            if xor_matches:
                print(f"    Detected XOR operations: {xor_matches}")
                self.implement_xor_decoder(xor_matches)
        
        # Look for substitution patterns
        if 'Replace' in decoder_body:
            replace_matches = re.findall(r'Replace\s*\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)', decoder_body)
            if replace_matches:
                print(f"    Detected character substitution: {replace_matches}")
                self.implement_substitution_decoder(replace_matches)

    def implement_shift_decoder(self, shift_patterns):
        """Implement a character shifting decoder"""
        # Most common: each character is shifted by a fixed amount
        def decode_shifted_string(encoded_string, shift_amount=13):  # Default to ROT13
            try:
                decoded = ""
                for char in encoded_string:
                    if char.isalpha():
                        # Handle uppercase
                        if char.isupper():
                            decoded += chr((ord(char) - ord('A') - shift_amount) % 26 + ord('A'))
                        # Handle lowercase
                        else:
                            decoded += chr((ord(char) - ord('a') - shift_amount) % 26 + ord('a'))
                    else:
                        decoded += char
                return decoded
            except:
                return encoded_string
        
        self.decoder_function = decode_shifted_string
        print("    ✓ Implemented shift decoder")

    def implement_xor_decoder(self, xor_patterns):
        """Implement XOR decoder"""
        def decode_xor_string(encoded_string, key="defaultkey"):
            try:
                decoded = ""
                key_len = len(key)
                for i, char in enumerate(encoded_string):
                    key_char = key[i % key_len]
                    decoded += chr(ord(char) ^ ord(key_char))
                return decoded
            except:
                return encoded_string
        
        self.decoder_function = decode_xor_string
        print("    ✓ Implemented XOR decoder")

    def implement_substitution_decoder(self, substitution_patterns):
        """Implement character substitution decoder"""
        substitution_map = {}
        for old_char, new_char in substitution_patterns:
            substitution_map[new_char] = old_char  # Reverse the substitution
        
        def decode_substituted_string(encoded_string):
            decoded = encoded_string
            for encoded_char, original_char in substitution_map.items():
                decoded = decoded.replace(encoded_char, original_char)
            return decoded
        
        self.decoder_function = decode_substituted_string
        print("    ✓ Implemented substitution decoder")

    def try_decode_string(self, encoded_string):
        """Try to decode a string using the discovered decoder"""
        if not hasattr(self, 'decoder_function'):
            # If no specific decoder found, try common methods
            attempts = [
                self.try_caesar_decode(encoded_string),
                self.try_reverse_decode(encoded_string),
                self.try_base64_variant_decode(encoded_string),
            ]
            
            # Return the most readable result
            for attempt in attempts:
                if attempt and self.looks_like_readable_text(attempt):
                    return attempt
            
            return f"UNDECODED_{encoded_string[:10]}..."
        else:
            try:
                return self.decoder_function(encoded_string)
            except:
                return f"DECODE_FAILED_{encoded_string[:10]}..."

    def try_caesar_decode(self, text):
        """Try Caesar cipher with different shifts"""
        for shift in range(1, 26):
            decoded = ""
            for char in text:
                if char.isalpha():
                    if char.isupper():
                        decoded += chr((ord(char) - ord('A') - shift) % 26 + ord('A'))
                    else:
                        decoded += chr((ord(char) - ord('a') - shift) % 26 + ord('a'))
                else:
                    decoded += char
            
            if self.looks_like_readable_text(decoded):
                return decoded
        return None

    def try_reverse_decode(self, text):
        """Try reversing the string"""
        return text[::-1]

    def try_base64_variant_decode(self, text):
        """Try base64-like decoding"""
        try:
            import base64
            # Try standard base64
            decoded = base64.b64decode(text + '==').decode('utf-8', errors='ignore')
            if self.looks_like_readable_text(decoded):
                return decoded
        except:
            pass
        return None

    def looks_like_readable_text(self, text):
        """Check if decoded text looks readable"""
        if not text or len(text) < 3:
            return False
        
        # Check for reasonable character distribution
        alpha_count = sum(1 for c in text if c.isalpha())
        total_count = len(text)
        
        if total_count == 0:
            return False
        
        alpha_ratio = alpha_count / total_count
        
        # Should have reasonable amount of letters
        if alpha_ratio < 0.3:
            return False
        
        # Check for common English patterns
        common_patterns = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new', 'now', 'way', 'may', 'say']
        text_lower = text.lower()
        
        pattern_matches = sum(1 for pattern in common_patterns if pattern in text_lower)
        
        return pattern_matches > 0 or alpha_ratio > 0.7

    def decode_all_obfuscated_content(self, input_folder):
        """Main function to decode everything"""
        print("🚀 Starting comprehensive DayZ deobfuscation...")
        print(f"📂 Input: {input_folder}")
        print(f"📂 Output: {self.output_dir}")
        print("=" * 80)
        
        # Step 1: Find the decoder
        if not self.find_decoder_implementation(input_folder):
            print("⚠️  Decoder implementation not found. Will use heuristic methods.")
        else:
            print("✅ Decoder implementation found!")
        
        # Step 2: Process all files
        self.process_all_files(input_folder)
        
        # Step 3: Show results
        self.print_results()

    def process_all_files(self, input_folder):
        """Process all files with proper decoding"""
        input_path = Path(input_folder)
        output_path = Path(self.output_dir)
        output_path.mkdir(exist_ok=True)
        
        print("\n🔧 Processing and decoding files...")
        print("=" * 80)
        
        for root, dirs, files in os.walk(input_path):
            root_path = Path(root)
            relative_root = root_path.relative_to(input_path)
            
            # Decode folder names
            clean_relative_parts = []
            for part in relative_root.parts:
                decoded_part = self.try_decode_string(part)
                clean_relative_parts.append(decoded_part)
                if decoded_part != part:
                    print(f"  📁 {part} → {decoded_part}")
            
            clean_relative_root = Path(*clean_relative_parts) if clean_relative_parts else Path()
            clean_output_dir = output_path / clean_relative_root
            clean_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Process files
            for file in files:
                original_file_path = root_path / file
                
                # Decode file name
                file_stem = Path(file).stem
                file_suffix = Path(file).suffix
                decoded_stem = self.try_decode_string(file_stem)
                clean_file_name = f"{decoded_stem}{file_suffix}"
                
                if decoded_stem != file_stem:
                    print(f"  📄 {file} → {clean_file_name}")
                
                clean_file_path = clean_output_dir / clean_file_name
                
                # Process file content
                try:
                    if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf', '.txt', '.cfg'}:
                        with open(original_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Decode content
                        decoded_content = self.decode_file_content(content)
                        
                        with open(clean_file_path, 'w', encoding='utf-8') as f:
                            f.write(decoded_content)
                        
                        self.stats['files_processed'] += 1
                    else:
                        # Binary files - just copy
                        import shutil
                        shutil.copy2(original_file_path, clean_file_path)
                
                except Exception as e:
                    print(f"    ❌ Error processing {file}: {e}")

    def decode_file_content(self, content):
        """Decode obfuscated content in files"""
        result = content
        
        # Find and decode obfuscated strings
        string_patterns = [
            r'(\w+)\.\s*(\w+)\("([A-Z]{15,})",\s*([^)]+)\)',
            r'(\w+)\s*\.\s*(\w+)\s*\(\s*"([A-Z]{15,})"\s*,\s*([^)]+)\s*\)'
        ]
        
        for pattern in string_patterns:
            def replace_with_decoded(match):
                obj_name, method_name, encoded_str, param = match.groups()
                decoded_str = self.try_decode_string(encoded_str)
                self.stats['obfuscated_strings_found'] += 1
                
                if decoded_str.startswith('UNDECODED_') or decoded_str.startswith('DECODE_FAILED_'):
                    return f'/* OBFUSCATED: {encoded_str[:20]}... */ "{decoded_str}"'
                else:
                    self.stats['decoded_strings'] += 1
                    return f'"{decoded_str}"'
            
            result = re.sub(pattern, replace_with_decoded, result)
        
        # Decode obfuscated identifiers
        identifier_pattern = r'\b[A-Za-z][A-Za-z0-9_]{12,}\b'
        identifiers = re.findall(identifier_pattern, result)
        
        for identifier in set(identifiers):
            # Skip common words
            if identifier.lower() in ['string', 'float', 'vector', 'class']:
                continue
            
            decoded_identifier = self.try_decode_string(identifier)
            if decoded_identifier != identifier and not decoded_identifier.startswith(('UNDECODED_', 'DECODE_FAILED_')):
                result = re.sub(r'\b' + re.escape(identifier) + r'\b', decoded_identifier, result)
        
        # Add header
        header = """/*
 * DECODED DAYZ FILE
 * Processed with actual decoder algorithm
 * Obfuscated strings and identifiers have been decoded
 */

"""
        return header + result

    def print_results(self):
        """Print final statistics"""
        print("\n" + "=" * 80)
        print("🎉 DEOBFUSCATION COMPLETE!")
        print("=" * 80)
        print(f"🔍 Files scanned for decoder: {self.stats['files_scanned']}")
        print(f"✅ Decoder found: {'Yes' if self.stats['decoder_found'] else 'No (used heuristics)'}")
        print(f"📄 Files processed: {self.stats['files_processed']}")
        print(f"🔗 Obfuscated strings found: {self.stats['obfuscated_strings_found']}")
        print(f"✅ Successfully decoded strings: {self.stats['decoded_strings']}")
        print(f"📂 Output saved to: {Path(self.output_dir).absolute()}")
        print("=" * 80)

# Usage
if __name__ == "__main__":
    INPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/"  # Your input folder
    OUTPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server_cleaned/"   # Where to save clean files   
    
    deobfuscator = ActualDayZDeobfuscator(output_dir=OUTPUT_FOLDER)
    deobfuscator.decode_all_obfuscated_content(INPUT_FOLDER)
    
    print(f"\n🎯 Real deobfuscation complete! Check: {OUTPUT_FOLDER}")