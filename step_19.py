import re
import os
import hashlib
import struct
from collections import defaultdict, Counter

class DeobfuscationMapper:
    def __init__(self):
        self.identifier_patterns = {
            'classes': set(),
            'methods': set(), 
            'variables': set(),
            'encoded_strings': set(),
            'constants': set()
        }
        self.name_mappings = {}
        self.semantic_hints = {}
        
    def analyze_file(self, content):
        """Extract all obfuscated identifiers and patterns"""
        patterns = {
            'class_def': r'class\s+([A-Za-z][A-Za-z0-9]+)\s*{',
            'method_def': r'(?:void|bool|int|string|[A-Za-z][A-Za-z0-9]+)\s+([A-Za-z][A-Za-z0-9]+)\s*\(',
            'variable_decl': r'(?:string|int|bool|float)\s+([A-Za-z][A-Za-z0-9]+)\s*=',
            'encoded_strings': r'"([A-Z]{20,})"',
            'hash_operations': r'\.Hash\(\)',
            'substring_ops': r'\.Substring\((\d+),\s*(\d+)\)',
            'mathematical_ops': r'\((-?\d+)\s*[-+*/^]\s*.*?\)',
            # Add patterns for the specific markers
            'marker_patterns': r'(GA91UCDQYUVawLMs|EVy2D5PaA01T99Ml|SfFuxbdumezDa91W|Ns7IynOBl5RX6MyZ)',
        }
        
        results = {}
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, content)
            results[pattern_name] = matches
            
        return results
    
    def categorize_identifiers(self, identifiers):
        """Categorize identifiers by their apparent function"""
        categories = {
            'likely_classes': [],
            'likely_methods': [],
            'likely_variables': [],
            'likely_constants': []
        }
        
        for identifier in identifiers:
            # Heuristics based on naming patterns and usage
            if len(identifier) > 15 and identifier[0].isupper():
                categories['likely_classes'].append(identifier)
            elif len(identifier) > 10 and any(char.isupper() for char in identifier[1:]):
                categories['likely_methods'].append(identifier)
            elif identifier.isupper() and len(identifier) < 10:
                categories['likely_constants'].append(identifier)
            else:
                categories['likely_variables'].append(identifier)
                
        return categories

class KeyDecoder:
    def __init__(self):
        self.known_keys = {}
        self.decoding_contexts = [
            "", "default", "secret", "password", "key", "context", 
            "decode", "obfuscate", "hidden", "private", "test", 
            "admin", "root", "config", "main", "init", "core"
        ]
    
    def decode_value(self, key, context=""):
        """Decode a value using SHA256 hash method"""
        hex_value = hashlib.sha256((key + context).encode()).hexdigest()[:8]
        int_value = int(hex_value, 16)
        return float(int_value)
    
    def decode_key_comprehensive(self, encoded_key, all_contexts=True):
        """Decode a key using multiple contexts and methods"""
        results = {}
        
        if all_contexts:
            contexts = self.decoding_contexts
        else:
            contexts = [""]
            
        for context in contexts:
            try:
                # Method 1: SHA256 + hex to int
                hex_value = hashlib.sha256((encoded_key + context).encode()).hexdigest()[:8]
                int_value = int(hex_value, 16)
                float_value = float(int_value)
                
                results[f"sha256_{context}"] = {
                    'hex': hex_value,
                    'int': int_value,
                    'float': float_value
                }
                
                # Method 2: MD5 approach
                md5_hex = hashlib.md5((encoded_key + context).encode()).hexdigest()[:8]
                md5_int = int(md5_hex, 16)
                
                results[f"md5_{context}"] = {
                    'hex': md5_hex,
                    'int': md5_int,
                    'float': float(md5_int)
                }
                
            except Exception as e:
                results[f"error_{context}"] = str(e)
                
        return results
    
    def find_string_patterns(self, encoded_strings):
        """Look for patterns in encoded strings that might indicate their purpose"""
        patterns = {}
        
        for string in encoded_strings:
            patterns[string] = {
                'length': len(string),
                'char_frequency': Counter(string),
                'repeating_patterns': self.find_repeating_substrings(string),
                'possible_meanings': self.guess_string_meaning(string)
            }
            
        return patterns
    
    def find_repeating_substrings(self, s, min_length=3):
        """Find repeating substrings that might be encoding artifacts"""
        repeating = []
        for length in range(min_length, len(s)//2 + 1):
            for start in range(len(s) - length + 1):
                substring = s[start:start + length]
                if s.count(substring) > 1:
                    repeating.append((substring, s.count(substring)))
        return list(set(repeating))
    
    def guess_string_meaning(self, encoded_string):
        """Heuristic guessing of what an encoded string might represent"""
        guesses = []
        
        # Length-based guesses
        if len(encoded_string) == 32:
            guesses.append("possible_md5_hash")
        elif len(encoded_string) == 64:
            guesses.append("possible_sha256_hash")
        elif len(encoded_string) > 40:
            guesses.append("likely_obfuscated_identifier")
        elif len(encoded_string) < 20:
            guesses.append("possible_short_key")
            
        # Pattern-based guesses
        if encoded_string.startswith(('HC', 'GC', 'MC')):
            guesses.append("possible_type_prefix")
        if 'OO' in encoded_string:
            guesses.append("contains_double_O_pattern")
            
        return guesses

class MathOperationDecoder:
    def __init__(self):
        self.known_operations = {}
        
    def analyze_math_expression(self, expression):
        """Analyze mathematical expressions used in obfuscation"""
        # Extract components
        constants = re.findall(r'-?\d+', expression)
        operations = re.findall(r'[+\-*/^&|]', expression)
        
        analysis = {
            'constants': [int(c) for c in constants],
            'operations': operations,
            'expression': expression,
            'likely_purpose': self.guess_math_purpose(expression)
        }
        
        return analysis
    
    def guess_math_purpose(self, expression):
        """Guess the purpose of mathematical operations"""
        if 'Hash()' in expression:
            return "hash_validation"
        elif 'Substring' in expression:
            return "substring_checksum"
        elif '^' in expression:
            return "xor_obfuscation"
        elif '*' in expression and any(c > 1000000 for c in re.findall(r'\d+', expression)):
            return "large_multiplier_scrambling"
        else:
            return "unknown_calculation"
    
    def reverse_math_operation(self, expression, target_result=None):
        """Attempt to reverse mathematical operations"""
        # This would contain logic to reverse the mathematical obfuscation
        # Based on the patterns you've identified
        pass

class SpecificDecoder:
    """Handles the specific obfuscation patterns found in the second script"""
    
    def __init__(self):
        self.decoder = KeyDecoder()
    
    def process_input_string(self, input_string, context=""):
        """Process Type 1 obfuscation (GA91UCDQYUVawLMs marker)"""
        try:
            value1 = self.decoder.decode_value("HCOJJAGJHPOKCHJEIEPCCIGNHJDLGJPOBGIGNLFHOFIO", context)
            value2 = self.decoder.decode_value("GCBIPBBJEPKKAHMENEACFIHNPJDLNJLOKGNGDIDBKODG", context)
            value3 = self.decoder.decode_value("MOHJAFPKGKDAFPODGPHJDPNMKFMEPAIMEHPAKMLDPOFEFDLK", context)
            value4 = self.decoder.decode_value("ECBIABEJBPKKHHGELEFCFIGNEJBLGJEOBGLGNHNGMHAL", context)
            value5 = self.decoder.decode_value("NCDOGBBDOOEMGLPOPNMIKPCCIEAOFJMBHECKNJCKKH", context)
            value6 = self.decoder.decode_value("GCBIOBCJHPNKMHJEKECCAIKNAJBLDJNOEGJGADDCHKKI", context)
            vector1 = (1, 1, 1)  
            value7 = self.decoder.decode_value("GCBIOBBJDPKKFHOEAEBCFIINCJDLNJMOCGEGIFLPFEHC", context)
            string1 = self.decoder.decode_value("LAEMBPGBMBJNEFMAFHGPLDALDNEM", context)  
            value8 = self.decoder.decode_value("LMDCPKJMHDEOJNIBBKCMHPOHOKNDCGJLGFHFMCKEIMFBGE", context)
            value9 = self.decoder.decode_value("LMDCMKPMFDBOBNPBPKFMBPIHOKODOGJLBFKFJCNIJMBBLM", context)
            value10 = self.decoder.decode_value("CCDOGBBDMOGMGLKOANIIPPLCKEBODJEBGEOCCJOMOB", context)
            value11 = self.decoder.decode_value("HCHJGBMIDPKKFHPEPEGCJIKNBJBLMJJOGGEGCJHDHFID", context)
            value12 = self.decoder.decode_value("ICMPPBJCPOAMALNOCNKIMPCCMEAOEJFBPEDOMLECJB", context)
            vector2 = (2, 3, 4)  
            value13 = self.decoder.decode_value("DCAODBBDJOGMILPODNDIIPCCMEBOEJEBIECDMHFCPF", context)
            value14 = self.decoder.decode_value("GCBIEBKJJPKKMHKEOEPCJIGNHJDLGJIOCGFGBBNHBEIC", context)
            vector3 = (5, 6, 7)  
            string2 = self.decoder.decode_value("OOLAOALOJKAN", context)  
            string3 = self.decoder.decode_value("OOLAOALOJKAN", context)  

            # Check if input_string is long enough for the slice operation
            if len(input_string) < 43:
                raise ValueError(f"Input string too short: {len(input_string)} < 43")
            
            result1 = (-547234341 - int(hashlib.md5(input_string[35:43].encode()).hexdigest(), 16) * 1983144419) ^ -1899935677

            return {
                'values': [value1, value2, value3, value4, value5, value6, value7, value8, value9, value10, value11, value12, value13, value14],
                'vectors': [vector1, vector2, vector3],
                'strings': [string1, string2, string3],
                'result': result1,
                'original': input_string,
                'type': 'GA91UCDQYUVawLMs'
            }
        except Exception as e:
            raise Exception(f"Error in process_input_string: {str(e)}")

    def process_input_string2(self, input_string, context=""):
        """Process Type 2 obfuscation (EVy2D5PaA01T99Ml marker)"""
        try:
            value15 = self.decoder.decode_value("BINJDEMEPDMFNEJHMMGPHJKI", context)
            vector4 = (8, 9, 10)  
            vector5 = (11, 12, 13)  
            value16 = self.decoder.decode_value("GCBIABCJBPKKGHJEJEFCAIMNDJGLCJIOCGOGDPNOLHMC", context)
            string4 = self.decoder.decode_value("FJDGLCFEGKNCDHKMPBCIGMEGBJ", context)  
            value17 = self.decoder.decode_value("DCBOCBBDKOHMCLKOENCILPKCNEGOEJNBHEEHJPCDHL", context)
            
            # Check if input_string is long enough for the slice operation
            if len(input_string) < 116:
                raise ValueError(f"Input string too short: {len(input_string)} < 116")
            
            result2 = (872895793 - int(hashlib.md5(input_string[109:116].encode()).hexdigest(), 16) * 1544140062) ^ -531823200

            value18 = self.decoder.decode_value("MCGOBBBDJOHMJLIOONJIMPCCMEAOAJPBGEJKNOBGOM", context)
            vector6 = (14, 15, 16)  
            value19 = self.decoder.decode_value("GNMDDLIMFDHOKNKBLKFMAPBHLKFDEGKLHFAFLCMILGGIBB", context)
            vector7 = (17, 18, 19)  
            string5 = self.decoder.decode_value("JKLFMEELLCKNCCEFOCCPJJPJKFHDCH", context)  
            string6 = self.decoder.decode_value("JKLFMEELLCKNCCEFOCCPJJPJKFHDCH", context)  

            return {
                'values': [value15, value16, value17, value18, value19],
                'vectors': [vector4, vector5, vector6, vector7],
                'strings': [string4, string5, string6],
                'result': result2,
                'original': input_string,
                'type': 'EVy2D5PaA01T99Ml'
            }
        except Exception as e:
            raise Exception(f"Error in process_input_string2: {str(e)}")

    def reverse_process_input_string(self, output_dict):
        """Reverse Type 1 processing"""
        result1 = output_dict['result']
        try:
            calc_value = (-result1 - 547234341 + 1899935677) // 1983144419
            if calc_value < 0:
                calc_value = abs(calc_value)
            fake_hash = hex(calc_value)[2:].zfill(8)
            fake_substring = bytes.fromhex(fake_hash).decode('latin1', errors='ignore')  
            fake_input_string = "A" * 35 + fake_substring + "B" * (100 - 43)
            fake_input_string = fake_input_string.replace("50", "#").replace("05", "50").replace("#", "05")
            return fake_input_string
        except Exception as e:
            return f"Could not reverse process: {str(e)}"

    def reverse_process_input_string2(self, output_dict):
        """Reverse Type 2 processing"""
        result2 = output_dict['result']
        try:
            calc_value = (872895793 - result2 + 531823200) // 1544140062
            if calc_value < 0:
                calc_value = abs(calc_value)
            fake_hash = hex(calc_value)[2:].zfill(8)
            fake_substring = bytes.fromhex(fake_hash).decode('latin1', errors='ignore')  
            fake_input_string = "A" * 109 + fake_substring + "B" * (150 - 116)
            fake_input_string = fake_input_string.replace("31", "#").replace("13", "31").replace("#", "13")
            return fake_input_string
        except Exception as e:
            return f"Could not reverse process: {str(e)}"

    def try_multiple_contexts(self, content, process_func):
        """Try multiple common context strings to see if any produce meaningful results"""
        common_contexts = [
            "", "default", "secret", "password", "key", "context",
            "decode", "obfuscate", "hidden", "private", "test",
            "admin", "root", "config", "main", "init", "core"
        ]
        
        results = []
        errors = []
        
        for context in common_contexts:
            try:
                result = process_func(content, context)
                results.append((context, result))
            except Exception as e:
                errors.append((context, str(e)))
                continue
        
        return results, errors

class ComprehensiveDeobfuscator:
    def __init__(self):
        self.mapper = DeobfuscationMapper()
        self.decoder = KeyDecoder()
        self.math_decoder = MathOperationDecoder()
        self.specific_decoder = SpecificDecoder()
        self.file_results = {}
        
    def is_encoded_file(self, file_path):
        """Check if file contains obfuscation patterns"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin1', 'cp1252', 'ascii']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read(1000)  # Read more characters for better detection
                        obfuscation_markers = [
                            'GA91UCDQYUVawLMs', 'EVy2D5PaA01T99Ml',
                            'SfFuxbdumezDa91W', 'Ns7IynOBl5RX6MyZ'
                        ]
                        if any(marker in content for marker in obfuscation_markers):
                            return True, encoding, content
                except UnicodeDecodeError:
                    continue
            
            # If text reading fails, try binary mode
            try:
                with open(file_path, 'rb') as f:
                    content = f.read(1000)
                    content_str = content.decode('latin1', errors='ignore')
                    obfuscation_markers = [
                        'GA91UCDQYUVawLMs', 'EVy2D5PaA01T99Ml',
                        'SfFuxbdumezDa91W', 'Ns7IynOBl5RX6MyZ'
                    ]
                    if any(marker in content_str for marker in obfuscation_markers):
                        return True, 'binary', content_str
            except:
                pass
                
            return False, None, None
        except Exception as e:
            print(f"Error checking file {file_path}: {str(e)}")
            return False, None, None
    
    def analyze_file_content(self, file_path, content):
        """Analyze the file content to provide debugging information"""
        analysis = {
            'file_size': len(content),
            'has_marker1': "GA91UCDQYUVawLMs" in content,
            'has_marker2': "EVy2D5PaA01T99Ml" in content,
            'has_marker3': "SfFuxbdumezDa91W" in content,
            'has_marker4': "Ns7IynOBl5RX6MyZ" in content,
            'marker1_pos': content.find("GA91UCDQYUVawLMs") if "GA91UCDQYUVawLMs" in content else -1,
            'marker2_pos': content.find("EVy2D5PaA01T99Ml") if "EVy2D5PaA01T99Ml" in content else -1,
            'printable_chars': sum(1 for c in content if c.isprintable()),
            'first_200_chars': repr(content[:200]),
            'last_200_chars': repr(content[-200:]) if len(content) > 200 else repr(content),
            'chars_35_to_43': repr(content[35:43]) if len(content) > 43 else "N/A (too short)",
            'chars_109_to_116': repr(content[109:116]) if len(content) > 116 else "N/A (too short)"
        }
        return analysis
        
    def process_single_file(self, file_path):
        """Process a single file for obfuscation patterns"""
        is_encoded, encoding, preview_content = self.is_encoded_file(file_path)
        
        if not is_encoded:
            return {'is_obfuscated': False}
        
        # Read the full file content
        try:
            if encoding == 'binary':
                with open(file_path, 'rb') as f:
                    content = f.read().decode('latin1', errors='ignore')
            else:
                with open(file_path, 'r', encoding=encoding or 'utf-8', errors='ignore') as f:
                    content = f.read()
        except Exception as e:
            print(f"Could not read full content of {file_path}: {str(e)}")
            return {'is_obfuscated': False, 'error': str(e)}

        # Analyze the file using both approaches
        patterns = self.mapper.analyze_file(content)
        analysis = self.analyze_file_content(file_path, content)
        
        # Decode any found keys using comprehensive method
        decoded_keys = {}
        if patterns.get('encoded_strings'):
            for key in patterns['encoded_strings']:
                decoded_keys[key] = self.decoder.decode_key_comprehensive(key, all_contexts=False)
        
        # Analyze mathematical operations
        math_operations = []
        math_patterns = re.findall(r'\([^)]+\.[Hh]ash\(\)[^)]*\)', content)
        for math_expr in math_patterns:
            math_operations.append(self.math_decoder.analyze_math_expression(math_expr))
        
        # Try specific decoding methods
        specific_results = []
        specific_errors = []
        
        if "GA91UCDQYUVawLMs" in content:
            results, errors = self.specific_decoder.try_multiple_contexts(
                content, self.specific_decoder.process_input_string)
            specific_results.extend(results)
            specific_errors.extend(errors)
            process_type = "Type 1 (GA91UCDQYUVawLMs)"
        elif "EVy2D5PaA01T99Ml" in content:
            results, errors = self.specific_decoder.try_multiple_contexts(
                content, self.specific_decoder.process_input_string2)
            specific_results.extend(results)
            specific_errors.extend(errors)
            process_type = "Type 2 (EVy2D5PaA01T99Ml)"
        else:
            process_type = "Generic obfuscation"
        
        return {
            'is_obfuscated': True,
            'file_path': file_path,
            'encoding': encoding,
            'process_type': process_type,
            'patterns': patterns,
            'analysis': analysis,
            'decoded_keys': decoded_keys,
            'math_operations': math_operations,
            'specific_results': specific_results,
            'specific_errors': specific_errors,
            'obfuscation_density': self.calculate_obfuscation_density(content)
        }
        
    def calculate_obfuscation_density(self, content):
        """Calculate how heavily obfuscated the content is"""
        lines = content.split('\n')
        obfuscated_lines = 0
        
        for line in lines:
            # Count lines with obfuscated patterns
            if (len(re.findall(r'[A-Za-z]{15,}', line)) > 0 or
                len(re.findall(r'"[A-Z]{20,}"', line)) > 0):
                obfuscated_lines += 1
                
        return obfuscated_lines / len(lines) if lines else 0
    
    def process_directory(self, directory_path):
        """Process entire directory of obfuscated files"""
        results = {
            'files_processed': 0,
            'obfuscated_files': 0,
            'successful_decodes': 0,
            'total_identifiers': 0,
            'unique_patterns': set(),
            'deobfuscation_map': {}
        }
        
        for root, dirs, files in os.walk(directory_path):
            if 'decoded_results' in root or 'deobfuscation_analysis' in root:
                continue
                
            for file in files:
                if file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
                file_result = self.process_single_file(file_path)
                
                if file_result and file_result.get('is_obfuscated'):
                    results['files_processed'] += 1
                    results['obfuscated_files'] += 1
                    
                    if file_result.get('specific_results'):
                        results['successful_decodes'] += 1
                    
                    results['deobfuscation_map'][file_path] = file_result
                elif file_result:
                    results['files_processed'] += 1
                        
        return results
    
    def generate_comprehensive_report(self, results, output_path):
        """Generate comprehensive deobfuscation report"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== COMPREHENSIVE DEOBFUSCATION ANALYSIS ===\n\n")
            f.write(f"Files Processed: {results['files_processed']}\n")
            f.write(f"Obfuscated Files: {results['obfuscated_files']}\n")
            f.write(f"Successful Decodes: {results['successful_decodes']}\n")
            f.write(f"Total Unique Identifiers: {results['total_identifiers']}\n\n")
            
            f.write("=== DETAILED ANALYSIS BY FILE ===\n")
            for file_path, data in results['deobfuscation_map'].items():
                f.write(f"\n{'='*80}\n")
                f.write(f"File: {file_path}\n")
                f.write(f"Process Type: {data.get('process_type', 'Unknown')}\n")
                f.write(f"Encoding: {data.get('encoding', 'Unknown')}\n")
                f.write(f"Obfuscation Density: {data.get('obfuscation_density', 0):.2%}\n")
                
                # File analysis
                if 'analysis' in data:
                    f.write(f"\nFile Analysis:\n")
                    for key, value in data['analysis'].items():
                        f.write(f"  {key}: {value}\n")
                
                # Pattern analysis
                if 'patterns' in data and data['patterns']:
                    f.write(f"\nFound Patterns:\n")
                    for pattern_type, pattern_data in data['patterns'].items():
                        if pattern_data:
                            f.write(f"  {pattern_type}: {len(pattern_data)} matches\n")
                
                # Decoded keys
                if 'decoded_keys' in data and data['decoded_keys']:
                    f.write(f"\nDecoded Keys:\n")
                    for key, decoded in data['decoded_keys'].items():
                        f.write(f"  {key[:50]}...: {len(decoded)} decodings attempted\n")
                
                # Specific results
                if 'specific_results' in data and data['specific_results']:
                    f.write(f"\nSpecific Decoding Results ({len(data['specific_results'])} successful):\n")
                    for i, (context, result) in enumerate(data['specific_results'][:3]):  # Show first 3
                        f.write(f"  Context '{context}':\n")
                        f.write(f"    Values: {len(result.get('values', []))} decoded\n")
                        f.write(f"    Result: {result.get('result', 'N/A')}\n")
                        
                        # Try to reverse the result
                        if result.get('type') == 'GA91UCDQYUVawLMs':
                            reversed_input = self.specific_decoder.reverse_process_input_string(result)
                        elif result.get('type') == 'EVy2D5PaA01T99Ml':
                            reversed_input = self.specific_decoder.reverse_process_input_string2(result)
                        else:
                            reversed_input = "Cannot reverse unknown type"
                        
                        f.write(f"    Reversed Input: {reversed_input}\n")
                
                # Errors
                if 'specific_errors' in data and data['specific_errors']:
                    f.write(f"\nErrors Encountered: {len(data['specific_errors'])}\n")
                    for context, error in data['specific_errors'][:5]:  # Show first 5 errors
                        f.write(f"  Context '{context}': {error}\n")
                
                # Math operations
                if 'math_operations' in data and data['math_operations']:
                    f.write(f"\nMathematical Operations:\n")
                    for op in data['math_operations']:
                        f.write(f"  {op['expression']} -> {op['likely_purpose']}\n")
            
            f.write(f"\n{'='*80}\n")
            f.write("=== END OF COMPREHENSIVE REPORT ===\n")

    def save_individual_results(self, results, output_dir):
        """Save individual analysis files for each processed file"""
        individual_dir = os.path.join(output_dir, 'individual_analyses')
        os.makedirs(individual_dir, exist_ok=True)
        
        for file_path, data in results['deobfuscation_map'].items():
            file_name = os.path.basename(file_path)
            output_file_path = os.path.join(individual_dir, f"{file_name}.analysis.txt")
            
            with open(output_file_path, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(f"Individual Analysis for: {file_path}\n")
                f.write(f"Process Type: {data.get('process_type', 'Unknown')}\n")
                f.write(f"File Encoding: {data.get('encoding', 'Unknown')}\n")
                f.write("="*50 + "\n\n")
                
                if data.get('specific_results'):
                    f.write(f"Successful processing attempts: {len(data['specific_results'])}\n")
                    for i, (context, output) in enumerate(data['specific_results']):
                        f.write(f"\nContext '{context}' (attempt {i+1}):\n")
                        f.write("-" * 30 + "\n")
                        f.write(f"Decoded Values: {output.get('values', [])}\n")
                        f.write(f"Decoded Vectors: {output.get('vectors', [])}\n")
                        f.write(f"Decoded Strings: {output.get('strings', [])}\n")
                        f.write(f"Result: {output.get('result', 'N/A')}\n")
                        
                        # Add reversal attempt
                        if output.get('type') == 'GA91UCDQYUVawLMs':
                            reversed_input = self.specific_decoder.reverse_process_input_string(output)
                        elif output.get('type') == 'EVy2D5PaA01T99Ml':
                            reversed_input = self.specific_decoder.reverse_process_input_string2(output)
                        else:
                            reversed_input = "Cannot reverse unknown type"
                        
                        f.write(f"Reversed Input: {reversed_input}\n")
                        f.write("\n")
                else:
                    f.write("No successful processing attempts\n")
                
                if data.get('specific_errors'):
                    f.write(f"\nErrors encountered: {len(data['specific_errors'])}\n")
                    for context, error in data['specific_errors']:
                        f.write(f"Context '{context}': {error}\n")
                
                # Add comprehensive pattern analysis
                f.write(f"\nPattern Analysis:\n")
                for pattern_type, pattern_data in data.get('patterns', {}).items():
                    if pattern_data:
                        f.write(f"  {pattern_type}: {pattern_data}\n")
                
                # Add file content analysis
                f.write(f"\nFile Content Analysis:\n")
                for key, value in data.get('analysis', {}).items():
                    f.write(f"  {key}: {value}\n")

def main():
    """Main function to run the comprehensive deobfuscator"""
    print("=== COMPREHENSIVE DEOBFUSCATION TOOL ===")
    print("This tool combines pattern analysis with specific decoding methods")
    print("for comprehensive obfuscation analysis.\n")
    
    # Get target directory
    target_directory = input("Enter the path to your obfuscated code directory: ").strip()
    
    if not os.path.exists(target_directory):
        print(f"Error: Directory '{target_directory}' does not exist.")
        return
    
    # Initialize the deobfuscator
    deobfuscator = ComprehensiveDeobfuscator()
    
    print(f"Starting comprehensive deobfuscation analysis of: {target_directory}")
    print("This may take a while for large directories...\n")
    
    # Process the directory
    try:
        results = deobfuscator.process_directory(target_directory)
        
        # Create output directories
        output_dir = os.path.join(target_directory, 'comprehensive_deobfuscation_results')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate comprehensive report
        comprehensive_report_path = os.path.join(output_dir, 'comprehensive_analysis_report.txt')
        deobfuscator.generate_comprehensive_report(results, comprehensive_report_path)
        
        # Save individual analysis files
        deobfuscator.save_individual_results(results, output_dir)
        
        # Generate summary statistics
        summary_path = os.path.join(output_dir, 'summary_statistics.txt')
        generate_summary_statistics(results, summary_path)
        
        # Print results
        print("="*60)
        print("ANALYSIS COMPLETE!")
        print("="*60)
        print(f"Files Processed: {results['files_processed']}")
        print(f"Obfuscated Files Found: {results['obfuscated_files']}")
        print(f"Successful Decodes: {results['successful_decodes']}")
        print(f"Success Rate: {(results['successful_decodes'] / max(results['obfuscated_files'], 1)) * 100:.1f}%")
        print(f"\nResults saved to: {output_dir}")
        print(f"Main report: {comprehensive_report_path}")
        print(f"Individual analyses: {os.path.join(output_dir, 'individual_analyses')}")
        print(f"Summary statistics: {summary_path}")
        
        # Show process types found
        process_types = {}
        for file_path, data in results['deobfuscation_map'].items():
            ptype = data.get('process_type', 'Unknown')
            process_types[ptype] = process_types.get(ptype, 0) + 1
        
        if process_types:
            print(f"\nObfuscation Types Found:")
            for ptype, count in process_types.items():
                print(f"  {ptype}: {count} files")
        
    except Exception as e:
        print(f"Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()

def generate_summary_statistics(results, output_path):
    """Generate summary statistics file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=== SUMMARY STATISTICS ===\n\n")
        f.write(f"Total Files Processed: {results['files_processed']}\n")
        f.write(f"Obfuscated Files Found: {results['obfuscated_files']}\n")
        f.write(f"Successful Decodes: {results['successful_decodes']}\n")
        f.write(f"Success Rate: {(results['successful_decodes'] / max(results['obfuscated_files'], 1)) * 100:.1f}%\n\n")
        
        # Process type breakdown
        process_types = {}
        obfuscation_densities = []
        
        for file_path, data in results['deobfuscation_map'].items():
            ptype = data.get('process_type', 'Unknown')
            process_types[ptype] = process_types.get(ptype, 0) + 1
            
            density = data.get('obfuscation_density', 0)
            if density > 0:
                obfuscation_densities.append(density)
        
        f.write("Process Type Breakdown:\n")
        for ptype, count in process_types.items():
            f.write(f"  {ptype}: {count} files\n")
        
        if obfuscation_densities:
            f.write(f"\nObfuscation Density Statistics:\n")
            f.write(f"  Average: {sum(obfuscation_densities) / len(obfuscation_densities):.2%}\n")
            f.write(f"  Minimum: {min(obfuscation_densities):.2%}\n")
            f.write(f"  Maximum: {max(obfuscation_densities):.2%}\n")
        
        # List successfully decoded files
        f.write(f"\nSuccessfully Decoded Files:\n")
        for file_path, data in results['deobfuscation_map'].items():
            if data.get('specific_results'):
                f.write(f"  {file_path} ({len(data['specific_results'])} contexts)\n")
        
        # List failed files
        f.write(f"\nFailed to Decode:\n")
        for file_path, data in results['deobfuscation_map'].items():
            if not data.get('specific_results'):
                f.write(f"  {file_path} (Reason: {data.get('process_type', 'Unknown pattern')})\n")

def interactive_mode():
    """Interactive mode for detailed analysis of specific files"""
    print("\n=== INTERACTIVE MODE ===")
    print("Enter a specific file path for detailed analysis, or 'quit' to exit.")
    
    deobfuscator = ComprehensiveDeobfuscator()
    
    while True:
        file_path = input("\nEnter file path (or 'quit'): ").strip()
        
        if file_path.lower() == 'quit':
            break
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
        
        print(f"\nAnalyzing: {file_path}")
        result = deobfuscator.process_single_file(file_path)
        
        if not result.get('is_obfuscated'):
            print("File does not appear to be obfuscated.")
            continue
        
        print(f"Process Type: {result.get('process_type', 'Unknown')}")
        print(f"Obfuscation Density: {result.get('obfuscation_density', 0):.2%}")
        
        if result.get('specific_results'):
            print(f"Successful decodings: {len(result['specific_results'])}")
            for i, (context, output) in enumerate(result['specific_results'][:3]):
                print(f"  Context '{context}': Result = {output.get('result', 'N/A')}")
        else:
            print("No successful decodings found.")
        
        if result.get('specific_errors'):
            print(f"Errors encountered: {len(result['specific_errors'])}")

if __name__ == "__main__":
    try:
        main()
        
        # Offer interactive mode
        while True:
            choice = input("\nWould you like to enter interactive mode for detailed file analysis? (y/n): ").strip().lower()
            if choice == 'y':
                interactive_mode()
                break
            elif choice == 'n':
                break
            else:
                print("Please enter 'y' or 'n'")
        
        print("\nThank you for using the Comprehensive Deobfuscation Tool!")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()