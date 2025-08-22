#!/usr/bin/env python3
"""
Advanced ML Code Deobfuscator with Ollama Integration
Analyzes all file types and uses LLM to intelligently deobfuscate code
"""

import os
import re
import json
import asyncio
import aiohttp
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import pickle
import time

class OllamaDeobfuscator:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "lazarevtill/Seed-Coder-8B-Base:latest"):
        self.ollama_url = ollama_url
        self.model = model
        self.cache_file = Path("deobfuscation_cache.pkl")
        self.cache = self.load_cache()
        self.session = None
        
    def load_cache(self) -> Dict[str, Any]:
        """Load previous deobfuscation results to avoid re-processing"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
        return {"mappings": {}, "file_hashes": {}}
    
    def save_cache(self):
        """Save deobfuscation cache"""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.cache, f)
    
    def get_file_hash(self, content: str) -> str:
        """Get hash of file content to detect changes"""
        return hashlib.md5(content.encode()).hexdigest()
    
    async def init_session(self):
        """Initialize HTTP session for Ollama API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    def extract_identifiers(self, content: str) -> Set[str]:
        """Extract all potential obfuscated identifiers from any file type"""
        identifiers = set()
        
        # Different patterns for different file types
        patterns = [
            # C/C++ style identifiers
            r'\b[A-Za-z][A-Za-z0-9_]{4,}\b',
            # Function calls
            r'([A-Za-z][A-Za-z0-9_]{4,})\s*\(',
            # Class/struct names
            r'(?:class|struct|enum)\s+([A-Za-z][A-Za-z0-9_]{4,})',
            # Variable declarations
            r'(?:int|float|bool|string|ref|auto)\s+([A-Za-z][A-Za-z0-9_]{4,})',
            # Method calls
            r'\.([A-Za-z][A-Za-z0-9_]{4,})\s*\(',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if isinstance(matches[0] if matches else None, tuple):
                identifiers.update(match[0] if isinstance(match, tuple) else match for match in matches)
            else:
                identifiers.update(matches)
        
        # Filter out common English words and known API calls
        common_words = {
            'return', 'public', 'private', 'static', 'const', 'class', 'struct',
            'include', 'define', 'ifdef', 'endif', 'namespace', 'using',
            'IsMultiplayer', 'IsClient', 'IsServer', 'GetMission', 'Cast'
        }
        
        # Only keep identifiers that look obfuscated (mixed case, long, random-looking)
        obfuscated = set()
        for identifier in identifiers:
            if (len(identifier) > 5 and 
                identifier not in common_words and
                self.looks_obfuscated(identifier)):
                obfuscated.add(identifier)
        
        return obfuscated
    
    def looks_obfuscated(self, identifier: str) -> bool:
        """Determine if an identifier looks obfuscated"""
        # Check for patterns that indicate obfuscation
        indicators = [
            len(identifier) > 10,  # Very long names
            sum(1 for c in identifier if c.isupper()) > len(identifier) * 0.3,  # Many uppercase
            sum(1 for c in identifier if c.islower()) > len(identifier) * 0.3,  # Mixed case
            not any(word in identifier.lower() for word in ['get', 'set', 'is', 'has', 'can', 'should']),  # No common prefixes
            len(set(identifier)) > len(identifier) * 0.6,  # High character diversity
        ]
        
        return sum(indicators) >= 3
    
    async def analyze_with_ollama(self, code_snippet: str, identifiers: List[str]) -> Dict[str, str]:
        """Use Ollama to analyze code and suggest meaningful names"""
        await self.init_session()
        
        # Create a focused prompt for the LLM
        prompt = f"""You are a code deobfuscator specializing in DayZ mod code. Analyze this code snippet and suggest meaningful names for the obfuscated identifiers.

Code snippet:
{code_snippet[:1000]}  # Limit snippet size

Obfuscated identifiers to rename:
{', '.join(identifiers[:10])}  # Limit number of identifiers per request

Based on the code context, usage patterns, and DayZ modding conventions, suggest meaningful names for each obfuscated identifier. 

Respond in JSON format:
{{
    "obfuscated_name1": "meaningful_name1",
    "obfuscated_name2": "meaningful_name2"
}}

Consider:
- DayZ API patterns (IsMultiplayer, IsClient, IsServer, GetMission, Cast)
- Variable usage context (if conditions, return values, method calls)
- Common programming patterns (managers, handlers, controllers, configs)
- Keep names concise but descriptive
"""

        try:
            async with self.session.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temperature for more consistent results
                        "top_p": 0.9,
                        "num_predict": 200
                    }
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    response_text = result.get('response', '')
                    
                    # Try to extract JSON from response
                    try:
                        # Find JSON in the response
                        json_start = response_text.find('{')
                        json_end = response_text.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = response_text[json_start:json_end]
                            mappings = json.loads(json_str)
                            return mappings
                    except json.JSONDecodeError:
                        pass
                    
                    # Fallback: parse line by line
                    return self.parse_llm_response(response_text, identifiers)
                
        except Exception as e:
            print(f"Ollama API error: {e}")
        
        return {}
    
    def parse_llm_response(self, response: str, identifiers: List[str]) -> Dict[str, str]:
        """Parse LLM response when JSON parsing fails"""
        mappings = {}
        lines = response.split('\n')
        
        for line in lines:
            for identifier in identifiers:
                # Look for patterns like "identifier -> new_name" or "identifier: new_name"
                patterns = [
                    rf'{re.escape(identifier)}\s*[-:>]+\s*([a-zA-Z_][a-zA-Z0-9_]*)',
                    rf'"{re.escape(identifier)}"\s*:\s*"([a-zA-Z_][a-zA-Z0-9_]*)"'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        mappings[identifier] = match.group(1)
                        break
        
        return mappings
    
    def create_fallback_mapping(self, identifiers: List[str]) -> Dict[str, str]:
        """Create fallback mappings when Ollama is unavailable"""
        mappings = {}
        categories = {
            'Manager': ['Mgr', 'Manager', 'Handler'],
            'Config': ['Cfg', 'Config', 'Settings'],
            'Player': ['Plr', 'Player', 'Character'],
            'Item': ['Itm', 'Item', 'Object'],
            'System': ['Sys', 'System', 'Service'],
            'Data': ['Data', 'Info', 'Record'],
            'Utils': ['Util', 'Helper', 'Tools']
        }
        
        counter = defaultdict(int)
        
        for identifier in identifiers:
            # Simple heuristic-based naming
            if 'config' in identifier.lower() or 'cfg' in identifier.lower():
                base = 'Config'
            elif 'player' in identifier.lower() or 'plr' in identifier.lower():
                base = 'Player'
            elif 'manager' in identifier.lower() or 'mgr' in identifier.lower():
                base = 'Manager'
            elif 'system' in identifier.lower() or 'sys' in identifier.lower():
                base = 'System'
            elif len(identifier) > 15:
                base = 'ComplexObject'
            else:
                base = 'Object'
            
            counter[base] += 1
            mappings[identifier] = f"{base}{counter[base]}" if counter[base] > 1 else base
        
        return mappings
    
    async def deobfuscate_content(self, content: str, file_path: Path) -> Tuple[str, Dict[str, str]]:
        """Deobfuscate content of any file type"""
        content_hash = self.get_file_hash(content)
        
        # Check cache first
        if str(file_path) in self.cache.get("file_hashes", {}):
            if self.cache["file_hashes"][str(file_path)] == content_hash:
                cached_mappings = self.cache.get("mappings", {}).get(str(file_path), {})
                if cached_mappings:
                    print(f"Using cached mappings for {file_path}")
                    return self.apply_mappings(content, cached_mappings), cached_mappings
        
        # Extract obfuscated identifiers
        identifiers = list(self.extract_identifiers(content))
        
        if not identifiers:
            return content, {}
        
        print(f"Found {len(identifiers)} obfuscated identifiers in {file_path}")
        
        all_mappings = {}
        
        # Process identifiers in batches to avoid overwhelming the LLM
        batch_size = 10
        for i in range(0, len(identifiers), batch_size):
            batch = identifiers[i:i + batch_size]
            
            # Get relevant code context for this batch
            context = self.get_code_context(content, batch)
            
            try:
                # Try Ollama first
                batch_mappings = await self.analyze_with_ollama(context, batch)
                
                # Fallback for unmapped identifiers
                for identifier in batch:
                    if identifier not in batch_mappings:
                        fallback_mappings = self.create_fallback_mapping([identifier])
                        batch_mappings.update(fallback_mappings)
                
                all_mappings.update(batch_mappings)
                
            except Exception as e:
                print(f"Error processing batch: {e}")
                # Use fallback for entire batch
                fallback_mappings = self.create_fallback_mapping(batch)
                all_mappings.update(fallback_mappings)
            
            # Small delay to avoid overwhelming the API
            await asyncio.sleep(0.5)
        
        # Cache results
        if str(file_path) not in self.cache["mappings"]:
            self.cache["mappings"][str(file_path)] = {}
        self.cache["mappings"][str(file_path)].update(all_mappings)
        self.cache["file_hashes"][str(file_path)] = content_hash
        
        # Apply mappings
        deobfuscated_content = self.apply_mappings(content, all_mappings)
        
        return deobfuscated_content, all_mappings
    
    def get_code_context(self, content: str, identifiers: List[str]) -> str:
        """Extract relevant code context around identifiers"""
        lines = content.split('\n')
        context_lines = set()
        
        for identifier in identifiers:
            for i, line in enumerate(lines):
                if identifier in line:
                    # Include surrounding lines for context
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context_lines.update(range(start, end))
        
        # Get unique lines and sort them
        sorted_lines = sorted(context_lines)
        context = '\n'.join(lines[i] for i in sorted_lines)
        
        # Limit context size
        return context[:2000]
    
    def apply_mappings(self, content: str, mappings: Dict[str, str]) -> str:
        """Apply identifier mappings to content"""
        result = content
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_mappings = sorted(mappings.items(), key=lambda x: len(x[0]), reverse=True)
        
        for obfuscated, meaningful in sorted_mappings:
            if meaningful and meaningful != obfuscated:
                # Use word boundaries to avoid partial matches
                pattern = rf'\b{re.escape(obfuscated)}\b'
                result = re.sub(pattern, meaningful, result)
        
        return result
    
    async def process_file(self, file_path: Path, output_dir: Path, show_progress: bool = True) -> Tuple[int, bool]:
        """Process a single file"""
        try:
            # Try different encodings
            content = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        content = f.read()
                    break
                except:
                    continue
            
            if content is None:
                print(f"Could not read {file_path}")
                return 0, False
            
            # Skip empty files
            if len(content.strip()) < 10:
                return 0, False
            
            # Skip binary files (basic check)
            if '\x00' in content[:1000]:
                if show_progress:
                    print(f"Skipping binary file: {file_path}")
                return 0, False
            
            if show_progress:
                print(f"Processing: {file_path}")
            
            # Deobfuscate
            deobfuscated_content, mappings = await self.deobfuscate_content(content, file_path)
            
            # Create output file path
            relative_path = file_path.relative_to(file_path.parts[0] if len(file_path.parts) > 1 else file_path.parent)
            output_file = output_dir / relative_path
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write deobfuscated content
            with open(output_file, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(deobfuscated_content)
            
            # Write mapping report
            if mappings:
                mapping_file = output_file.with_suffix(output_file.suffix + '.mappings.json')
                with open(mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(mappings, f, indent=2)
            
            return len(mappings), True
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return 0, False
    
    async def process_directory(self, input_dir: Path, output_dir: Path, max_workers: int = 4):
        """Process all files in directory"""
        # Find all files (any extension)
        all_files = []
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                file_path = Path(root) / file
                # Skip very large files (>10MB) to avoid memory issues
                try:
                    if file_path.stat().st_size < 10 * 1024 * 1024:
                        all_files.append(file_path)
                except:
                    pass
        
        print(f"Found {len(all_files)} files to process")
        
        # Process files with limited concurrency
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_with_semaphore(file_path):
            async with semaphore:
                return await self.process_file(file_path, output_dir)
        
        # Process all files
        tasks = [process_with_semaphore(file_path) for file_path in all_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate statistics
        total_mappings = 0
        successful_files = 0
        
        for result in results:
            if not isinstance(result, Exception):
                mappings_count, success = result
                if success:
                    successful_files += 1
                    total_mappings += mappings_count
        
        print(f"\nProcessing complete!")
        print(f"Files processed: {successful_files}/{len(all_files)}")
        print(f"Total identifiers deobfuscated: {total_mappings}")
        
        # Save cache
        self.save_cache()

async def main():
    parser = argparse.ArgumentParser(description='Advanced ML Code Deobfuscator with Ollama')
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('-o', '--output', required=True, help='Output directory')
    parser.add_argument('--ollama-url', default='http://localhost:11434', help='Ollama API URL')
    parser.add_argument('--model', default='codellama:7b', help='Ollama model to use')
    parser.add_argument('--workers', type=int, default=4, help='Number of concurrent workers')
    parser.add_argument('--clear-cache', action='store_true', help='Clear deobfuscation cache')
    
    args = parser.parse_args()
    
    # Initialize deobfuscator
    deobfuscator = OllamaDeobfuscator(args.ollama_url, args.model)
    
    if args.clear_cache:
        deobfuscator.cache = {"mappings": {}, "file_hashes": {}}
        print("Cache cleared")
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"Error: {input_path} does not exist")
        return 1
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        if input_path.is_file():
            # Single file
            mappings_count, success = await deobfuscator.process_file(input_path, output_path)
            if success:
                print(f"Deobfuscated {mappings_count} identifiers")
            else:
                print("Failed to process file")
        else:
            # Directory
            await deobfuscator.process_directory(input_path, output_path, args.workers)
        
    finally:
        await deobfuscator.close_session()

if __name__ == "__main__":
    asyncio.run(main())