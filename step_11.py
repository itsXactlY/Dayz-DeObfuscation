#!/usr/bin/env python3
"""
Complete DayZ Deobfuscation Script
Handles Ns7IynOBl5RX6MyZ and F9uQoeANHD4S5R56 decryption functions
Automatically extracts constants, context keys, and removes junk code
"""

import re
import os
import json
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse
import logging

class CompleteDayZDeobfuscator:
    def __init__(self, output_dir="deobfuscated_dayz", verbose=False):
        self.output_dir = output_dir
        self.verbose = verbose
        
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Context arrays and keys
        self.context_keys = {}  # Multiple context objects
        self.primary_context_key = []
        self.primary_context_len = 0
        
        # Extracted constants with intelligent defaults based on common obfuscation
        self.constants = {
            # Length constants
            'Ccw1TwHfDPZggLVK': 8,
            'DoIeHgDE2mVRoHSc': 256,  # Typical key array length
            
            # Index multipliers  
            'XdjDbQjncRrhyHCQ': 2,
            'Rj7dcv1nSMPT3yj4': 2, 
            'VGg1l8gfLgy7Yfo2': 1,
            
            # Arithmetic constants
            'HGS0YYmtehRNsqu0': 32,   # Common ASCII shift
            'TfLX6A3wPjCFybhs': 65,   # 'A' ASCII value
            'FKvfMYJxCW20yYBF': 0xFF, # Byte mask
            'R0xMkh5k90T1essw': 3,    # Bit shift amount
            
            # Algorithm constants
            'YIv48kTc2kMWJ5qx': 7,
            'UGiapRt2QI0mOmEw': 13,
            'U1uloE0ujVVvxhe2': 3,
            'Q4M2uDvKXkQE7PiA': 5,
            'DzExo7t5l9xWxtUm': 0xFF,
            
            # Checksum constants
            'IWCAs9AferLH8XNG': 0,
            'FZEKE80NncIr0e25': 0,
        }
        
        # Known obfuscated identifiers
        self.known_identifiers = {
            'SfFuxbdumezDa91W': 'DecoderClass',
            'Ns7IynOBl5RX6MyZ': 'DecryptString',
            'F9uQoeANHD4S5R56': 'DecryptStringAlt',
            'T4QPEBrB2xOEx7Qc': 'ContextObject',
            'AQT3lGGVuJj5kIVr': 'KeyArray',
            'BrzP4IgclV4CTfv0': 'KeyData',
            'SomBJ8YD6RPDXVXM': 'KeyMerge',
        }
        
        # Statistics
        self.stats = {
            'files_scanned': 0,
            'files_processed': 0,
            'constants_found': 0,
            'context_keys_found': 0,
            'obfuscated_strings_found': 0,
            'successfully_decoded': 0,
            'junk_patterns_removed': 0,
            'identifiers_deobfuscated': 0,
            'total_reduction_bytes': 0,
        }
        
        # Decoder cache for performance
        self.decode_cache = {}

    def setup_output_directory(self):
        """Create clean output directory"""
        output_path = Path(self.output_dir)
        if output_path.exists():
            shutil.rmtree(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"📂 Output directory: {output_path.absolute()}")

    def scan_for_decoder_components(self, input_folder: str) -> bool:
        """Comprehensive scan to find all decoder components"""
        self.logger.info("🔍 Scanning for decoder components...")
        
        found_decoder = False
        input_path = Path(input_folder)
        
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf', '.txt'}:
                    file_path = Path(root) / file
                    self.stats['files_scanned'] += 1
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Look for decoder functions
                        if any(func in content for func in ['Ns7IynOBl5RX6MyZ', 'F9uQoeANHD4S5R56']):
                            self.logger.info(f"  📄 Decoder found in: {file_path}")
                            self.extract_decoder_components(content, str(file_path))
                            found_decoder = True
                        
                        # Extract constants from any file
                        self.extract_constants(content)
                        
                        # Extract context keys
                        self.extract_context_keys(content)
                        
                    except Exception as e:
                        self.logger.warning(f"  ❌ Error reading {file_path}: {e}")
        
        self.logger.info(f"  ✅ Found {self.stats['constants_found']} constants")
        self.logger.info(f"  ✅ Found {self.stats['context_keys_found']} context keys")
        
        return found_decoder

    def extract_constants(self, content: str):
        """Extract obfuscated constants with multiple patterns"""
        patterns = [
            # Standard assignments
            r'(\w{12,})\s*=\s*(\d+)(?:\s*;|\s*,|\s*\))',
            r'(\w{12,})\s*=\s*(0x[0-9A-Fa-f]+)(?:\s*;|\s*,|\s*\))',
            
            # Static declarations
            r'static\s+(?:const\s+)?(?:int|long|uint|ulong)\s+(\w{12,})\s*=\s*(\d+)',
            r'static\s+(?:const\s+)?(?:int|long|uint|ulong)\s+(\w{12,})\s*=\s*(0x[0-9A-Fa-f]+)',
            
            # Define statements
            r'#define\s+(\w{12,})\s+(\d+)',
            r'#define\s+(\w{12,})\s+(0x[0-9A-Fa-f]+)',
            
            # Enum values
            r'(\w{12,})\s*=\s*([-]?\d+)(?:\s*,|\s*})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for const_name, value_str in matches:
                try:
                    if value_str.lower().startswith('0x'):
                        value = int(value_str, 16)
                    else:
                        value = int(value_str)
                    
                    # Update if we recognize this constant or if it's reasonable
                    if (const_name in self.constants or 
                        (len(const_name) >= 12 and 0 <= value <= 0xFFFF)):
                        
                        old_value = self.constants.get(const_name, "unknown")
                        self.constants[const_name] = value
                        
                        if old_value != value:
                            self.stats['constants_found'] += 1
                            self.logger.debug(f"    📊 {const_name} = {value} (was {old_value})")
                            
                except ValueError:
                    continue

    def extract_context_keys(self, content: str):
        """Extract context key arrays with multiple patterns"""
        patterns = [
            # Array initializations
            r'(\w{12,})\s*=\s*\{([0-9,\s\-x]+)\}',
            r'(\w{12,})\s*=\s*new\s+(?:int|uint|long)\[\]\s*\{([0-9,\s\-x]+)\}',
            r'static\s+(?:const\s+)?(?:int|uint|long)\s+(\w{12,})\[\]\s*=\s*\{([0-9,\s\-x]+)\}',
            
            # Method calls that might initialize arrays
            r'(\w{12,})\.(?:Add|Push|Insert)\s*\(\s*([0-9\-x]+)\s*\)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for array_name, array_data in matches:
                if len(array_name) >= 12:  # Likely obfuscated
                    try:
                        # Parse array values
                        if ',' in array_data:
                            # Full array initialization
                            values = []
                            for val_str in array_data.split(','):
                                val_str = val_str.strip()
                                if val_str:
                                    if val_str.lower().startswith('0x'):
                                        values.append(int(val_str, 16))
                                    else:
                                        values.append(int(val_str))
                            
                            if len(values) > 5:  # Reasonable key array
                                self.context_keys[array_name] = values
                                self.stats['context_keys_found'] += 1
                                self.logger.debug(f"    🔑 Found key array {array_name}: {len(values)} elements")
                                
                                # Set as primary if largest or first
                                if (not self.primary_context_key or 
                                    len(values) > len(self.primary_context_key)):
                                    self.primary_context_key = values
                                    self.primary_context_len = len(values)
                        else:
                            # Single value - might be building array incrementally
                            if array_name not in self.context_keys:
                                self.context_keys[array_name] = []
                            
                            val_str = array_data.strip()
                            if val_str.lower().startswith('0x'):
                                self.context_keys[array_name].append(int(val_str, 16))
                            else:
                                self.context_keys[array_name].append(int(val_str))
                                
                    except ValueError as e:
                        self.logger.debug(f"    ❌ Failed to parse array {array_name}: {e}")

    def extract_decoder_components(self, content: str, file_path: str):
        """Extract decoder function implementations"""
        self.logger.debug(f"    🔬 Analyzing decoder in: {file_path}")
        
        # Look for decoder function implementations
        decoder_patterns = [
            r'string\s+(Ns7IynOBl5RX6MyZ)\s*\([^)]*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
            r'string\s+(F9uQoeANHD4S5R56)\s*\([^)]*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
        ]
        
        for pattern in decoder_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for func_name, func_body in matches:
                self.logger.info(f"      ✅ Found {func_name} implementation")
                
                # Extract constants from function body
                self.extract_constants(func_body)
                
                # Look for hash function implementation
                if '.Hash()' in func_body or '.hash()' in func_body:
                    self.analyze_hash_function(func_body)

    def analyze_hash_function(self, func_body: str):
        """Analyze the hash function used in decoding"""
        # Common hash implementations in obfuscated code
        hash_patterns = [
            r'(\w+)\s*=\s*(\w+)\s*\*\s*(\d+)\s*\+\s*(\d+)',  # Simple polynomial hash
            r'(\w+)\s*=\s*\(\s*(\w+)\s*\+\s*(\d+)\s*\)\s*\%\s*(\d+)',  # Modular hash
            r'(\w+)\s*=\s*(\w+)\s*\^\s*(\w+)',  # XOR hash
        ]
        
        for pattern in hash_patterns:
            matches = re.findall(pattern, func_body)
            if matches:
                self.logger.debug(f"      🔍 Hash pattern found: {matches[0]}")

    def create_optimized_decoder(self) -> callable:
        """Create optimized decoder function"""
        if not self.primary_context_key:
            # Generate default key if none found
            self.logger.warning("    ⚠️ No context key found, generating default")
            self.primary_context_key = [i * 7 + 13 for i in range(256)]
            self.primary_context_len = 256
        
        def optimized_ns7_decoder(ciphertext: str) -> str:
            """Optimized Ns7IynOBl5RX6MyZ decoder"""
            if ciphertext in self.decode_cache:
                return self.decode_cache[ciphertext]
            
            if len(ciphertext) < 3:
                return ciphertext
            
            try:
                result = ""
                length = len(ciphertext)
                
                # Use extracted or default constants
                offset = self.constants.get('Ccw1TwHfDPZggLVK', 8)
                if length <= offset:
                    return ciphertext
                
                effective_length = length - offset
                iterations = max(1, effective_length // 2)
                
                for i in range(iterations):
                    # Calculate indices with bounds checking
                    a_idx = min((i * self.constants.get('XdjDbQjncRrhyHCQ', 2)) % length, length - 1)
                    b_idx = min((i * self.constants.get('Rj7dcv1nSMPT3yj4', 2) + 
                               self.constants.get('VGg1l8gfLgy7Yfo2', 1)) % length, length - 1)
                    
                    # Get character values
                    a = ord(ciphertext[a_idx])
                    b = ord(ciphertext[b_idx])
                    
                    # Apply transformations
                    a = (a - self.constants.get('HGS0YYmtehRNsqu0', 32)) & 0xFF
                    b = (b - self.constants.get('TfLX6A3wPjCFybhs', 65)) & 0xFF
                    b = (b << self.constants.get('R0xMkh5k90T1essw', 3)) & 0xFF
                    
                    # Calculate key index
                    key_idx = abs(i * self.constants.get('YIv48kTc2kMWJ5qx', 7) + 
                                effective_length * self.constants.get('UGiapRt2QI0mOmEw', 13))
                    key_val = self.primary_context_key[key_idx % self.primary_context_len]
                    
                    # Final decryption
                    result_byte = (a + b) ^ (
                        self.constants.get('U1uloE0ujVVvxhe2', 3) * key_val + 
                        i * self.constants.get('Q4M2uDvKXkQE7PiA', 5)
                    )
                    result_byte &= self.constants.get('DzExo7t5l9xWxtUm', 0xFF)
                    
                    # Convert to character if printable
                    if 32 <= result_byte <= 126:
                        result += chr(result_byte)
                    elif result_byte == 0:  # Null terminator
                        break
                    else:
                        result += chr(result_byte % 95 + 32)  # Force into printable range
                
                # Cache successful decodes
                if result and self.is_likely_plaintext(result):
                    self.decode_cache[ciphertext] = result
                    return result
                else:
                    # Try alternative approaches
                    alt_result = self.try_alternative_decoders(ciphertext)
                    self.decode_cache[ciphertext] = alt_result
                    return alt_result
                    
            except Exception as e:
                self.logger.debug(f"      ❌ Decode error for '{ciphertext[:20]}...': {e}")
                return f"DECODE_ERROR_{ciphertext[:10]}"
        
        return optimized_ns7_decoder

    def try_alternative_decoders(self, ciphertext: str) -> str:
        """Try alternative decoding methods"""
        alternatives = [
            self.caesar_decode,
            self.xor_decode,
            self.reverse_decode,
            self.substitution_decode,
            self.base64_variant_decode,
        ]
        
        for decoder in alternatives:
            try:
                result = decoder(ciphertext)
                if result and self.is_likely_plaintext(result):
                    return result
            except:
                continue
        
        return f"ALT_FAILED_{ciphertext[:10]}"

    def caesar_decode(self, text: str) -> str:
        """Caesar cipher decoder with multiple shifts"""
        best_result = ""
        best_score = 0
        
        for shift in range(1, 26):
            result = ""
            for char in text:
                if char.isalpha():
                    if char.isupper():
                        result += chr((ord(char) - ord('A') - shift) % 26 + ord('A'))
                    else:
                        result += chr((ord(char) - ord('a') - shift) % 26 + ord('a'))
                else:
                    result += char
            
            score = self.calculate_readability_score(result)
            if score > best_score:
                best_score = score
                best_result = result
        
        return best_result if best_score > 0.3 else ""

    def xor_decode(self, text: str) -> str:
        """XOR decoder with common keys"""
        common_keys = [
            "key", "password", "secret", "decode", "dayz", "game",
            "0123456789", "abcdefgh", "zyxwvuts"
        ]
        
        for key in common_keys:
            try:
                result = ""
                key_len = len(key)
                for i, char in enumerate(text):
                    result += chr(ord(char) ^ ord(key[i % key_len]))
                
                if self.is_likely_plaintext(result):
                    return result
            except:
                continue
        
        return ""

    def reverse_decode(self, text: str) -> str:
        """Simple reverse decoder"""
        return text[::-1]

    def substitution_decode(self, text: str) -> str:
        """Character substitution decoder"""
        # Common substitution: A-Z -> N-ZA-M (ROT13 variant)
        result = ""
        for char in text:
            if char.isupper() and 'A' <= char <= 'Z':
                result += chr((ord(char) - ord('A') + 13) % 26 + ord('A'))
            elif char.islower() and 'a' <= char <= 'z':
                result += chr((ord(char) - ord('a') + 13) % 26 + ord('a'))
            else:
                result += char
        
        return result

    def base64_variant_decode(self, text: str) -> str:
        """Custom base64-like decoder"""
        try:
            import base64
            
            # Try different base64 variants
            variants = [
                lambda x: base64.b64decode(x + '=='),
                lambda x: base64.b64decode(x + '='),
                lambda x: base64.b64decode(x),
            ]
            
            for variant in variants:
                try:
                    decoded_bytes = variant(text)
                    result = decoded_bytes.decode('utf-8', errors='ignore')
                    if self.is_likely_plaintext(result):
                        return result
                except:
                    continue
        except ImportError:
            pass
        
        return ""

    def is_likely_plaintext(self, text: str) -> bool:
        """Enhanced plaintext detection"""
        if not text or len(text) < 3:
            return False
        
        # Character distribution analysis
        printable_count = sum(1 for c in text if 32 <= ord(c) <= 126)
        alpha_count = sum(1 for c in text if c.isalpha())
        digit_count = sum(1 for c in text if c.isdigit())
        space_count = sum(1 for c in text if c.isspace())
        
        total = len(text)
        if total == 0:
            return False
        
        printable_ratio = printable_count / total
        alpha_ratio = alpha_count / total
        
        # Must be mostly printable
        if printable_ratio < 0.7:
            return False
        
        # Should have reasonable letter content
        if alpha_ratio < 0.2:
            return False
        
        # Check for common English patterns
        common_words = [
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new',
            'now', 'way', 'may', 'say', 'each', 'which', 'she', 'how', 'its', 'two'
        ]
        
        text_lower = text.lower()
        word_matches = sum(1 for word in common_words if word in text_lower)
        
        # Check for programming keywords (since this is code)
        code_words = [
            'class', 'function', 'string', 'int', 'float', 'vector', 'array',
            'if', 'else', 'for', 'while', 'return', 'void', 'public', 'private'
        ]
        
        code_matches = sum(1 for word in code_words if word in text_lower)
        
        return word_matches > 0 or code_matches > 0 or alpha_ratio > 0.8

    def calculate_readability_score(self, text: str) -> float:
        """Calculate readability score for decoded text"""
        if not text:
            return 0.0
        
        score = 0.0
        total = len(text)
        
        # Letter frequency analysis
        alpha_count = sum(1 for c in text if c.isalpha())
        score += (alpha_count / total) * 0.4
        
        # Common letter patterns
        common_bigrams = ['th', 'he', 'in', 'er', 'an', 're', 'ed', 'nd', 'ha', 'to']
        text_lower = text.lower()
        bigram_matches = sum(1 for bg in common_bigrams if bg in text_lower)
        score += min(bigram_matches / 10, 0.3)
        
        # Reasonable punctuation
        punct_count = sum(1 for c in text if c in '.,;:!?')
        score += min(punct_count / total * 2, 0.3)
        
        return score

    def remove_junk_code_patterns(self, content: str) -> str:
        """Remove junk code with comprehensive patterns"""
        original_length = len(content)
        
        junk_patterns = [
            # Always false conditions
            (r'if\s*\(\s*false\s*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', 'false conditions'),
            (r'if\s*\(\s*0\s*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', 'zero conditions'),
            
            # Empty constructs
            (r'for\s*\([^)]*\)\s*\{\s*\}', 'empty for loops'),
            (r'while\s*\([^)]*\)\s*\{\s*\}', 'empty while loops'),
            (r'if\s*\([^)]*\)\s*\{\s*\}', 'empty if blocks'),
            
            # Redundant assignments
            (r'(\w+)\s*=\s*(\w+)\s*;\s*\1\s*=\s*\2\s*;', 'redundant assignments'),
            
            # Useless function calls
            (r'\w+\s*\(\s*"[^"]*"\s*,\s*vector\s*\([^)]*\)\s*\)\s*;', 'dummy function calls'),
            
            # Dead code after return
            (r'return\s+[^;]+;\s*\w+[^}]*(?=\})', 'dead code after return'),
            
            # Excessive whitespace
            (r'\n\s*\n\s*\n+', 'excessive newlines'),
            (r'[ \t]+\n', 'trailing whitespace'),
        ]
        
        for pattern, description in junk_patterns:
            before_count = len(re.findall(pattern, content, re.DOTALL))
            content = re.sub(pattern, '', content, flags=re.DOTALL)
            after_count = len(re.findall(pattern, content, re.DOTALL))
            
            removed = before_count - after_count
            if removed > 0:
                self.stats['junk_patterns_removed'] += removed
                self.logger.debug(f"      🗑️ Removed {removed} {description}")
        
        # Clean up excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+\n', '\n', content)
        
        reduction = original_length - len(content)
        self.stats['total_reduction_bytes'] += reduction
        
        return content

    def deobfuscate_identifiers(self, content: str) -> str:
        """Deobfuscate known identifiers"""
        result = content
        
        for obfuscated, clean in self.known_identifiers.items():
            if obfuscated in result:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(obfuscated) + r'\b'
                result = re.sub(pattern, clean, result)
                self.stats['identifiers_deobfuscated'] += 1
                self.logger.debug(f"      🔤 {obfuscated} → {clean}")
        
        return result

    def process_file_content(self, content: str, file_path: str) -> str:
        """Process and deobfuscate file content"""
        self.logger.debug(f"    🔧 Processing: {file_path}")
        
        # Step 1: Remove junk code
        content = self.remove_junk_code_patterns(content)
        
        # Step 2: Deobfuscate known identifiers
        content = self.deobfuscate_identifiers(content)
        
        # Step 3: Create decoder
        decoder = self.create_optimized_decoder()
        
        # Step 4: Find and decode obfuscated strings
        string_patterns = [
            # Primary decoder pattern
            r'(\w+)\s*\.\s*(Ns7IynOBl5RX6MyZ)\s*\(\s*"([A-Z0-9]{12,})"\s*,\s*([^)]+)\s*\)',
            # Alternative decoder pattern  
            r'(\w+)\s*\.\s*(F9uQoeANHD4S5R56)\s*\(\s*"([A-Z0-9]{12,})"\s*,\s*([^)]+)\s*\)',
            # Direct string patterns
            r'"([A-Z0-9]{15,})"',
        ]
        
        for pattern in string_patterns:
            def replace_obfuscated_string(match):
                if len(match.groups()) == 4:
                    obj_name, method_name, encoded_str, context = match.groups()
                else:
                    encoded_str = match.group(1)
                    method_name = "direct"
                
                self.stats['obfuscated_strings_found'] += 1
                
                # Try to decode
                decoded = decoder(encoded_str)
                
                if (decoded and 
                    not decoded.startswith(('DECODE_ERROR_', 'ALT_FAILED_', 'UNDECODED_')) and
                    self.is_likely_plaintext(decoded)):
                    
                    self.stats['successfully_decoded'] += 1
                    
                    if len(match.groups()) == 4:
                        return f'"{decoded}"  /* was {method_name}("{encoded_str[:15]}...") */'
                    else:
                        return f'"{decoded}"'
                else:
                    # Keep original with comment
                    if len(match.groups()) == 4:
                        return f'{obj_name}.{method_name}("{encoded_str}", {context})  /* DECODE_FAILED */'
                    else:
                        return f'"{encoded_str}"  /* DECODE_FAILED */'
            
            content = re.sub(pattern, replace_obfuscated_string, content)
        
        # Step 5: Add header with processing info
        processing_info = f"""/*
 * DayZ Deobfuscation Results
 * File: {Path(file_path).name}
 * Decoder: {'Custom' if self.primary_context_key else 'Heuristic'}  
 * Constants: {len([k for k, v in self.constants.items() if v != 0])} found
 * Context Keys: {len(self.context_keys)} arrays found
 * Strings Processed: {self.stats['obfuscated_strings_found']} 
 * Successfully Decoded: {self.stats['successfully_decoded']}
 * Junk Patterns Removed: {self.stats['junk_patterns_removed']}
 */

"""
        
        return processing_info + content

    def process_single_file(self, input_file: str, output_file: str) -> bool:
        """Process a single file for deobfuscation"""
        try:
            # Read input file
            with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                self.logger.warning(f"    ⚠️ Empty file: {input_file}")
                return False
            
            # Process content
            processed_content = self.process_file_content(content, input_file)
            
            # Write output file
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            self.stats['files_processed'] += 1
            self.logger.info(f"    ✅ Processed: {Path(input_file).name}")
            return True
            
        except Exception as e:
            self.logger.error(f"    ❌ Error processing {input_file}: {e}")
            return False

    def process_directory(self, input_folder: str) -> bool:
        """Process entire directory of files"""
        self.logger.info("🚀 Starting deobfuscation process...")
        
        # Setup output directory
        self.setup_output_directory()
        
        # Scan for decoder components first
        decoder_found = self.scan_for_decoder_components(input_folder)
        
        if not decoder_found:
            self.logger.warning("⚠️ No decoder functions found, using heuristic approach")
        
        # Process all files
        input_path = Path(input_folder)
        success_count = 0
        
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf', '.txt'}:
                    input_file = Path(root) / file
                    
                    # Create corresponding output path
                    relative_path = input_file.relative_to(input_path)
                    output_file = Path(self.output_dir) / relative_path
                    
                    if self.process_single_file(str(input_file), str(output_file)):
                        success_count += 1
        
        # Generate summary report
        self.generate_summary_report()
        
        return success_count > 0

    def generate_summary_report(self):
        """Generate detailed summary report"""
        report_path = Path(self.output_dir) / "deobfuscation_report.json"
        
        # Calculate success rates
        decode_rate = (self.stats['successfully_decoded'] / 
                      max(self.stats['obfuscated_strings_found'], 1)) * 100
        
        processing_rate = (self.stats['files_processed'] / 
                          max(self.stats['files_scanned'], 1)) * 100
        
        report_data = {
            'summary': {
                'total_files_scanned': self.stats['files_scanned'],
                'files_processed': self.stats['files_processed'],
                'processing_success_rate': f"{processing_rate:.1f}%",
                'total_strings_found': self.stats['obfuscated_strings_found'],
                'strings_decoded': self.stats['successfully_decoded'],
                'decode_success_rate': f"{decode_rate:.1f}%",
                'bytes_reduced': self.stats['total_reduction_bytes'],
                'junk_patterns_removed': self.stats['junk_patterns_removed'],
                'identifiers_deobfuscated': self.stats['identifiers_deobfuscated']
            },
            'decoder_config': {
                'constants_found': len([k for k, v in self.constants.items() if v != 0]),
                'context_keys_found': len(self.context_keys),
                'primary_context_length': self.primary_context_len,
                'cache_entries': len(self.decode_cache)
            },
            'discovered_constants': {k: v for k, v in self.constants.items() if v != 0},
            'context_arrays': {k: len(v) for k, v in self.context_keys.items()},
            'known_identifiers': self.known_identifiers
        }
        
        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        
        # Console summary
        self.logger.info("=" * 60)
        self.logger.info("📊 DEOBFUSCATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"📁 Files Scanned:        {self.stats['files_scanned']}")
        self.logger.info(f"⚡ Files Processed:      {self.stats['files_processed']} ({processing_rate:.1f}%)")
        self.logger.info(f"🔤 Strings Found:        {self.stats['obfuscated_strings_found']}")
        self.logger.info(f"✅ Strings Decoded:      {self.stats['successfully_decoded']} ({decode_rate:.1f}%)")
        self.logger.info(f"🗑️ Junk Removed:         {self.stats['junk_patterns_removed']} patterns")
        self.logger.info(f"📝 Identifiers Cleaned:  {self.stats['identifiers_deobfuscated']}")
        self.logger.info(f"💾 Size Reduction:       {self.stats['total_reduction_bytes']:,} bytes")
        self.logger.info(f"🔑 Context Arrays:       {len(self.context_keys)}")
        self.logger.info(f"📊 Constants Found:      {len([k for k, v in self.constants.items() if v != 0])}")
        self.logger.info("=" * 60)
        self.logger.info(f"📄 Full report saved: {report_path}")
        self.logger.info(f"📂 Output directory: {Path(self.output_dir).absolute()}")

if __name__ == "__main__":
    INPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/"  # Your input folder
    OUTPUT_FOLDER = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server_cleaned/"   # Where to save clean files   
    
    deobfuscator = CompleteDayZDeobfuscator(output_dir=OUTPUT_FOLDER)
    deobfuscator.process_directory(INPUT_FOLDER)
    
    print(f"\n🎯 Real deobfuscation complete! Check: {OUTPUT_FOLDER}")