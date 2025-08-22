#!/usr/bin/env python3
"""
Enhanced DayZ Deobfuscation Script
Improved pattern detection and flexible string matching
"""

import re
import os
import json
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
import argparse
import logging
from collections import Counter

class EnhancedDayZDeobfuscator:
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
        self.context_keys = {}
        self.primary_context_key = []
        self.primary_context_len = 0
        
        # Enhanced constants with broader detection
        self.constants = {
            # Common obfuscation constants
            'Ccw1TwHfDPZggLVK': 8, 'DoIeHgDE2mVRoHSc': 256, 'XdjDbQjncRrhyHCQ': 2,
            'Rj7dcv1nSMPT3yj4': 2, 'VGg1l8gfLgy7Yfo2': 1, 'HGS0YYmtehRNsqu0': 32,
            'TfLX6A3wPjCFybhs': 65, 'FKvfMYJxCW20yYBF': 0xFF, 'R0xMkh5k90T1essw': 3,
            'YIv48kTc2kMWJ5qx': 7, 'UGiapRt2QI0mOmEw': 13, 'U1uloE0ujVVvxhe2': 3,
            'Q4M2uDvKXkQE7PiA': 5, 'DzExo7t5l9xWxtUm': 0xFF, 'IWCAs9AferLH8XNG': 0,
            'FZEKE80NncIr0e25': 0,
        }
        
        # Enhanced identifier patterns
        self.known_identifiers = {
            'SfFuxbdumezDa91W': 'DecoderClass', 'Ns7IynOBl5RX6MyZ': 'DecryptString',
            'F9uQoeANHD4S5R56': 'DecryptStringAlt', 'T4QPEBrB2xOEx7Qc': 'ContextObject',
            'AQT3lGGVuJj5kIVr': 'KeyArray', 'BrzP4IgclV4CTfv0': 'KeyData',
            'SomBJ8YD6RPDXVXM': 'KeyMerge',
        }
        
        # Pattern analysis
        self.discovered_patterns = set()
        self.string_analysis = {'suspicious_strings': [], 'potential_encoded': []}
        
        # Statistics
        self.stats = {
            'files_scanned': 0, 'files_processed': 0, 'constants_found': 0,
            'context_keys_found': 0, 'obfuscated_strings_found': 0, 'successfully_decoded': 0,
            'junk_patterns_removed': 0, 'identifiers_deobfuscated': 0, 'total_reduction_bytes': 0,
            'patterns_discovered': 0, 'suspicious_strings_analyzed': 0
        }
        
        # Decoder cache
        self.decode_cache = {}

    def setup_output_directory(self):
        """Create clean output directory"""
        output_path = Path(self.output_dir)
        if output_path.exists():
            shutil.rmtree(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"📂 Output directory: {output_path.absolute()}")

    def analyze_file_patterns(self, content: str, file_path: str):
        """Analyze file to discover obfuscation patterns"""
        self.logger.debug(f"    🔍 Analyzing patterns in: {Path(file_path).name}")
        
        # Look for suspicious string patterns
        suspicious_patterns = [
            # Long random-looking strings
            r'"([A-Z0-9]{12,})"',
            r'"([a-zA-Z0-9]{16,})"',
            r'"([A-Za-z0-9+/]{20,}={0,2})"',  # Base64-like
            
            # Function calls with encoded strings
            r'(\w+)\s*\.\s*(\w+)\s*\(\s*"([^"]{10,})"\s*(?:,\s*[^)]+)?\s*\)',
            
            # Variable assignments with suspicious values
            r'(\w+)\s*=\s*"([A-Z0-9]{10,})"',
            
            # Array/vector initializations with encoded data
            r'\{\s*"([^"]{10,})"\s*(?:,\s*"([^"]{10,})"\s*)*\}',
        ]
        
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Extract the actual string from tuple
                    for item in match:
                        if len(item) >= 10:
                            self.analyze_string_characteristics(item, file_path)
                else:
                    self.analyze_string_characteristics(match, file_path)

    def analyze_string_characteristics(self, string_value: str, file_path: str):
        """Analyze string to determine if it's likely obfuscated"""
        if len(string_value) < 10:
            return
        
        # Characteristics analysis
        char_count = Counter(string_value)
        total_chars = len(string_value)
        
        # Calculate entropy and other metrics
        uppercase_ratio = sum(1 for c in string_value if c.isupper()) / total_chars
        digit_ratio = sum(1 for c in string_value if c.isdigit()) / total_chars
        alpha_ratio = sum(1 for c in string_value if c.isalpha()) / total_chars
        
        # Unique character ratio
        unique_ratio = len(char_count) / total_chars
        
        # Check for patterns that suggest encoding
        is_suspicious = (
            (uppercase_ratio > 0.5 and digit_ratio > 0.2) or  # Mixed case/digits
            (alpha_ratio > 0.8 and unique_ratio > 0.4) or     # High entropy
            (len(string_value) > 20 and uppercase_ratio > 0.8) or  # Long uppercase
            re.match(r'^[A-Za-z0-9+/]+=*$', string_value)  # Base64-like
        )
        
        if is_suspicious:
            self.string_analysis['suspicious_strings'].append({
                'string': string_value,
                'file': Path(file_path).name,
                'length': len(string_value),
                'uppercase_ratio': uppercase_ratio,
                'digit_ratio': digit_ratio,
                'unique_ratio': unique_ratio
            })
            self.stats['suspicious_strings_analyzed'] += 1
            
            # Try to determine encoding type
            self.classify_encoding_type(string_value)

    def classify_encoding_type(self, string_value: str):
        """Classify the type of encoding used"""
        encoding_indicators = {
            'base64': re.match(r'^[A-Za-z0-9+/]+=*$', string_value) and len(string_value) % 4 == 0,
            'hex': re.match(r'^[0-9A-Fa-f]+$', string_value) and len(string_value) % 2 == 0,
            'custom_cipher': len(string_value) > 15 and re.match(r'^[A-Z0-9]+$', string_value),
            'mixed_encoding': bool(re.search(r'[A-Z]', string_value) and re.search(r'[0-9]', string_value))
        }
        
        for encoding_type, is_match in encoding_indicators.items():
            if is_match:
                self.string_analysis['potential_encoded'].append({
                    'string': string_value,
                    'type': encoding_type,
                    'confidence': self.calculate_encoding_confidence(string_value, encoding_type)
                })
                break

    def calculate_encoding_confidence(self, string_value: str, encoding_type: str) -> float:
        """Calculate confidence level for encoding type"""
        confidence = 0.0
        
        if encoding_type == 'base64':
            # Check padding and character set
            if string_value.endswith('=') or string_value.endswith('=='):
                confidence += 0.3
            if re.match(r'^[A-Za-z0-9+/]+={0,2}$', string_value):
                confidence += 0.4
            if len(string_value) >= 20:
                confidence += 0.3
                
        elif encoding_type == 'custom_cipher':
            # Check for DayZ-specific patterns
            if len(string_value) >= 16 and re.match(r'^[A-Z0-9]+$', string_value):
                confidence += 0.5
            if any(pattern in string_value for pattern in ['LBMASTER', 'DAYZ', 'ARMA']):
                confidence += 0.3
            if len(string_value) in [16, 32, 64]:  # Common cipher lengths
                confidence += 0.2
        
        return min(confidence, 1.0)

    def enhanced_string_detection(self, content: str) -> List[Tuple[str, str, str]]:
        """Enhanced detection of obfuscated strings"""
        found_strings = []
        
        # Comprehensive patterns for different obfuscation styles
        detection_patterns = [
            # Method calls with encoded strings
            (r'(\w+)\s*\.\s*(Ns7IynOBl5RX6MyZ|F9uQoeANHD4S5R56)\s*\(\s*"([^"]+)"\s*(?:,\s*[^)]+)?\s*\)', 'method_call'),
            
            # Direct encoded string assignments
            (r'(\w+)\s*=\s*"([A-Z0-9]{12,})"', 'assignment'),
            
            # String literals that look encoded
            (r'"([A-Z0-9]{15,})"', 'literal'),
            (r'"([a-zA-Z0-9+/]{20,}={0,2})"', 'base64_like'),
            
            # Function parameters
            (r'\w+\s*\(\s*"([A-Z0-9]{12,})"\s*(?:,\s*[^)]+)?\s*\)', 'parameter'),
            
            # Array/vector initializations
            (r'\{\s*"([A-Z0-9]{10,})"\s*(?:,\s*"([A-Z0-9]{10,})"\s*)*\}', 'array_init'),
        ]
        
        for pattern, pattern_type in detection_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                
                # Extract the encoded string from different group positions
                encoded_string = None
                context = ""
                
                if pattern_type == 'method_call' and len(groups) >= 3:
                    context = f"{groups[0]}.{groups[1]}"
                    encoded_string = groups[2]
                elif pattern_type == 'assignment' and len(groups) >= 2:
                    context = f"var_{groups[0]}"
                    encoded_string = groups[1]
                elif pattern_type in ['literal', 'base64_like', 'parameter']:
                    encoded_string = groups[0]
                    context = pattern_type
                elif pattern_type == 'array_init':
                    # Handle multiple strings in array
                    for group in groups:
                        if group and len(group) >= 10:
                            found_strings.append((group, 'array_element', match.start()))
                    continue
                
                if encoded_string and len(encoded_string) >= 10:
                    found_strings.append((encoded_string, context, match.start()))
                    self.discovered_patterns.add(pattern_type)
        
        self.stats['patterns_discovered'] = len(self.discovered_patterns)
        return found_strings

    def create_adaptive_decoder(self) -> callable:
        """Create adaptive decoder that tries multiple approaches"""
        if not self.primary_context_key:
            self.logger.warning("    ⚠️ No context key found, generating adaptive key")
            self.primary_context_key = [i * 7 + 13 for i in range(256)]
            self.primary_context_len = 256
        
        def adaptive_decoder(ciphertext: str, context: str = "") -> str:
            """Adaptive decoder that tries multiple decoding methods"""
            if ciphertext in self.decode_cache:
                return self.decode_cache[ciphertext]
            
            if len(ciphertext) < 6:
                return ciphertext
            
            # Try different decoding approaches based on string characteristics
            decoders = [
                ('primary', self.primary_decoder),
                ('base64', self.base64_decoder),
                ('hex', self.hex_decoder),
                ('caesar', self.caesar_decoder),
                ('xor', self.xor_decoder),
                ('custom', self.custom_pattern_decoder),
                ('reverse', self.reverse_decoder)
            ]
            
            best_result = ""
            best_score = 0.0
            
            for decoder_name, decoder_func in decoders:
                try:
                    result = decoder_func(ciphertext)
                    if result and result != ciphertext:
                        score = self.score_decoded_text(result)
                        if score > best_score:
                            best_score = score
                            best_result = result
                            
                        # If we get a very high score, use it immediately
                        if score > 0.8:
                            break
                            
                except Exception as e:
                    self.logger.debug(f"      ❌ {decoder_name} decoder failed: {e}")
                    continue
            
            # Cache result
            final_result = best_result if best_score > 0.3 else f"UNDECODED_{ciphertext[:10]}"
            self.decode_cache[ciphertext] = final_result
            
            if best_score > 0.3:
                self.logger.debug(f"      ✅ Decoded with score {best_score:.2f}: '{ciphertext[:15]}...' -> '{final_result[:30]}...'")
            
            return final_result
        
        return adaptive_decoder

    def primary_decoder(self, ciphertext: str) -> str:
        """Primary decoder using extracted constants"""
        try:
            result = ""
            length = len(ciphertext)
            
            offset = self.constants.get('Ccw1TwHfDPZggLVK', 8)
            if length <= offset:
                return ciphertext
            
            effective_length = length - offset
            iterations = max(1, effective_length // 2)
            
            for i in range(min(iterations, 100)):  # Limit iterations
                a_idx = (i * self.constants.get('XdjDbQjncRrhyHCQ', 2)) % length
                b_idx = (i * self.constants.get('Rj7dcv1nSMPT3yj4', 2) + 
                        self.constants.get('VGg1l8gfLgy7Yfo2', 1)) % length
                
                a = ord(ciphertext[a_idx])
                b = ord(ciphertext[b_idx])
                
                a = (a - self.constants.get('HGS0YYmtehRNsqu0', 32)) & 0xFF
                b = (b - self.constants.get('TfLX6A3wPjCFybhs', 65)) & 0xFF
                b = (b << self.constants.get('R0xMkh5k90T1essw', 3)) & 0xFF
                
                key_idx = abs(i * self.constants.get('YIv48kTc2kMWJ5qx', 7) + 
                             effective_length * self.constants.get('UGiapRt2QI0mOmEw', 13))
                key_val = self.primary_context_key[key_idx % self.primary_context_len]
                
                result_byte = (a + b) ^ (
                    self.constants.get('U1uloE0ujVVvxhe2', 3) * key_val + 
                    i * self.constants.get('Q4M2uDvKXkQE7PiA', 5)
                )
                result_byte &= 0xFF
                
                if 32 <= result_byte <= 126:
                    result += chr(result_byte)
                elif result_byte == 0:
                    break
                else:
                    result += chr(result_byte % 95 + 32)
            
            return result
            
        except Exception as e:
            return ""

    def base64_decoder(self, ciphertext: str) -> str:
        """Base64 decoder with variants"""
        try:
            import base64
            
            # Try different base64 approaches
            variants = [
                ciphertext,
                ciphertext + '=',
                ciphertext + '==',
                ciphertext.replace('-', '+').replace('_', '/'),  # URL-safe base64
            ]
            
            for variant in variants:
                try:
                    decoded_bytes = base64.b64decode(variant, validate=True)
                    result = decoded_bytes.decode('utf-8', errors='ignore')
                    if result and len(result) > 0:
                        return result
                except:
                    continue
                    
        except ImportError:
            pass
        
        return ""

    def hex_decoder(self, ciphertext: str) -> str:
        """Hexadecimal decoder"""
        try:
            if len(ciphertext) % 2 == 0 and re.match(r'^[0-9A-Fa-f]+$', ciphertext):
                decoded_bytes = bytes.fromhex(ciphertext)
                return decoded_bytes.decode('utf-8', errors='ignore')
        except:
            pass
        return ""

    def caesar_decoder(self, ciphertext: str) -> str:
        """Caesar cipher decoder"""
        best_result = ""
        best_score = 0
        
        for shift in range(1, 26):
            result = ""
            for char in ciphertext:
                if char.isalpha():
                    if char.isupper():
                        result += chr((ord(char) - ord('A') - shift) % 26 + ord('A'))
                    else:
                        result += chr((ord(char) - ord('a') - shift) % 26 + ord('a'))
                else:
                    result += char
            
            score = self.score_decoded_text(result)
            if score > best_score:
                best_score = score
                best_result = result
        
        return best_result if best_score > 0.3 else ""

    def xor_decoder(self, ciphertext: str) -> str:
        """XOR decoder with various keys"""
        keys = ["key", "dayz", "arma", "game", "decode", "secret", "password"]
        
        for key in keys:
            try:
                result = ""
                key_len = len(key)
                for i, char in enumerate(ciphertext):
                    result += chr(ord(char) ^ ord(key[i % key_len]))
                
                if self.score_decoded_text(result) > 0.3:
                    return result
            except:
                continue
        
        return ""

    def custom_pattern_decoder(self, ciphertext: str) -> str:
        """Custom pattern decoder for DayZ-specific encoding"""
        try:
            # Try DayZ-specific transformations
            result = ""
            
            # Pattern 1: Reverse + Caesar
            reversed_text = ciphertext[::-1]
            for shift in [13, 7, 3, 5]:
                shifted = ""
                for char in reversed_text:
                    if char.isalpha():
                        if char.isupper():
                            shifted += chr((ord(char) - ord('A') - shift) % 26 + ord('A'))
                        else:
                            shifted += chr((ord(char) - ord('a') - shift) % 26 + ord('a'))
                    else:
                        shifted += char
                
                if self.score_decoded_text(shifted) > 0.4:
                    return shifted
            
            # Pattern 2: Alternating XOR
            for xor_val in [7, 13, 23, 31]:
                result = ""
                for i, char in enumerate(ciphertext):
                    xor_key = xor_val if i % 2 == 0 else (xor_val + 5) % 256
                    result += chr(ord(char) ^ xor_key)
                
                if self.score_decoded_text(result) > 0.4:
                    return result
            
        except:
            pass
        
        return ""

    def reverse_decoder(self, ciphertext: str) -> str:
        """Simple reverse decoder"""
        return ciphertext[::-1]

    def score_decoded_text(self, text: str) -> float:
        """Score decoded text for quality"""
        if not text or len(text) < 3:
            return 0.0
        
        score = 0.0
        total = len(text)
        
        # Printable character ratio
        printable_count = sum(1 for c in text if 32 <= ord(c) <= 126)
        score += (printable_count / total) * 0.3
        
        # Alphabetic character ratio
        alpha_count = sum(1 for c in text if c.isalpha())
        score += (alpha_count / total) * 0.3
        
        # Common English words
        common_words = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new', 'now', 'way', 'may', 'say']
        text_lower = text.lower()
        word_matches = sum(1 for word in common_words if word in text_lower)
        score += min(word_matches / 10, 0.2)
        
        # Programming keywords
        code_words = ['class', 'function', 'string', 'int', 'float', 'vector', 'array', 'if', 'else', 'for', 'while', 'return', 'void', 'public', 'private']
        code_matches = sum(1 for word in code_words if word in text_lower)
        score += min(code_matches / 5, 0.2)
        
        return min(score, 1.0)

    def scan_for_decoder_components(self, input_folder: str) -> bool:
        """Enhanced scanning for decoder components"""
        self.logger.info("🔍 Scanning for decoder components and patterns...")
        
        found_decoder = False
        input_path = Path(input_folder)
        
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf', '.txt', '.cs', '.js'}:
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
                        
                        # Analyze patterns in all files
                        self.analyze_file_patterns(content, str(file_path))
                        
                        # Extract constants
                        self.extract_constants(content)
                        
                        # Extract context keys
                        self.extract_context_keys(content)
                        
                    except Exception as e:
                        self.logger.warning(f"  ❌ Error reading {file_path}: {e}")
        
        # Log discovery results
        self.logger.info(f"  ✅ Found {self.stats['constants_found']} constants")
        self.logger.info(f"  ✅ Found {self.stats['context_keys_found']} context keys")
        self.logger.info(f"  ✅ Analyzed {self.stats['suspicious_strings_analyzed']} suspicious strings")
        self.logger.info(f"  ✅ Discovered {len(self.discovered_patterns)} pattern types")
        
        return found_decoder

    def extract_constants(self, content: str):
        """Extract constants with enhanced patterns"""
        patterns = [
            r'(\w{12,})\s*=\s*(\d+)(?:\s*[;,\)])',
            r'(\w{12,})\s*=\s*(0x[0-9A-Fa-f]+)(?:\s*[;,\)])',
            r'static\s+(?:const\s+)?(?:int|long|uint|ulong|double|float)\s+(\w{12,})\s*=\s*(\d+)',
            r'#define\s+(\w{12,})\s+(\d+)',
            r'(\w{12,})\s*=\s*([-]?\d+)(?:\s*[,}])',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for const_name, value_str in matches:
                try:
                    if value_str.lower().startswith('0x'):
                        value = int(value_str, 16)
                    else:
                        value = int(value_str)
                    
                    if (const_name in self.constants or 
                        (len(const_name) >= 12 and 0 <= value <= 0xFFFFFF)):
                        
                        old_value = self.constants.get(const_name, "unknown")
                        self.constants[const_name] = value
                        
                        if old_value != value:
                            self.stats['constants_found'] += 1
                            self.logger.debug(f"    📊 {const_name} = {value}")
                            
                except ValueError:
                    continue

    def extract_context_keys(self, content: str):
        """Extract context keys with enhanced patterns"""
        patterns = [
            r'(\w{12,})\s*=\s*\{([0-9,\s\-x]+)\}',
            r'(\w{12,})\s*=\s*new\s+(?:int|uint|long)\[\]\s*\{([0-9,\s\-x]+)\}',
            r'static\s+(?:const\s+)?(?:int|uint|long)\s+(\w{12,})\[\]\s*=\s*\{([0-9,\s\-x]+)\}',
            r'(\w{12,})\.(?:Add|Push|Insert)\s*\(\s*([0-9\-x]+)\s*\)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for array_name, array_data in matches:
                if len(array_name) >= 12:
                    try:
                        if ',' in array_data:
                            values = []
                            for val_str in array_data.split(','):
                                val_str = val_str.strip()
                                if val_str:
                                    if val_str.lower().startswith('0x'):
                                        values.append(int(val_str, 16))
                                    else:
                                        values.append(int(val_str))
                            
                            if len(values) > 5:
                                self.context_keys[array_name] = values
                                self.stats['context_keys_found'] += 1
                                self.logger.debug(f"    🔑 Key array {array_name}: {len(values)} elements")
                                
                                if not self.primary_context_key or len(values) > len(self.primary_context_key):
                                    self.primary_context_key = values
                                    self.primary_context_len = len(values)
                                    
                    except ValueError as e:
                        self.logger.debug(f"    ❌ Failed to parse array {array_name}: {e}")

    def extract_decoder_components(self, content: str, file_path: str):
        """Extract decoder function implementations"""
        self.logger.debug(f"    🔬 Analyzing decoder in: {file_path}")
        
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
        """Analyze hash function used in decoding"""
        hash_patterns = [
            r'(\w+)\s*=\s*(\w+)\s*\*\s*(\d+)\s*\+\s*(\d+)',
            r'(\w+)\s*=\s*\(\s*(\w+)\s*\+\s*(\d+)\s*\)\s*\%\s*(\d+)',
            r'(\w+)\s*=\s*(\w+)\s*\^\s*(\w+)',
        ]
        
        for pattern in hash_patterns:
            matches = re.findall(pattern, func_body)
            if matches:
                self.logger.debug(f"      🔍 Hash pattern found: {matches[0]}")

    def remove_junk_code_patterns(self, content: str) -> str:
        """Enhanced junk code removal"""
        original_length = len(content)
        
        # Comprehensive junk patterns
        junk_patterns = [
            # Dead code patterns
            (r'if\s*\(\s*(?:false|0)\s*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', 'false conditions'),
            (r'if\s*\(\s*(?:true|1)\s*\)\s*\{\s*\}\s*else\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', 'always true conditions'),
            
            # Empty constructs
            (r'for\s*\([^)]*\)\s*\{\s*\}', 'empty for loops'),
            (r'while\s*\([^)]*\)\s*\{\s*\}', 'empty while loops'),
            (r'if\s*\([^)]*\)\s*\{\s*\}', 'empty if blocks'),
            (r'switch\s*\([^)]*\)\s*\{\s*\}', 'empty switch blocks'),
            
            # Redundant operations
            (r'(\w+)\s*=\s*(\w+)\s*;\s*\1\s*=\s*\2\s*;', 'redundant assignments'),
            (r'(\w+)\s*\+=\s*0\s*;', 'useless additions'),
            (r'(\w+)\s*\*=\s*1\s*;', 'useless multiplications'),
            
            # Dummy function calls
            (r'\w+\s*\(\s*"[^"]*"\s*,\s*vector\s*\([^)]*\)\s*\)\s*;', 'dummy function calls'),
            (r'Debug\s*\.\s*Log\s*\(\s*"[^"]*"\s*\)\s*;', 'debug logs'),
            
            # Junk variable declarations
            (r'(?:int|float|string|bool)\s+\w+\s*=\s*(?:0|false|""|\'\');\s*(?=\n)', 'unused variable declarations'),
            
            # Dead code after return/break/continue
            (r'(?:return|break|continue)\s*[^;]*;\s*[^}]+(?=\})', 'dead code after control statements'),
            
            # Excessive whitespace and formatting
            (r'\n\s*\n\s*\n+', 'excessive newlines'),
            (r'[ \t]+\n', 'trailing whitespace'),
            (r'^\s*\n', 'leading empty lines'),
            
            # Commented out code blocks
            (r'\/\*[^*]*\*+(?:[^/*][^*]*\*+)*\/', 'block comments'),
            (r'\/\/[^\n]*\n', 'line comments'),
            
            # Obfuscation artifacts
            (r'\{\s*\}', 'empty blocks'),
            (r';\s*;+', 'double semicolons'),
        ]
        
        for pattern, description in junk_patterns:
            before_matches = len(re.findall(pattern, content, re.MULTILINE | re.DOTALL))
            content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
            after_matches = len(re.findall(pattern, content, re.MULTILINE | re.DOTALL))
            
            removed = before_matches - after_matches
            if removed > 0:
                self.stats['junk_patterns_removed'] += removed
                self.logger.debug(f"      🗑️ Removed {removed} {description}")
        
        # Final cleanup
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+\n', '\n', content)
        content = content.strip()
        
        reduction = original_length - len(content)
        self.stats['total_reduction_bytes'] += reduction
        
        return content

    def deobfuscate_identifiers(self, content: str) -> str:
        """Enhanced identifier deobfuscation"""
        result = content
        
        # Enhanced known identifiers based on common DayZ obfuscation
        enhanced_identifiers = {
            **self.known_identifiers,
            # Add patterns discovered during analysis
        }
        
        # Look for additional obfuscated identifiers
        obfuscated_pattern = r'\b([A-Za-z]{2}[A-Za-z0-9]{10,})\b'
        potential_obfuscated = re.findall(obfuscated_pattern, content)
        
        # Analyze potential obfuscated identifiers
        for identifier in set(potential_obfuscated):
            if len(identifier) >= 12 and identifier not in enhanced_identifiers:
                # Try to determine what this might be
                context_hints = self.analyze_identifier_context(content, identifier)
                if context_hints:
                    suggested_name = self.suggest_clean_name(identifier, context_hints)
                    enhanced_identifiers[identifier] = suggested_name
        
        # Apply replacements
        for obfuscated, clean in enhanced_identifiers.items():
            if obfuscated in result:
                pattern = r'\b' + re.escape(obfuscated) + r'\b'
                old_count = len(re.findall(pattern, result))
                result = re.sub(pattern, clean, result)
                new_count = len(re.findall(pattern, result))
                
                if old_count > new_count:
                    self.stats['identifiers_deobfuscated'] += (old_count - new_count)
                    self.logger.debug(f"      🔤 {obfuscated} → {clean} ({old_count - new_count} times)")
        
        return result

    def analyze_identifier_context(self, content: str, identifier: str) -> List[str]:
        """Analyze context around identifier to suggest clean name"""
        contexts = []
        
        # Look for usage patterns
        patterns = [
            (rf'{identifier}\s*\(', 'function'),
            (rf'class\s+{identifier}', 'class'),
            (rf'{identifier}\s*=\s*new', 'object'),
            (rf'{identifier}\s*\[\s*\]', 'array'),
            (rf'string\s+{identifier}', 'string_var'),
            (rf'int\s+{identifier}', 'int_var'),
            (rf'float\s+{identifier}', 'float_var'),
            (rf'vector\s+{identifier}', 'vector_var'),
        ]
        
        for pattern, context_type in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                contexts.append(context_type)
        
        return contexts

    def suggest_clean_name(self, obfuscated: str, contexts: List[str]) -> str:
        """Suggest clean name based on context"""
        if 'function' in contexts:
            if 'decode' in obfuscated.lower() or 'decrypt' in obfuscated.lower():
                return 'DecodeFunction'
            elif 'get' in obfuscated.lower():
                return 'GetFunction'
            else:
                return 'CustomFunction'
        elif 'class' in contexts:
            return 'CustomClass'
        elif 'array' in contexts:
            return 'DataArray'
        elif any(var_type in contexts for var_type in ['string_var', 'int_var', 'float_var', 'vector_var']):
            return 'DataVariable'
        else:
            return f'Cleaned_{obfuscated[:8]}'

    def process_file_content(self, content: str, file_path: str) -> str:
        """Enhanced file content processing"""
        self.logger.debug(f"    🔧 Processing: {Path(file_path).name}")
        
        # Step 1: Remove junk code first
        content = self.remove_junk_code_patterns(content)
        
        # Step 2: Deobfuscate identifiers
        content = self.deobfuscate_identifiers(content)
        
        # Step 3: Create adaptive decoder
        decoder = self.create_adaptive_decoder()
        
        # Step 4: Enhanced string detection and decoding
        found_strings = self.enhanced_string_detection(content)
        
        self.logger.debug(f"      🔍 Found {len(found_strings)} potential encoded strings")
        
        # Process each found string
        replacements = {}
        for encoded_string, context, position in found_strings:
            self.stats['obfuscated_strings_found'] += 1
            
            # Try to decode
            decoded = decoder(encoded_string, context)
            
            if (decoded and 
                not decoded.startswith(('DECODE_ERROR_', 'ALT_FAILED_', 'UNDECODED_')) and
                self.score_decoded_text(decoded) > 0.3):
                
                self.stats['successfully_decoded'] += 1
                replacements[encoded_string] = decoded
                self.logger.debug(f"      ✅ '{encoded_string[:15]}...' → '{decoded[:30]}...'")
            else:
                self.logger.debug(f"      ❌ Failed to decode: '{encoded_string[:15]}...'")
        
        # Apply replacements to content
        for encoded, decoded in replacements.items():
            # Be careful with replacements to avoid breaking code structure
            safe_patterns = [
                (rf'"{re.escape(encoded)}"', f'"{decoded}"  /* was "{encoded[:15]}..." */'),
                (rf'(\w+\s*\.\s*\w+\s*\(\s*)"{re.escape(encoded)}"(\s*(?:,\s*[^)]+)?\s*\))', 
                 rf'\1"{decoded}"\2  /* decoded from "{encoded[:15]}..." */'),
            ]
            
            for pattern, replacement in safe_patterns:
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    break
        
        # Step 5: Add processing header
        processing_info = self.generate_file_header(file_path, len(found_strings), len(replacements))
        
        return processing_info + content

    def generate_file_header(self, file_path: str, strings_found: int, strings_decoded: int) -> str:
        """Generate informative header for processed files"""
        decode_rate = (strings_decoded / max(strings_found, 1)) * 100
        
        header = f"""/*
 * ================================================================
 * DayZ Enhanced Deobfuscation Results
 * ================================================================
 * File: {Path(file_path).name}
 * Original Size: {Path(file_path).stat().st_size if Path(file_path).exists() else 'unknown'} bytes
 * 
 * Processing Results:
 * - Decoder Type: {'Adaptive Multi-Method' if self.primary_context_key else 'Heuristic Fallback'}
 * - Constants Available: {len([k for k, v in self.constants.items() if v != 0])}
 * - Context Keys: {len(self.context_keys)} arrays
 * - Strings Found: {strings_found}
 * - Successfully Decoded: {strings_decoded} ({decode_rate:.1f}%)
 * - Junk Patterns Removed: {self.stats['junk_patterns_removed']}
 * - Identifiers Cleaned: {self.stats['identifiers_deobfuscated']}
 * 
 * Decoder Methods Used:
 * - Primary Algorithm: {'✓' if self.primary_context_key else '✗'}
 * - Base64 Decoder: ✓
 * - Hex Decoder: ✓
 * - Caesar Cipher: ✓
 * - XOR Decoder: ✓
 * - Custom Patterns: ✓
 * - Reverse Transform: ✓
 * 
 * Note: Decoded strings are marked with /* decoded from "..." */ comments
 * ================================================================
 */

"""
        return header

    def process_single_file(self, input_file: str, output_file: str) -> bool:
        """Process single file with enhanced error handling"""
        try:
            # Read input file with multiple encodings
            content = None
            encodings = ['utf-8', 'latin1', 'cp1252', 'utf-16']
            
            for encoding in encodings:
                try:
                    with open(input_file, 'r', encoding=encoding, errors='ignore') as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if not content or not content.strip():
                self.logger.warning(f"    ⚠️ Could not read or empty file: {input_file}")
                return False
            
            # Process content
            processed_content = self.process_file_content(content, input_file)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # Write output file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            self.stats['files_processed'] += 1
            
            # Calculate file size reduction
            original_size = len(content)
            processed_size = len(processed_content)
            reduction = original_size - processed_size
            
            self.logger.info(f"    ✅ {Path(input_file).name} ({original_size:,} → {processed_size:,} bytes, {reduction:+,})")
            return True
            
        except Exception as e:
            self.logger.error(f"    ❌ Error processing {input_file}: {e}")
            return False

    def process_directory(self, input_folder: str) -> bool:
        """Enhanced directory processing with better organization"""
        self.logger.info("🚀 Starting enhanced deobfuscation process...")
        
        # Setup output directory
        self.setup_output_directory()
        
        # Phase 1: Comprehensive scanning
        self.logger.info("📊 Phase 1: Scanning and pattern analysis...")
        decoder_found = self.scan_for_decoder_components(input_folder)
        
        if not decoder_found:
            self.logger.warning("⚠️ No specific decoder functions found, using adaptive approach")
        
        # Phase 2: File processing
        self.logger.info("🔧 Phase 2: Processing files...")
        input_path = Path(input_folder)
        success_count = 0
        total_files = 0
        
        # Count total files first
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf', '.txt', '.cs', '.js', '.sqc'}:
                    total_files += 1
        
        processed_files = 0
        
        # Process files with progress indication
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if Path(file).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.sqf', '.txt', '.cs', '.js', '.sqc'}:
                    input_file = Path(root) / file
                    relative_path = input_file.relative_to(input_path)
                    output_file = Path(self.output_dir) / relative_path
                    
                    processed_files += 1
                    progress = (processed_files / total_files) * 100
                    
                    self.logger.info(f"  📄 [{progress:5.1f}%] Processing: {relative_path}")
                    
                    if self.process_single_file(str(input_file), str(output_file)):
                        success_count += 1
        
        # Phase 3: Generate reports
        self.logger.info("📋 Phase 3: Generating reports...")
        self.generate_summary_report()
        self.generate_analysis_report()
        
        return success_count > 0

    def generate_analysis_report(self):
        """Generate detailed analysis report"""
        analysis_path = Path(self.output_dir) / "analysis_report.txt"
        
        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write("DayZ Enhanced Deobfuscation - Detailed Analysis Report\n")
            f.write("=" * 70 + "\n\n")
            
            # Suspicious strings analysis
            f.write("SUSPICIOUS STRINGS ANALYSIS\n")
            f.write("-" * 30 + "\n")
            
            if self.string_analysis['suspicious_strings']:
                # Group by characteristics
                by_length = {}
                for item in self.string_analysis['suspicious_strings']:
                    length_range = f"{(item['length']//10)*10}-{(item['length']//10)*10+9}"
                    if length_range not in by_length:
                        by_length[length_range] = []
                    by_length[length_range].append(item)
                
                for length_range, items in sorted(by_length.items()):
                    f.write(f"\nLength {length_range} characters:\n")
                    for item in items[:5]:  # Show first 5 examples
                        f.write(f"  File: {item['file']}\n")
                        f.write(f"  String: {item['string'][:50]}{'...' if len(item['string']) > 50 else ''}\n")
                        f.write(f"  Uppercase: {item['uppercase_ratio']:.2f}, Digits: {item['digit_ratio']:.2f}\n")
                        f.write("\n")
            else:
                f.write("No suspicious strings detected.\n")
            
            # Encoding analysis
            f.write("\nENCODING TYPE ANALYSIS\n")
            f.write("-" * 25 + "\n")
            
            if self.string_analysis['potential_encoded']:
                encoding_stats = {}
                for item in self.string_analysis['potential_encoded']:
                    enc_type = item['type']
                    if enc_type not in encoding_stats:
                        encoding_stats[enc_type] = {'count': 0, 'avg_confidence': 0}
                    encoding_stats[enc_type]['count'] += 1
                    encoding_stats[enc_type]['avg_confidence'] += item['confidence']
                
                for enc_type, stats in encoding_stats.items():
                    avg_conf = stats['avg_confidence'] / stats['count']
                    f.write(f"{enc_type}: {stats['count']} instances (avg confidence: {avg_conf:.2f})\n")
            else:
                f.write("No encoding patterns detected.\n")
            
            # Pattern discovery
            f.write(f"\nDISCOVERED PATTERNS\n")
            f.write("-" * 20 + "\n")
            
            if self.discovered_patterns:
                for pattern in sorted(self.discovered_patterns):
                    f.write(f"- {pattern}\n")
            else:
                f.write("No specific patterns discovered.\n")
            
            # Constants analysis
            f.write(f"\nCONSTANTS FOUND\n")
            f.write("-" * 15 + "\n")
            
            active_constants = {k: v for k, v in self.constants.items() if v != 0}
            if active_constants:
                for const_name, value in sorted(active_constants.items()):
                    f.write(f"{const_name} = {value}\n")
            else:
                f.write("No meaningful constants extracted.\n")
            
            # Context keys
            f.write(f"\nCONTEXT KEY ARRAYS\n")
            f.write("-" * 18 + "\n")
            
            if self.context_keys:
                for key_name, key_array in self.context_keys.items():
                    f.write(f"{key_name}: {len(key_array)} elements\n")
                    f.write(f"  Sample: {key_array[:10]}{'...' if len(key_array) > 10 else ''}\n")
            else:
                f.write("No context key arrays found.\n")
        
        self.logger.info(f"📄 Analysis report saved: {analysis_path}")

    def generate_summary_report(self):
        """Generate enhanced summary report"""
        report_path = Path(self.output_dir) / "deobfuscation_report.json"
        
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
                'identifiers_deobfuscated': self.stats['identifiers_deobfuscated'],
                'suspicious_strings_analyzed': self.stats['suspicious_strings_analyzed'],
                'patterns_discovered': len(self.discovered_patterns)
            },
            'decoder_config': {
                'constants_found': len([k for k, v in self.constants.items() if v != 0]),
                'context_keys_found': len(self.context_keys),
                'primary_context_length': self.primary_context_len,
                'cache_entries': len(self.decode_cache),
                'discovered_patterns': list(self.discovered_patterns)
            },
            'analysis_results': {
                'suspicious_strings_count': len(self.string_analysis['suspicious_strings']),
                'potential_encoded_count': len(self.string_analysis['potential_encoded']),
                'encoding_types_found': list(set(item['type'] for item in self.string_analysis['potential_encoded']))
            },
            'discovered_constants': {k: v for k, v in self.constants.items() if v != 0},
            'context_arrays': {k: len(v) for k, v in self.context_keys.items()},
            'known_identifiers': self.known_identifiers
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        
        # Enhanced console summary
        self.logger.info("=" * 70)
        self.logger.info("📊 ENHANCED DEOBFUSCATION SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"📁 Files Scanned:        {self.stats['files_scanned']:,}")
        self.logger.info(f"⚡ Files Processed:      {self.stats['files_processed']:,} ({processing_rate:.1f}%)")
        self.logger.info(f"🔤 Strings Found:        {self.stats['obfuscated_strings_found']:,}")
        self.logger.info(f"✅ Strings Decoded:      {self.stats['successfully_decoded']:,} ({decode_rate:.1f}%)")
        self.logger.info(f"🗑️ Junk Removed:         {self.stats['junk_patterns_removed']:,} patterns")
        self.logger.info(f"📝 Identifiers Cleaned:  {self.stats['identifiers_deobfuscated']:,}")
        self.logger.info(f"💾 Size Reduction:       {self.stats['total_reduction_bytes']:,} bytes")
        self.logger.info(f"🔍 Suspicious Analyzed:  {self.stats['suspicious_strings_analyzed']:,}")
        self.logger.info(f"🎯 Patterns Discovered:  {len(self.discovered_patterns)}")
        self.logger.info(f"🔑 Context Arrays:       {len(self.context_keys)}")
        self.logger.info(f"📊 Constants Found:      {len([k for k, v in self.constants.items() if v != 0])}")
        self.logger.info("=" * 70)
        
        if decode_rate > 0:
            self.logger.info(f"🎉 SUCCESS: {decode_rate:.1f}% of strings were successfully decoded!")
        else:
            self.logger.info("⚠️  No strings were decoded. Check analysis report for details.")
        
        self.logger.info(f"📄 Full report: {report_path}")
        self.logger.info(f"📄 Analysis report: {Path(self.output_dir) / 'analysis_report.txt'}")
        self.logger.info(f"📂 Output directory: {Path(self.output_dir).absolute()}")


if __name__ == "__main__":
    # Configuration
    INPUT_FOLDER = "/home/alca/Schreibtisch/old/LBmaster-serverside_NEWEST/AdvancedGroups_Server_latest_crackme.pbo"
    OUTPUT_FOLDER = "/home/alca/Schreibtisch/old/LBmaster-serverside_NEWEST/AdvancedGroups_Server_cleaned/"
    
    # Create enhanced deobfuscator
    deobfuscator = EnhancedDayZDeobfuscator(output_dir=OUTPUT_FOLDER, verbose=True)
    
    # Process directory
    success = deobfuscator.process_directory(INPUT_FOLDER)
    
    if success:
        print(f"\n🎯 Enhanced deobfuscation complete! Check: {OUTPUT_FOLDER}")
        print(f"📊 View detailed analysis in: {OUTPUT_FOLDER}/analysis_report.txt")
    else:
        print("\n❌ Deobfuscation failed. Check logs for details.")