import os
import re
import json
import requests
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict

# --- Configuration ---
# Directory where your extracted .txt files are located (clean reference data)
EXTRACTED_TXT_FILES_DIR = '/home/alca/Schreibtisch/test/'  # Directory containing your .txt files

# Directory where your SCRAMBLED PBO addon was extracted
SCRAMBLED_ADDON_INPUT_DIR = '/home/alca/Schreibtisch/test/AdvancedGroups_Server_latest/' 

# Final output for the RESTORED LM_Master addon
FINAL_RESTORED_ADDON_OUTPUT_DIR = 'reconstructed_addons/LM_Master' 

# Ollama Configuration
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"
MAX_CONTENT_FOR_LLM = 6000
LLM_CONFIDENCE_THRESHOLD = 6

# --- Text File Parser Class ---
class ExtractedTxtParser:
    def __init__(self, txt_files_dir: str):
        self.txt_files_dir = txt_files_dir
        self.valid_text_extensions = {
            'c', 'sqf', 'inc', 'ext', 'cpp', 'h', 'hpp', 
            'config', 'xml', 'json', 'txt', 'ini', 'cfg', 'rvmat'
        }
        
        self.all_clean_text_blocks: List[Dict] = []
        self.all_found_paths: Set[str] = set()
        self.all_script_snippets: List[str] = []
        
    def parse_all_txt_files(self):
        """Parse all .txt files to extract clean code blocks and file paths."""
        print(f"Parsing extracted .txt files from: {self.txt_files_dir}")
        
        if not os.path.exists(self.txt_files_dir):
            print(f"❌ Directory not found: {self.txt_files_dir}")
            return
            
        txt_files = [f for f in os.listdir(self.txt_files_dir) if f.endswith('.txt')]
        print(f"Found {len(txt_files)} .txt files to process")
        
        for txt_file in txt_files:
            file_path = os.path.join(self.txt_files_dir, txt_file)
            print(f"Processing: {txt_file}")
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Extract file paths from this txt file
                paths = self._extract_file_paths_from_content(content)
                self.all_found_paths.update(paths)
                
                # Extract code blocks/snippets
                code_blocks = self._extract_code_blocks_from_content(content, txt_file)
                self.all_clean_text_blocks.extend(code_blocks)
                
                # Extract script snippets for LLM context
                script_snippets = self._extract_script_snippets_from_content(content)
                self.all_script_snippets.extend(script_snippets)
                
            except Exception as e:
                print(f"Error processing {txt_file}: {e}")
        
        print(f"Extracted {len(self.all_clean_text_blocks)} code blocks, "
              f"{len(self.all_found_paths)} file paths, "
              f"and {len(self.all_script_snippets)} script snippets")
    
    def _extract_file_paths_from_content(self, content: str) -> Set[str]:
        """Extract file paths from text content."""
        paths = set()
        
        # Patterns for DayZ file paths
        path_patterns = [
            r'([a-zA-Z0-9_]+(?:[\\\/][\w\-\.]+)*\.(?:' + '|'.join(self.valid_text_extensions) + r'))',
            r'(addons[\\\/]LM_Master[\\\/][\w\-\.\\\//]+\.(?:' + '|'.join(self.valid_text_extensions) + r'))',
            r'(scripts[\\\/][\w\-\.\\\//]+\.(?:' + '|'.join(self.valid_text_extensions) + r'))',
            r'(data[\\\/][\w\-\.\\\//]+\.(?:' + '|'.join(self.valid_text_extensions) + r'))',
            r'(config[\\\/][\w\-\.\\\//]+\.(?:' + '|'.join(self.valid_text_extensions) + r'))',
            r'(LM_Master[\\\/][\w\-\.\\\//]+\.(?:' + '|'.join(self.valid_text_extensions) + r'))',
        ]
        
        for pattern in path_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if self._is_valid_path(match):
                    normalized = match.replace('\\', '/').strip('/').lower()
                    if normalized:
                        paths.add(normalized)
        
        return paths
    
    def _extract_code_blocks_from_content(self, content: str, source_file: str) -> List[Dict]:
        """Extract meaningful code blocks from content."""
        blocks = []
        
        # Split content into potential code blocks
        # Look for patterns that suggest code structure
        code_patterns = [
            r'class\s+\w+[^{]*{[^}]*}',  # Class definitions
            r'void\s+\w+\s*\([^)]*\)[^{]*{[^}]*}',  # Function definitions
            r'bool\s+\w+\s*\([^)]*\)[^{]*{[^}]*}',  # Boolean functions
            r'string\s+\w+\s*\([^)]*\)[^{]*{[^}]*}',  # String functions
            r'int\s+\w+\s*\([^)]*\)[^{]*{[^}]*}',  # Integer functions
        ]
        
        block_id = 0
        for pattern in code_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                block_content = match.group(0)
                if len(block_content) > 50 and self._is_valid_code_block(block_content):
                    block_id += 1
                    blocks.append({
                        "block_id": f"{source_file}_block_{block_id}",
                        "source_file": source_file,
                        "content": block_content.strip(),
                        "start_pos": match.start(),
                        "end_pos": match.end()
                    })
        
        return blocks
    
    def _extract_script_snippets_from_content(self, content: str) -> List[str]:
        """Extract smaller script snippets for LLM context."""
        snippets = []
        
        # Look for lines that look like DayZ/Enforce script
        lines = content.split('\n')
        current_snippet = []
        
        for line in lines:
            line = line.strip()
            if self._looks_like_script_line(line):
                current_snippet.append(line)
                if len(current_snippet) >= 10:  # Collect 10-line snippets
                    snippet_text = '\n'.join(current_snippet)
                    if len(snippet_text) > 100:
                        snippets.append(snippet_text)
                    current_snippet = current_snippet[5:]  # Overlap by 5 lines
        
        return snippets[:50]  # Limit to 50 snippets to avoid overwhelming LLM
    
    def _is_valid_path(self, path: str) -> bool:
        """Validate if a string looks like a valid file path."""
        if not path or len(path) < 5 or len(path) > 255:
            return False
        if '.' not in path:
            return False
        
        # Check for invalid characters
        invalid_chars = ['\x00', '\n', '\r', '\t', '<', '>', '|', '"', ':', '*', '?', '#']
        if any(char in path for char in invalid_chars):
            return False
        
        return True
    
    def _is_valid_code_block(self, block: str) -> bool:
        """Validate if a text block looks like valid code."""
        if not block or len(block) < 20:
            return False
        
        # Check for code-like patterns
        code_indicators = [
            r'class\s+\w+',
            r'void\s+\w+\s*\(',
            r'bool\s+\w+\s*\(',
            r'string\s+\w+\s*\(',
            r'int\s+\w+\s*\(',
            r'if\s*\(',
            r'for\s*\(',
            r'while\s*\(',
            r'return\s+',
            r'#include',
            r'#define'
        ]
        
        score = sum(1 for pattern in code_indicators if re.search(pattern, block, re.IGNORECASE))
        return score >= 2
    
    def _looks_like_script_line(self, line: str) -> bool:
        """Check if a line looks like it belongs to a script."""
        if not line or len(line) < 10:
            return False
        
        script_patterns = [
            r'^\s*(class|void|bool|string|int|float)\s+\w+',
            r'^\s*(if|for|while|switch)\s*\(',
            r'^\s*return\s+',
            r'^\s*#(include|define)',
            r'^\s*\w+\s*=\s*',
            r'^\s*\w+\.\w+\s*\(',
            r'^\s*Print\s*\(',
            r'^\s*GetGame\(\)',
        ]
        
        return any(re.search(pattern, line, re.IGNORECASE) for pattern in script_patterns)

    def get_clean_reference_snippets(self, num_snippets: int = 5, max_snippet_len: int = 500) -> str:
        """Get clean code snippets for LLM context."""
        snippets = []
        used_snippets = set()
        
        # First try code blocks
        for block in self.all_clean_text_blocks[:num_snippets * 2]:
            content = block['content']
            if len(content) > 100:
                snippet = content[:max_snippet_len].strip()
                if snippet and snippet not in used_snippets:
                    snippets.append(f"// --- Clean Code Block from {block['source_file']} ---\n{snippet}\n")
                    used_snippets.add(snippet)
                    if len(snippets) >= num_snippets:
                        break
        
        # Fill remaining with script snippets if needed
        if len(snippets) < num_snippets:
            for script_snippet in self.all_script_snippets:
                if len(script_snippet) <= max_snippet_len and script_snippet not in used_snippets:
                    snippets.append(f"// --- Clean Script Snippet ---\n{script_snippet}\n")
                    used_snippets.add(script_snippet)
                    if len(snippets) >= num_snippets:
                        break
        
        return "\n".join(snippets)
    
    def get_clean_path_examples(self, num_examples: int = 10) -> str:
        """Get clean file path examples for LLM context."""
        paths = sorted(list(self.all_found_paths))[:num_examples]
        return "\n".join(paths)

# --- LLM Reconstruction Class ---
class DayZLLMReconstructor:
    def __init__(self, txt_parser: ExtractedTxtParser, scrambled_addon_input_dir: str, final_output_base_dir: str):
        self.txt_parser = txt_parser
        self.scrambled_addon_input_dir = scrambled_addon_input_dir
        self.final_output_base_dir = final_output_base_dir
        os.makedirs(self.final_output_base_dir, exist_ok=True)
        
        self.scrambled_addon_files: Dict[str, str] = {}
        self.restored_lm_master_files: Dict[str, Dict[str, Any]] = {}
        
        self._load_scrambled_addon_files()
    
    def _load_scrambled_addon_files(self):
        """Load scrambled addon files for processing."""
        print(f"Loading scrambled addon files from: {self.scrambled_addon_input_dir}")
        
        if not os.path.exists(self.scrambled_addon_input_dir):
            print(f"❌ Scrambled addon input directory not found: {self.scrambled_addon_input_dir}")
            return
        
        text_extensions = self.txt_parser.valid_text_extensions
        
        for root, _, files in os.walk(self.scrambled_addon_input_dir):
            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower().lstrip('.')
                if ext not in text_extensions:
                    continue
                
                full_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(full_path, self.scrambled_addon_input_dir)
                
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        self.scrambled_addon_files[relative_path.replace('\\', '/')] = f.read()
                except Exception as e:
                    print(f"Error reading scrambled file {relative_path}: {e}")
        
        print(f"Loaded {len(self.scrambled_addon_files)} scrambled text files.")
    
    def _call_ollama(self, prompt: str, system_message: str = "", file_id: str = "N/A") -> Optional[Dict]:
        """Call Ollama API for LLM processing."""
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 16384
            },
            "format": "json"
        }
        if system_message:
            payload["system"] = system_message
        
        try:
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=240)
            response.raise_for_status()
            result = response.json()
            
            if "response" in result:
                try:
                    # Try to extract JSON from code blocks first
                    json_str_match = re.search(r'```json\n(.*?)\n```', result["response"], re.DOTALL)
                    if json_str_match:
                        json_str = json_str_match.group(1)
                    else:
                        # Try to find JSON object in the response
                        json_match = re.search(r'\{.*\}', result["response"], re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                        else:
                            json_str = result["response"]
                    
                    parsed_json = json.loads(json_str)
                    
                    # Debug: Print the parsed JSON structure
                    print(f"   📊 LLM Response structure for {file_id}: {list(parsed_json.keys()) if isinstance(parsed_json, dict) else type(parsed_json)}")
                    
                    return parsed_json
                    
                except json.JSONDecodeError as e:
                    print(f"   ❌ LLM returned invalid JSON for {file_id}: {e}")
                    print(f"   Raw response: {result['response'][:200]}...")
                    return None
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error calling Ollama API for {file_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error during LLM call for {file_id}: {e}")
            return None

    def restore_scrambled_addon(self):
        """Main function to restore scrambled addon using LLM."""
        print("\n--- Phase: LLM-Powered Scrambled Addon Restoration ---")
        
        total_files = len(self.scrambled_addon_files)
        if total_files == 0:
            print("No scrambled text files found to process.")
            return
        
        processed_count = 0
        clean_code_snippets = self.txt_parser.get_clean_reference_snippets(num_snippets=5, max_snippet_len=800)
        clean_path_examples = self.txt_parser.get_clean_path_examples(num_examples=10)
        
        for scrambled_relative_path, scrambled_content in self.scrambled_addon_files.items():
            processed_count += 1
            print(f"[{processed_count}/{total_files}] Processing: {scrambled_relative_path}")
            
            if len(scrambled_content) < 50:
                print(f"   Skipping very small file (len: {len(scrambled_content)}).")
                continue
            
            # Construct LLM prompt
            system_msg = (
                "You are an expert DayZ Enforce Script reverse engineer and de-obfuscator. "
                "Analyze scrambled DayZ addon script content using clean reference examples. "
                "Infer original paths, de-obfuscate names, and restore clean code. "
                "Output MUST be valid JSON."
            )
            
            prompt = self._build_restoration_prompt(
                scrambled_relative_path, 
                scrambled_content, 
                clean_code_snippets, 
                clean_path_examples
            )
            
            llm_response = self._call_ollama(prompt, system_msg, file_id=scrambled_relative_path)
            
            if self._process_llm_response(llm_response, scrambled_relative_path, scrambled_content):
                print(f"   ✓ RESTORED {scrambled_relative_path}")
            else:
                print(f"   ✗ Failed to restore {scrambled_relative_path}")
        
        print(f"\nRestoration complete. Identified {len(self.restored_lm_master_files)} LM_Master files.")
        self._save_restored_addon()
    
    def _build_restoration_prompt(self, scrambled_path: str, scrambled_content: str, 
                                clean_snippets: str, clean_paths: str) -> str:
        """Build the LLM prompt for file restoration."""
        return (
            f"Analyze this scrambled DayZ Enforce Script file: '{scrambled_path}'\n\n"
            f"**Scrambled Content:**\n```enforce\n{scrambled_content[:MAX_CONTENT_FOR_LLM]}\n```\n\n"
            f"**Clean Reference Code Examples:**\n```enforce\n{clean_snippets}\n```\n\n"
            f"**Clean File Path Examples:**\n```\n{clean_paths}\n```\n\n"
            f"Tasks:\n"
            f"1. Determine if this is an Enforce Script belonging to 'LM_Master' addon\n"
            f"2. Infer the original clean file path (e.g., 'addons/LM_Master/scripts/...')\n"
            f"3. De-obfuscate scrambled names (classes, functions, variables)\n"
            f"4. Provide fully restored and beautified code\n"
            f"5. Rate confidence (1-10)\n\n"
            f"Output JSON format:\n"
            f"{{\n"
            f'  "is_enforce_script": boolean,\n'
            f'  "is_lm_master_addon": boolean,\n'
            f'  "inferred_clean_path": "string",\n'
            f'  "deobfuscations": [{{\n'
            f'    "obfuscated_name": "string",\n'
            f'    "suggested_name": "string",\n'
            f'    "type": "class|function|variable",\n'
            f'    "inference_reason": "string"\n'
            f'  }}],\n'
            f'  "restored_content": "string",\n'
            f'  "confidence": number,\n'
            f'  "reasoning": "string"\n'
            f"}}"
        )
    
    def _process_llm_response(self, llm_response: Optional[Dict], scrambled_path: str, 
                            scrambled_content: str) -> bool:
        """Process LLM response and store results."""
        if not llm_response or not isinstance(llm_response, dict):
            return False
        
        is_enforce_script = llm_response.get("is_enforce_script", False)
        is_lm_master_addon = llm_response.get("is_lm_master_addon", False)
        inferred_clean_path = llm_response.get("inferred_clean_path")
        restored_content = llm_response.get("restored_content")
        confidence = llm_response.get("confidence", 0)
        deobfuscations = llm_response.get("deobfuscations", [])
        
        # Fix: Handle case where restored_content might be a dict or other type
        if isinstance(restored_content, dict):
            print(f"   ⚠ Warning: restored_content is dict for {scrambled_path}, converting to string")
            restored_content = json.dumps(restored_content, indent=2)
        elif not isinstance(restored_content, str):
            print(f"   ⚠ Warning: restored_content is {type(restored_content)} for {scrambled_path}, converting to string")
            restored_content = str(restored_content) if restored_content is not None else ""
        
        # Additional validation
        if not restored_content or len(restored_content.strip()) < 10:
            print(f"   ✗ Invalid or empty restored_content for {scrambled_path}")
            return False
        
        if not (is_enforce_script and is_lm_master_addon and inferred_clean_path 
                and restored_content and confidence >= LLM_CONFIDENCE_THRESHOLD):
            print(f"   ✗ LLM validation failed for {scrambled_path}: script={is_enforce_script}, lm_master={is_lm_master_addon}, path={bool(inferred_clean_path)}, conf={confidence}")
            return False
        
        # Normalize and validate path
        inferred_clean_path = self._normalize_inferred_path(inferred_clean_path)
        
        # Add deobfuscation comments
        try:
            final_content = self._add_deobfuscation_comments(restored_content, deobfuscations)
        except Exception as e:
            print(f"   ⚠ Error adding deobfuscation comments for {scrambled_path}: {e}")
            final_content = f"// LLM Restoration Error: {e}\n\n{restored_content}"
        
        # Store result (prefer higher confidence if path collision)
        current_file = self.restored_lm_master_files.get(inferred_clean_path)
        if not current_file or confidence > current_file.get("confidence", 0):
            self.restored_lm_master_files[inferred_clean_path] = {
                "content": final_content,
                "original_scrambled_path": scrambled_path,
                "deobfuscations": deobfuscations,
                "confidence": confidence,
                "reasoning": llm_response.get("reasoning", "")
            }
        
        return True

    def _normalize_inferred_path(self, path: str) -> str:
        """Normalize and correct inferred file paths."""
        path = path.replace('\\', '/').strip('/')
        
        if not path.lower().startswith("addons/lm_master/"):
            filename = os.path.basename(path)
            ext = os.path.splitext(filename)[1].lower()
            
            if ext == ".c":
                path = f"addons/LM_Master/scripts/{filename}"
            elif ext in [".cpp", ".h", ".hpp"]:
                path = f"addons/LM_Master/config/{filename}"
            elif ext in [".json", ".xml", ".txt"]:
                path = f"addons/LM_Master/data/{filename}"
            else:
                path = f"addons/LM_Master/misc/{filename}"
        
        return path
    
    def _add_deobfuscation_comments(self, content: str, deobfuscations: List[Dict]) -> str:
        """Add deobfuscation summary to restored content."""
        # Ensure content is a string
        if not isinstance(content, str):
            raise TypeError(f"Content must be string, got {type(content)}")
        
        if not deobfuscations:
            return content
        
        header = "// --- LLM De-obfuscation Summary ---\n"
        
        # Handle case where deobfuscations might not be a list
        if not isinstance(deobfuscations, list):
            print(f"   ⚠ Warning: deobfuscations is not a list, got {type(deobfuscations)}")
            deobfuscations = []
        
        for deobf in deobfuscations:
            if not isinstance(deobf, dict):
                print(f"   ⚠ Warning: deobfuscation item is not a dict, skipping")
                continue
                
            obf_name = deobf.get("obfuscated_name", "N/A")
            sugg_name = deobf.get("suggested_name", "N/A")
            deobf_type = deobf.get("type", "N/A")
            reason = deobf.get("inference_reason", "No reason")
            
            if obf_name and sugg_name and obf_name != sugg_name:
                header += f"// {deobf_type.upper()}: {obf_name} -> {sugg_name} (Reason: {reason})\n"
        
        header += "// -------------------------------------\n\n"
        
        llm_note = "// This file was restored by LLM. Manual review recommended.\n\n"
        return llm_note + header + content
    
    def _save_restored_addon(self):
        """Save all restored files to output directory."""
        print(f"\n--- Saving Restored LM_Master Addon to {self.final_output_base_dir} ---")
        
        saved_count = 0
        for inferred_path, file_data in self.restored_lm_master_files.items():
            try:
                full_output_path = os.path.join(self.final_output_base_dir, inferred_path)
                os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
                
                with open(full_output_path, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(file_data["content"])
                
                saved_count += 1
                print(f"Saved: {inferred_path} (confidence: {file_data['confidence']})")
                
            except Exception as e:
                print(f"Error saving {inferred_path}: {e}")
        
        print(f"\n✓ Successfully saved {saved_count} restored files")

# --- Main Function ---
def main():
    print(f"{'='*80}")
    print("DayZ LM_Master Addon Restoration from Extracted Text Files")
    print(f"{'='*80}\n")
    
    # Phase 1: Parse extracted .txt files
    print("Phase 1: Parsing extracted .txt files for clean reference data")
    txt_parser = ExtractedTxtParser(EXTRACTED_TXT_FILES_DIR)
    txt_parser.parse_all_txt_files()
    
    if not txt_parser.all_clean_text_blocks and not txt_parser.all_script_snippets:
        print("❌ No clean reference data found in .txt files. Check directory path.")
        return
    
    # Phase 2: LLM restoration
    print("\nPhase 2: LLM-powered restoration of scrambled addon")
    reconstructor = DayZLLMReconstructor(
        txt_parser=txt_parser,
        scrambled_addon_input_dir=SCRAMBLED_ADDON_INPUT_DIR,
        final_output_base_dir=FINAL_RESTORED_ADDON_OUTPUT_DIR
    )
    reconstructor.restore_scrambled_addon()
    
    print(f"\n{'='*80}")
    print("PROCESS COMPLETE")
    print(f"Restored files are in: {os.path.abspath(FINAL_RESTORED_ADDON_OUTPUT_DIR)}")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()