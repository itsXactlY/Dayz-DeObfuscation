import os
import sys
import json
import hashlib
import struct
import subprocess
import requests
import math
from pathlib import Path
from typing import Dict, List, Any, Optional
import binascii

class EnhancedPBOAnalyzer:
    def __init__(self, ollama_model: str = "llama3.1:8b", ollama_host: str = "http://localhost:11434"):
        self.ollama_model = ollama_model
        self.ollama_host = ollama_host
        self.analysis_results = {}
        self.deobfuscation_log = []
        
    def analyze_file_structure(self, file_path: str) -> Dict[str, Any]:
        """Initial file structure analysis"""
        file_info = {
            'path': file_path,
            'size': os.path.getsize(file_path),
            'hash_md5': self._get_file_hash(file_path, 'md5'),
            'hash_sha256': self._get_file_hash(file_path, 'sha256'),
            'magic_type': self._get_file_type(file_path),
            'entropy': self._calculate_entropy(file_path),
            'header_analysis': self._analyze_header(file_path),
            'strings': self._extract_strings(file_path),
            'byte_patterns': self._analyze_byte_patterns(file_path)
        }
        return file_info
    
    def _get_file_hash(self, file_path: str, algorithm: str) -> str:
        """Calculate file hash"""
        hash_func = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    def _get_file_type(self, file_path: str) -> str:
        """Detect file type"""
        try:
            # Try to identify basic file signatures
            with open(file_path, 'rb') as f:
                header = f.read(16)
            
            if header.startswith(b'PK'):
                return "ZIP/Archive"
            elif header.startswith(b'\x7fELF'):
                return "ELF executable"
            elif header.startswith(b'MZ'):
                return "PE executable"
            elif b'sreV' in header or b'Vers' in header:
                return "Potential PBO file"
            else:
                return "Unknown binary"
        except:
            return "Unknown"
    
    def _calculate_entropy(self, file_path: str) -> float:
        """Calculate Shannon entropy of the file"""
        with open(file_path, 'rb') as f:
            data = f.read()
        
        if not data:
            return 0
        
        # Count frequency of each byte
        byte_counts = [0] * 256
        for byte in data:
            byte_counts[byte] += 1
        
        # Calculate entropy
        entropy = 0
        data_len = len(data)
        for count in byte_counts:
            if count > 0:
                p = count / data_len
                entropy -= p * math.log2(p)
        
        return entropy
    
    def _analyze_header(self, file_path: str, header_size: int = 512) -> Dict[str, Any]:
        """Analyze file header for PBO-specific structures"""
        with open(file_path, 'rb') as f:
            header = f.read(min(header_size, os.path.getsize(file_path)))
        
        if not header:
            return {'hex_dump': '', 'potential_signatures': [], 'null_bytes': 0, 'printable_ratio': 0}
        
        analysis = {
            'hex_dump': binascii.hexlify(header[:64]).decode(),
            'potential_signatures': [],
            'null_bytes': header.count(b'\x00'),
            'printable_ratio': sum(1 for b in header if 32 <= b <= 126) / len(header) if header else 0
        }
        
        # Look for common PBO signatures
        pbo_signatures = [b'sreV', b'Vers', b'\x00\x00\x00\x00']
        for sig in pbo_signatures:
            if sig in header:
                analysis['potential_signatures'].append(f"Found signature: {sig.hex()}")
        
        return analysis
    
    def _extract_strings(self, file_path: str, min_length: int = 4) -> List[str]:
        """Extract printable strings from file"""
        strings = []
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            chunk_size = 1024 * 1024  # 1MB chunks
            current_string = ""
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                for byte in chunk:
                    if 32 <= byte <= 126:  # Printable ASCII
                        current_string += chr(byte)
                    else:
                        if len(current_string) >= min_length:
                            strings.append(current_string)
                        current_string = ""
                
                # Limit total strings to prevent memory issues
                if len(strings) >= 100000:
                    break
        
        # Add final string if exists
        if len(current_string) >= min_length:
            strings.append(current_string)
        
        return strings[:10000]  # Limit to first 100 strings
    
    def _analyze_byte_patterns(self, file_path: str) -> Dict[str, Any]:
        """Analyze byte patterns for obfuscation detection"""
        sample_size = min(100000, os.path.getsize(file_path))  # First 100KB or entire file
        
        with open(file_path, 'rb') as f:
            data = f.read(sample_size)
        
        if not data:
            return {'most_common_bytes': [], 'repeating_sequences': [], 'xor_candidates': []}
        
        byte_freq = {}
        for byte in data:
            byte_freq[byte] = byte_freq.get(byte, 0) + 1
        
        patterns = {
            'most_common_bytes': sorted(byte_freq.items(), key=lambda x: x[1], reverse=True)[:10000],
            'repeating_sequences': self._find_repeating_sequences(data),
            'xor_candidates': self._detect_xor_patterns(data)
        }
        
        return patterns
    
    def _find_repeating_sequences(self, data: bytes, min_length: int = 4) -> List[Dict]:
        """Find repeating byte sequences"""
        if len(data) < min_length:
            return []
        
        sequences = {}
        max_sequences = 100000  # Limit to prevent memory issues
        
        for i in range(min(len(data) - min_length, max_sequences)):
            seq = data[i:i + min_length]
            if seq in sequences:
                sequences[seq] += 1
            else:
                sequences[seq] = 1
        
        return [{'sequence': binascii.hexlify(seq).decode(), 'count': count} 
                for seq, count in sequences.items() if count > 2][:1000]
    
    def _detect_xor_patterns(self, data: bytes) -> List[int]:
        """Detect potential XOR keys"""
        candidates = []
        sample_data = data[:min(100000, len(data))]  # Use smaller sample
        
        for key in range(1, 256):
            try:
                xor_result = bytes(b ^ key for b in sample_data)
                printable_count = sum(1 for b in xor_result if 32 <= b <= 126)
                printable_ratio = printable_count / len(sample_data) if sample_data else 0
                
                if printable_ratio > 0.7:  # High printable ratio
                    candidates.append(key)
            except:
                continue
        
        return candidates[:1000]
    
    def query_ollama(self, prompt: str, context: str = "") -> str:
        """Send query to Ollama for AI analysis"""
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json().get('response', 'No response from model')
            else:
                return f"Error: HTTP {response.status_code} - {response.text}"
        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to Ollama. Make sure Ollama is running on localhost:11434"
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"
    
    def ai_analyze_structure(self, file_info: Dict[str, Any]) -> str:
        """Use AI to analyze file structure"""
        context = f"""
        You are an expert reverse engineer analyzing a potentially obfuscated .pbo file.
        
        File Information:
        - Size: {file_info['size']} bytes
        - Entropy: {file_info['entropy']:.2f}
        - File type: {file_info['magic_type']}
        - Header hex: {file_info['header_analysis']['hex_dump']}
        - Printable ratio in header: {file_info['header_analysis']['printable_ratio']:.2f}
        - Null bytes in header: {file_info['header_analysis']['null_bytes']}
        - Most common bytes: {file_info['byte_patterns']['most_common_bytes'][:5]}
        - XOR key candidates: {file_info['byte_patterns']['xor_candidates']}
        - Sample strings: {file_info['strings'][:5]}
        """
        
        prompt = """
        Analyze this .pbo file data and provide:
        1. Assessment of obfuscation techniques used
        2. Recommended deobfuscation approaches
        3. Potential file structure insights
        4. Next steps for reverse engineering
        
        Focus on practical reverse engineering techniques. Be concise.
        """
        
        return self.query_ollama(prompt, context)
    
    def attempt_deobfuscation(self, file_path: str, method: str, **kwargs) -> Optional[bytes]:
        """Attempt various deobfuscation methods"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            if not data:
                return None
            
            if method == "xor":
                key = kwargs.get('key', 0)
                return bytes(b ^ key for b in data)
            
            elif method == "caesar":
                shift = kwargs.get('shift', 1)
                return bytes((b + shift) % 256 for b in data)
            
            elif method == "reverse":
                return data[::-1]
            
            elif method == "base64_decode":
                try:
                    import base64
                    return base64.b64decode(data)
                except:
                    return None
            
            elif method == "zlib_decompress":
                try:
                    import zlib
                    return zlib.decompress(data)
                except:
                    return None
            
            elif method == "simple_substitution":
                # Try simple byte substitution
                key = kwargs.get('key', 1)
                return bytes((b - key) % 256 for b in data)
        
        except Exception as e:
            print(f"Error in deobfuscation method {method}: {e}")
            return None
        
        return None
    
    def iterative_analysis(self, file_path: str, max_iterations: int = 5) -> Dict[str, Any]:
        """Perform iterative analysis and deobfuscation"""
        current_file = file_path
        temp_files = []
        
        print(f"Starting analysis of: {file_path}")
        
        for iteration in range(max_iterations):
            print(f"\n--- Iteration {iteration + 1} ---")
            
            try:
                # Analyze current file
                file_info = self.analyze_file_structure(current_file)
                print(f"File size: {file_info['size']} bytes")
                print(f"Entropy: {file_info['entropy']:.2f}")
                print(f"File type: {file_info['magic_type']}")
                
                # Get AI analysis
                ai_analysis = self.ai_analyze_structure(file_info)
                print(f"AI Analysis preview: {ai_analysis[:1500]}...")
                
                # Check if we've achieved clear text
                if self._is_cleartext(file_info):
                    print("✓ Clear text achieved!")
                    break
                
                # Try deobfuscation methods
                best_result = None
                best_entropy = file_info['entropy']
                best_method = None
                
                methods_to_try = []
                
                # Add XOR methods with detected candidates
                if file_info['byte_patterns']['xor_candidates']:
                    for xor_key in file_info['byte_patterns']['xor_candidates'][:3]:  # Limit to 3 keys
                        methods_to_try.append(('xor', {'key': xor_key}))
                
                # Add other common methods
                methods_to_try.extend([
                    ('caesar', {'shift': 1}),
                    ('caesar', {'shift': -1}),
                    ('simple_substitution', {'key': 1}),
                    ('reverse', {}),
                    ('zlib_decompress', {})
                ])
                
                for method, params in methods_to_try:
                    try:
                        result = self.attempt_deobfuscation(current_file, method, **params)
                        if result and len(result) > 0:
                            temp_path = f"temp_{method}_{iteration}_{hash(str(params)) % 1000}.bin"
                            
                            with open(temp_path, 'wb') as f:
                                f.write(result)
                            
                            temp_info = self.analyze_file_structure(temp_path)
                            
                            if temp_info['entropy'] < best_entropy:
                                best_result = temp_path
                                best_entropy = temp_info['entropy']
                                best_method = f"{method} {params}"
                                print(f"  → {method} improved entropy: {best_entropy:.2f}")
                            
                            temp_files.append(temp_path)
                    
                    except Exception as e:
                        print(f"  → {method} failed: {e}")
                        continue
                
                if best_result and best_entropy < file_info['entropy'] - 0.1:  # Require significant improvement
                    current_file = best_result
                    print(f"✓ Best method: {best_method}")
                    print(f"✓ Entropy improved to: {best_entropy:.2f}")
                else:
                    print("✗ No significant improvement found")
                    break
                    
            except Exception as e:
                print(f"Error in iteration {iteration + 1}: {e}")
                break
        
        # Final analysis
        try:
            final_info = self.analyze_file_structure(current_file)
            final_ai_analysis = self.ai_analyze_structure(final_info)
        except Exception as e:
            print(f"Error in final analysis: {e}")
            final_info = {'error': str(e)}
            final_ai_analysis = "Error in final analysis"
        
        # Cleanup temp files (keep the best result)
        for temp_file in temp_files:
            try:
                if temp_file != current_file and os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        
        return {
            'final_file': current_file,
            'final_analysis': final_info,
            'ai_conclusion': final_ai_analysis,
            'iterations': iteration + 1
        }
    
    def _is_cleartext(self, file_info: Dict[str, Any]) -> bool:
        """Determine if file appears to be cleartext"""
        entropy_threshold = 4.0
        printable_threshold = 0.6
        
        try:
            header_printable = file_info['header_analysis']['printable_ratio']
            entropy = file_info['entropy']
            
            # Check for readable strings
            has_readable_strings = len([s for s in file_info['strings'] if len(s) > 10]) > 5
            
            return (entropy < entropy_threshold and 
                   header_printable > printable_threshold and 
                   has_readable_strings)
        except:
            return False

def main():
    print("Enhanced PBO File Analyzer")
    print("=" * 50)
    
    if len(sys.argv) != 2:
        print("Usage: python pbo_analyzer.py <file_path>")
        print("Example: python pbo_analyzer.py encrypted_file.pbo")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    # Check if Ollama is accessible
    analyzer = EnhancedPBOAnalyzer()
    test_response = analyzer.query_ollama("Hello, are you working?")
    if "Error" in test_response:
        print(f"⚠️  Ollama connection issue: {test_response}")
        print("   Make sure Ollama is running: ollama serve")
        print("   And the model is available: ollama list")
    else:
        print("✓ Ollama connection successful")
    
    # Perform iterative analysis
    try:
        results = analyzer.iterative_analysis(file_path)
        
        print("\n" + "=" * 50)
        print("FINAL RESULTS")
        print("=" * 50)
        
        print(f"Processing completed in {results['iterations']} iterations")
        
        if 'error' not in results['final_analysis']:
            print(f"Final entropy: {results['final_analysis']['entropy']:.2f}")
            print(f"Final file size: {results['final_analysis']['size']} bytes")
        
        print(f"Final file location: {results['final_file']}")
        
        print("\n📋 AI Conclusion:")
        print("-" * 20)
        print(results['ai_conclusion'])
        
        # Save results to JSON
        output_file = 'analysis_results.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Full results saved to: {output_file}")
        
        # Show some final file info
        if results['final_file'] != file_path:
            print(f"\n🎯 Deobfuscated file created: {results['final_file']}")
            print("   You can now analyze this file with other tools!")
    
    except Exception as e:
        print(f"❌ Fatal error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()