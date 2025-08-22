import os
import shutil
import subprocess
import json
import logging
import re
import time
from datetime import datetime
import difflib # For generating diffs

# --- Configuration ---
OLLAMA_MODEL = "llama3.1:8b"  # Or "codelLama", "mixtral", etc.
OLLAMA_API_URL = "http://localhost:11434/api/generate" # Default Ollama API endpoint
LOG_FILE = "deobfuscator_log.txt"
MAX_DEOBF_ITERATIONS = 5 # How many times to try and re-analyze/deobfuscate
PROOF_REPORT_FILE = "deobfuscation_proof_report.txt"
MANUAL_SCRIPT_FILE = "manual_deobfuscation_script.py"

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def ollama_query(prompt, model=OLLAMA_MODEL, api_url=OLLAMA_API_URL):
    """Sends a query to the Ollama API and returns the response content."""
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": -1 # Predict until stop token or context limit
        }
    }
    logger.info(f"Sending prompt to Ollama (model: {model})...")
    try:
        import requests
        response = requests.post(api_url, headers=headers, json=data, timeout=600) # Increased timeout
        response.raise_for_status()
        result = response.json()
        logger.info("Ollama response received.")
        return result.get("response", "").strip()
    except requests.exceptions.ConnectionError as e:
        logger.critical(f"Failed to connect to Ollama API at {api_url}. Is Ollama running? Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Ollama query: {e}")
        return None

def read_file_content(filepath):
    """Reads content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read file {filepath}: {e}")
        return None

def write_file_content(filepath, content):
    """Writes content to a file."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to write file {filepath}: {e}")
        return False

def get_file_type_hint(filepath):
    """Guesses file type based on extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.sqf', '.fsm', '.c']: # .c might be used for Enforce Script files
        return "SQF (Arma Scripting Language)/Enforce Script"
    elif ext in ['.cpp', '.h']:
        return "C++ Source Code"
    elif ext in ['.txt', '.log', '.md', '.html', '.xml', '.json']:
        return "Plain Text"
    elif ext in ['.paa', '.jpg', '.png', '.tga', '.dds']:
        return "Image File (binary, likely not obfuscated)"
    elif ext in ['.p3d', '.rtm', '.ebo', '.rvmat']:
        return "Model/Animation/Material File (binary, likely not obfuscated)"
    elif ext in ['.bisign', '.bikey']:
        return "Signature/Key File (binary)"
    else:
        return "Unknown/Other"

# --- Main Deobfuscator Agent Class ---
class PBO_Deobfuscator_Agent:
    def __init__(self, extracted_content_dir, output_dir):
        if not os.path.exists(extracted_content_dir) or not os.path.isdir(extracted_content_dir):
            raise FileNotFoundError(f"Extracted content directory not found or is not a directory: {extracted_content_dir}")

        self.input_extracted_dir = os.path.abspath(extracted_content_dir)
        self.output_dir = os.path.abspath(output_dir)
        self.deobfuscated_dir = os.path.join(self.output_dir, "deobfuscated_content")
        
        self.state = {
            "current_iteration": 0,
            "files_to_process": [],
            "obfuscation_detected_this_iter": False,
            "total_obfuscation_steps": 0
        }
        self.deobfuscation_log_entries = [] # Stores all changes for reporting and manual script
        self.decryption_functions = {} # Stores named decryption function code snippets

        os.makedirs(self.deobfuscated_dir, exist_ok=True) # Ensure output directory exists
        logger.info(f"Initialized PBO Deobfuscator to work on extracted content from '{self.input_extracted_dir}'. Output to '{self.output_dir}'")

    def _scan_and_prioritize_files(self, directory):
        """Scans a directory for files, prioritizing code/script files."""
        found_files = []
        for root, _, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                relative_path = os.path.relpath(filepath, directory)
                file_type_hint = get_file_type_hint(filepath)
                if file_type_hint in ["SQF (Arma Scripting Language)/Enforce Script", "C++ Source Code", "Plain Text"]:
                    priority = 1 # High priority for code/scripts
                else:
                    priority = 2 # Lower priority for other files
                found_files.append((priority, filepath, relative_path, file_type_hint))
        
        found_files.sort(key=lambda x: x[0]) # Sort by priority
        self.state["files_to_process"] = [(fp, rp, ft) for _, fp, rp, ft in found_files]
        logger.info(f"Found {len(self.state['files_to_process'])} files to process, prioritized.")
        return len(self.state["files_to_process"]) > 0

    def _analyze_and_deobfuscate_file(self, current_filepath_in_deobf_dir, relative_path, file_type_hint):
        """
        Analyzes a single file for obfuscation and attempts to deobfuscate.
        Modifies the file in the self.deobfuscated_dir directly.
        Records changes to self.deobfuscation_log_entries.
        """
        logger.info(f"Analyzing file: {relative_path} (Type: {file_type_hint})")
        
        original_content_for_diff = read_file_content(current_filepath_in_deobf_dir)
        if original_content_for_diff is None:
            return False # Failed to read

        current_content = original_content_for_diff # Start with the current state of the file
        obfuscation_found_in_file = False

        # Max content to send to Ollama to avoid context window limits
        ollama_content = current_content[:8000] 
        if len(current_content) > 8000:
            ollama_content += "\n... [content truncated for Ollama analysis] ..."

        deobfuscation_prompt = f"""
        You are an expert reverse engineer analyzing an obfuscated game file from Bohemia Interactive (Arma/DayZ context).
        The file is part of an already extracted PBO archive.
        File Path (relative): {relative_path}
        File Type Hint: {file_type_hint} (This could be Enforce Script, similar to C++ or C#)

        Analyze the following code/text content for signs of obfuscation.
        Prioritize deobfuscation in this order:
        1.  **File Naming Obfuscation:** Does the file name ({os.path.basename(relative_path)}) seem deliberately scrambled (e.g., random characters, misleading extensions like .xyz for .sqf) given its content or common game file conventions? If so, suggest a more logical original name.
        2.  **Junk Code / Dead Code:** Identify any lines of code that perform useless computations, repetitive assignments, or operations that have no effect (e.g., `*0`).
        3.  **String/Literal Obfuscation:** Look for encrypted strings, computed strings, or patterns that construct strings at runtime. Pay close attention to patterns like `ObfuscatedClass.ObfuscatedMethod("ENCODED_STRING", KEY_OR_CONTEXT)`.
        4.  **Variable/Function/Class Renaming:** Identify highly randomized or meaningless names for classes, methods, variables, and parameters. Infer their actual meaning based on context (e.g., adjacent standard API calls like `.IsServer()`, `.GetPlayer()`, `.SetSoundVolume()`).
        5.  **Control Flow Obfuscation:** Look for complex `if/else`, `switch`, or `goto` structures that obscure the logic. (Note: automated fixing of this is hard, but identification is key).
        6.  **Other Obfuscation:** Any other unusual patterns or anti-tampering techniques.

        Provide your analysis and a step-by-step deobfuscation strategy.
        For each obfuscation type detected, provide:
        -   **Detection:** How you identified it.
        -   **Suggested Action (Python/Regex):** Concrete steps or Python-compatible regular expressions to clean or reverse the obfuscation. Be precise with regex, include capture groups if needed for replacement.
            *   For **renaming files, variables, functions, or classes**, provide `OLD_NAME -> NEW_NAME` pairs in a `renames` block. Use word boundaries (`\\b`) for variable/function renames if you were to apply them with regex.
            *   For **junk code removal**, provide the specific regex to match and remove in a `regex_remove` block.
            *   For **string deobfuscation**, if you can determine the decryption algorithm and it's simple enough for a Python function, provide the `python_decrypt_snippet` (make sure the function is named `decrypt_string` for consistency) AND a `regex_decrypt_target` that captures *only the encrypted string* in group 1.
            *   If the "string obfuscation" is actually a lookup key into a configuration, state that and suggest what the plain-text key might be, so the human can decide how to best represent it (e.g., replace `Obf.Get("KEY")` with `Config.GetValue("PlaintextKey")` or just `PlaintextKey`).

        If no significant obfuscation is detected, state "No significant obfuscation detected."

        --- FILE CONTENT ---
        {ollama_content}
        --- END FILE CONTENT ---

        Your response should be structured clearly, making it easy for an automated script to parse.
        Example for a regex suggestion (for removal):
        ```regex_remove
        ^\\s*_temp\\d+\\s*=\\s*\\d+\\s*[+\\-*\\/]\\s*\\d+;\\s*$
        ```
        Example for renaming file or variables:
        ```renames
        OLD_NAME_1 -> NEW_NAME_1
        OLD_NAME_2 -> NEW_NAME_2
        ```
        Example for string decryption (if simple) - **provide the function named `decrypt_string`:**
        ```python_decrypt_snippet
        def decrypt_string(encrypted_data):
            # Example: simple XOR with a known key (Ollama needs to figure this out)
            key = 0xAB # Placeholder, Ollama must suggest this!
            return "".join(chr(ord(c) ^ key) for c in encrypted_data)
        ```
        Example for regex to *find* the calls containing the encrypted strings for `python_decrypt_snippet` to use (capture the encrypted string in group 1):
        ```regex_decrypt_target
        (?:SfFuxbdumezDa91W\\s*\\.\\s*Ns7IynOBl5RX6MyZ\\(\\s*")([A-Za-z0-9]+)(".*?)
        ```
        (The regex_decrypt_target should capture the encrypted string in group 1. The replacement will be the *entire matched text* by the regex, with the captured group replaced by the decrypted string, potentially transforming the function call into a direct string or relevant variable name.)
        """

        ollama_response = ollama_query(deobfuscation_prompt)

        if ollama_response is None:
            logger.error(f"Failed to get Ollama response for {relative_path}. Skipping deobfuscation for this file.")
            return False

        current_content_before_this_file_pass = current_content # Snapshot before any changes in this file pass
        
        # --- Process Ollama's Suggestions ---
        logger.info(f"Ollama's analysis for {relative_path}:\n{ollama_response[:2000]}...") # Log more of the response

        # 1. File Renaming (needs to be applied to the file path on disk)
        file_renames_section_match = re.search(r'```renames\n(.*?)\n```', ollama_response, re.DOTALL)
        if file_renames_section_match:
            rename_suggestions = file_renames_section_match.group(1).strip().split('\n')
            for rename_line in rename_suggestions:
                parts = rename_line.split(' -> ')
                if len(parts) == 2:
                    old_name_frag = parts[0].strip()
                    new_name_frag = parts[1].strip()
                    
                    current_file_basename = os.path.basename(current_filepath_in_deobf_dir)
                    # Check if Ollama wants to rename THIS file based on its current base name
                    if current_file_basename == old_name_frag or \
                       (file_type_hint == "SQF (Arma Scripting Language)/Enforce Script" and old_name_frag.lower() == current_file_basename.rsplit('.', 1)[0].lower()):
                        # Try to handle .c -> .xyz type renames by mapping extension
                        new_filepath_base = os.path.join(os.path.dirname(current_filepath_in_deobf_dir), new_name_frag)
                        # Retain original extension if new_name_frag doesn't have one, or if it's just a base name suggestion
                        if '.' not in os.path.basename(new_name_frag):
                            original_ext = os.path.splitext(current_filepath_in_deobf_dir)[1]
                            new_filepath = new_filepath_base + original_ext
                        else:
                            new_filepath = new_filepath_base
                        
                        try:
                            if os.path.exists(new_filepath) and new_filepath != current_filepath_in_deobf_dir:
                                logger.warning(f"Proposed rename '{new_filepath}' already exists. Skipping to avoid overwrite.")
                                continue

                            # Record the file rename *before* executing
                            self.deobfuscation_log_entries.append({
                                "type": "file_rename",
                                "original_relative_path": relative_path,
                                "new_relative_path": os.path.relpath(new_filepath, self.deobfuscated_dir),
                                "old_name": current_file_basename,
                                "new_name": os.path.basename(new_filepath),
                                "iteration": self.state["current_iteration"]
                            })

                            os.rename(current_filepath_in_deobf_dir, new_filepath)
                            logger.info(f"Renamed file {current_file_basename} to {os.path.basename(new_filepath)}")
                            current_filepath_in_deobf_dir = new_filepath # Update path for subsequent operations
                            relative_path = os.path.relpath(new_filepath, self.deobfuscated_dir) # Update relative path for logging
                            obfuscation_found_in_file = True
                            self.state["obfuscation_detected_this_iter"] = True
                            self.state["total_obfuscation_steps"] += 1
                        except Exception as e:
                            logger.warning(f"Could not rename file {current_filepath_in_deobf_dir} to {new_filepath}: {e}")

        # 2. Junk Code Removal / Regex-based cleaning
        regex_remove_matches = re.findall(r'```regex_remove\n(.*?)\n```', ollama_response, re.DOTALL)
        for regex_str in regex_remove_matches:
            try:
                pattern = re.compile(regex_str, re.MULTILINE)
                new_content = re.sub(pattern, '', current_content) # Empty string for removal
                if new_content != current_content:
                    self.deobfuscation_log_entries.append({
                        "type": "regex_remove",
                        "relative_filepath": relative_path,
                        "pattern": regex_str,
                        "iteration": self.state["current_iteration"],
                        "original_snippet": current_content[current_content.find(re.search(pattern, current_content).group(0))-50:current_content.find(re.search(pattern, current_content).group(0))+50] if re.search(pattern, current_content) else None, # Snippet around first match
                        "modified_snippet": new_content[new_content.find(re.sub(pattern, '', current_content))-50:new_content.find(re.sub(pattern, '', current_content))+50] if re.search(pattern, current_content) else None,
                    })
                    logger.info(f"Applied regex removal pattern: '{regex_str}'")
                    current_content = new_content
                    obfuscation_found_in_file = True
                    self.state["obfuscation_detected_this_iter"] = True
                    self.state["total_obfuscation_steps"] += 1
            except re.error as e:
                logger.warning(f"Invalid regex suggested by Ollama for removal: '{regex_str}' - Error: {e}")
            except Exception as e:
                logger.warning(f"Error applying regex removal '{regex_str}': {e}")
        
        # 3. String Decryption (if simple and Python snippet provided with target regex)
        python_decrypt_snippets = re.findall(r'```python_decrypt_snippet\n(.*?)\n```', ollama_response, re.DOTALL)
        regex_decrypt_targets = re.findall(r'```regex_decrypt_target\n(.*?)\n```', ollama_response, re.DOTALL)

        decryption_applied_this_file = False
        if python_decrypt_snippets:
            logger.warning(f"Attempting to execute Python decryption snippet. This is a security risk if the snippet is malicious. Sandbox in production!")
            
            exec_globals = {}
            exec_locals = {}
            for snippet in python_decrypt_snippets:
                try:
                    # Store snippet for manual script
                    # Assume single 'decrypt_string' function for now. Could be extended for multiple.
                    match_func_name = re.search(r"def (\w+)\(", snippet)
                    func_name = match_func_name.group(1) if match_func_name else "decrypt_string"
                    self.decryption_functions[func_name] = snippet

                    exec(snippet, exec_globals, exec_locals)
                except Exception as e:
                    logger.warning(f"Error executing Python decryption snippet: {e}")
                    continue

            if 'decrypt_string' in exec_locals and callable(exec_locals['decrypt_string']):
                decrypt_func = exec_locals['decrypt_string']
                for decrypt_regex_str in regex_decrypt_targets:
                    try:
                        # Use a custom replacer function for re.sub
                        def replace_encrypted_string_with_decrypted(match):
                            encrypted_data = match.group(1) # This is the string captured by group 1
                            original_full_match = match.group(0) # The entire matched string

                            try:
                                decrypted_string = decrypt_func(encrypted_data)
                                logger.info(f"Decrypted '{encrypted_data}' to '{decrypted_string}'")
                                
                                # Record the decryption
                                self.deobfuscation_log_entries.append({
                                    "type": "string_decrypt",
                                    "relative_filepath": relative_path,
                                    "encrypted_data": encrypted_data,
                                    "decrypted_string": decrypted_string,
                                    "pattern_used": decrypt_regex_str,
                                    "original_snippet": original_full_match,
                                    "modified_snippet": f'"{decrypted_string}"', # This is what it will become
                                    "iteration": self.state["current_iteration"]
                                })
                                decryption_applied_this_file = True # Mark that a change happened

                                # Replace the original encrypted call with the plain string literal
                                return f'"{decrypted_string}"' # Surround with quotes for string literals
                            except Exception as e:
                                logger.warning(f"Error during decryption of '{encrypted_data}': {e}. Keeping original.")
                                return original_full_match # Return original full match if decryption fails

                        pattern = re.compile(decrypt_regex_str, re.MULTILINE)
                        temp_content = re.sub(pattern, replace_encrypted_string_with_decrypted, current_content) # Use temp to check if actual changes
                        
                        if temp_content != current_content:
                            logger.info(f"Applied string decryption using pattern: '{decrypt_regex_str}'.")
                            current_content = temp_content
                            obfuscation_found_in_file = True
                            self.state["obfuscation_detected_this_iter"] = True
                            self.state["total_obfuscation_steps"] += 1
                        
                    except re.error as e:
                        logger.warning(f"Invalid regex for decryption target suggested by Ollama: '{decrypt_regex_str}' - Error: {e}")
                    except Exception as e:
                        logger.warning(f"Error during string decryption process with pattern '{decrypt_regex_str}': {e}")
            else:
                logger.info(f"Decryption function 'decrypt_string' not found or not callable after snippet execution.")
        elif python_decrypt_snippets and not regex_decrypt_targets:
            logger.info("Ollama provided decryption snippet but no target regex. Cannot automate string decryption.")
        
        # 4. In-content Variable/Function/Class Renames (applied last on content)
        if file_renames_section_match: # Reuse the match if it exists
            rename_lines = file_renames_section_match.group(1).strip().split('\n')
            for line in rename_lines:
                try:
                    old_name, new_name = map(str.strip, line.split(' -> '))
                    # Skip if it was handled as a file rename (to avoid double-processing)
                    current_file_basename = os.path.basename(current_filepath_in_deobf_dir)
                    if current_file_basename == old_name or \
                       (file_type_hint == "SQF (Arma Scripting Language)/Enforce Script" and old_name.lower() == current_file_basename.rsplit('.', 1)[0].lower()):
                        continue 

                    # Use word boundaries for precise replacement of identifiers
                    pattern = r'\b' + re.escape(old_name) + r'\b'
                    new_content = re.sub(pattern, new_name, current_content)
                    if new_content != current_content:
                        # Record the content rename
                        self.deobfuscation_log_entries.append({
                            "type": "content_rename",
                            "relative_filepath": relative_path,
                            "old_name": old_name,
                            "new_name": new_name,
                            "pattern": pattern.pattern, # Store the regex used for renaming
                            "iteration": self.state["current_iteration"],
                            "original_snippet": current_content[current_content.find(re.search(pattern, current_content).group(0))-50:current_content.find(re.search(pattern, current_content).group(0))+50] if re.search(pattern, current_content) else None, # Snippet around first match
                            "modified_snippet": new_content[new_content.find(re.sub(pattern, new_name, current_content))-50:new_content.find(re.sub(pattern, new_name, current_content))+50] if re.search(pattern, current_content) else None,
                        })
                        logger.info(f"Renamed '{old_name}' to '{new_name}' in content.")
                        current_content = new_content
                        obfuscation_found_in_file = True
                        self.state["obfuscation_detected_this_iter"] = True
                        self.state["total_obfuscation_steps"] += 1
                except ValueError:
                    logger.warning(f"Invalid rename format: {line}")
                except Exception as e:
                    logger.warning(f"Error applying in-content rename '{line}': {e}")

        # Write the potentially modified content back if any changes were made
        if current_content != original_content_for_diff: # Check if *any* content change happened
            if write_file_content(current_filepath_in_deobf_dir, current_content):
                logger.info(f"Deobfuscation applied to {relative_path}. Saved to {current_filepath_in_deobf_dir}")
                return True
            else:
                logger.error(f"Failed to save deobfuscated content for {relative_path}.")
                return False
        else:
            logger.info(f"No significant deobfuscation applied to {relative_path} in this iteration.")
            return False # Indicate no change for this iteration

    def generate_deobfuscation_report(self):
        """Generates a detailed report of all deobfuscation changes."""
        report_path = os.path.join(self.output_dir, PROOF_REPORT_FILE)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"--- Deobfuscation Report for {self.input_extracted_dir} ---\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Iterations: {self.state['current_iteration']}\n")
            f.write(f"Total Deobfuscation Steps Applied: {self.state['total_obfuscation_steps']}\n")
            f.write(f"Deobfuscated files located in: {self.deobfuscated_dir}\n\n")

            f.write("--- Summary of Changes ---\n\n")

            # Group changes by file for better readability
            changes_by_file = {}
            for entry in self.deobfuscation_log_entries:
                filepath = entry.get("relative_filepath") or entry.get("original_relative_path") # Use original if it's a file rename
                if filepath not in changes_by_file:
                    changes_by_file[filepath] = []
                changes_by_file[filepath].append(entry)
            
            for filepath, entries in changes_by_file.items():
                f.write(f"File: {filepath}\n")
                for entry in entries:
                    f.write(f"  - Type: {entry['type']} (Iteration: {entry['iteration']})\n")
                    if entry["type"] == "file_rename":
                        f.write(f"    Renamed from: {entry['old_name']}\n")
                        f.write(f"    Renamed to: {entry['new_name']}\n")
                    elif entry["type"] == "regex_remove":
                        f.write(f"    Pattern Removed: `{entry['pattern']}`\n")
                        if entry.get("original_snippet"):
                            f.write(f"    Original Snippet: '{entry['original_snippet'].replacelines(r'\n')}'\n") # Single line
                    elif entry["type"] == "string_decrypt":
                        f.write(f"    Encrypted: '{entry['encrypted_data']}'\n")
                        f.write(f"    Decrypted: '{entry['decrypted_string']}'\n")
                        f.write(f"    Pattern Used: `{entry['pattern_used']}`\n")
                        f.write(f"    Original Match: '{entry['original_snippet'].replacelines(r'\n')}'\n") # Single line
                    elif entry["type"] == "content_rename":
                        f.write(f"    Renamed '{entry['old_name']}' to '{entry['new_name']}'\n")
                        f.write(f"    Pattern Used: `{entry['pattern']}`\n")
                        if entry.get("original_snippet"):
                            f.write(f"    Original Snippet: '{entry['original_snippet'].replacelines(r'\n')}'\n") # Single line
                f.write("\n")
            
            # Add full diffs for all modified text files
            f.write("\n--- Full File Diffs (Original vs. Deobfuscated) ---\n\n")
            for root, _, files in os.walk(self.deobfuscated_dir):
                for filename in files:
                    filepath_deobf = os.path.join(root, filename)
                    relative_path_deobf = os.path.relpath(filepath_deobf, self.deobfuscated_dir)
                    original_path_corresponding = os.path.join(self.input_extracted_dir, relative_path_deobf) # Assume same rel path for original

                    # Handle renames for diff: find the original source of this file
                    original_source_for_diff = original_path_corresponding
                    for entry in self.deobfuscation_log_entries:
                        if entry["type"] == "file_rename" and entry["new_relative_path"] == relative_path_deobf:
                            original_source_for_diff = os.path.join(self.input_extracted_dir, entry["original_relative_path"])
                            break

                    if not os.path.exists(original_source_for_diff) or get_file_type_hint(filepath_deobf) not in ["SQF (Arma Scripting Language)/Enforce Script", "C++ Source Code", "Plain Text"]:
                        continue # Skip if no original or if not a text file

                    original_lines = read_file_content(original_source_for_diff)
                    deobfuscated_lines = read_file_content(filepath_deobf)

                    if original_lines is None or deobfuscated_lines is None:
                        continue
                    
                    original_lines_list = original_lines.splitlines(keepends=True)
                    deobfuscated_lines_list = deobfuscated_lines.splitlines(keepends=True)

                    if original_lines_list == deobfuscated_lines_list:
                        continue # Skip if content is identical (e.g., binary files copied, or text files with no changes)

                    diff = difflib.unified_diff(original_lines_list, deobfuscated_lines_list, 
                                                fromfile=os.path.basename(original_source_for_diff), 
                                                tofile=os.path.basename(filepath_deobf),
                                                lineterm='') # No line terminators in output

                    f.write(f"--- Diff for {relative_path_deobf} ---\n")
                    f.writelines(diff)
                    f.write("\n\n")
        logger.info(f"Deobfuscation report generated: {report_path}")

    def generate_manual_deobfuscation_script(self):
        """Generates a Python script to manually replicate deobfuscation."""
        script_path = os.path.join(self.output_dir, MANUAL_SCRIPT_FILE)
        
        script_content = []
        script_content.append(f"# Manual Deobfuscation Script\n")
        script_content.append(f"# Generated by PBO Deobfuscator Agent on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        script_content.append(f"# WARNING: Run this script in a clean, isolated environment.\n")
        script_content.append(f"# It will apply changes to files in the TARGET_DIRECTORY.\n")
        script_content.append(f"# Make sure to provide the path to the *original extracted* PBO content.\n\n")

        script_content.append(f"import os\nimport re\nimport shutil\n\n")
        script_content.append(f"TARGET_DIRECTORY = r'{self.deobfuscated_dir}' # The directory to apply changes to\n") # Or input_extracted_dir if we want to rebuild from scratch
        script_content.append(f"# If you want to apply to a fresh copy of original extracted files, change TARGET_DIRECTORY to point there,\n")
        script_content.append(f"# and ensure that directory contains the *original, un-deobfuscated* files.\n\n")

        # Include all identified decryption functions
        script_content.append("# --- Decryption Functions (from Ollama) ---\n")
        for func_name, snippet in self.decryption_functions.items():
            script_content.append(snippet + "\n\n")
        script_content.append("# ----------------------------------------\n\n")

        # Group operations by file path (post-rename path if applicable)
        file_operations = {}
        for entry in self.deobfuscation_log_entries:
            # Use the NEW_RELATIVE_PATH for file renames, otherwise the current relative_filepath
            target_file_rel_path = entry.get("new_relative_path") if entry["type"] == "file_rename" else entry["relative_filepath"]
            if target_file_rel_path not in file_operations:
                file_operations[target_file_rel_path] = []
            file_operations[target_file_rel_path].append(entry)

        # First, process file renames separately as they affect paths
        script_content.append("# --- File Renames ---\n")
        script_content.append("file_renames = [\n")
        for entry in self.deobfuscation_log_entries:
            if entry["type"] == "file_rename":
                original_full_path_for_rename = os.path.join(self.input_extracted_dir, entry["original_relative_path"])
                new_full_path_for_rename = os.path.join(self.deobfuscated_dir, entry["new_relative_path"])
                
                # For manual script, we want to rename the original relative path to the new relative path
                script_content.append(f"    (r'{entry['original_relative_path']}', r'{entry['new_relative_path']}'), # {entry['old_name']} -> {entry['new_name']}\n")
        script_content.append("]\n\n")

        script_content.append("print('Applying file renames...')\n")
        script_content.append("for old_rel_path, new_rel_path in file_renames:\n")
        script_content.append("    full_old_path = os.path.join(TARGET_DIRECTORY, old_rel_path)\n")
        script_content.append("    full_new_path = os.path.join(TARGET_DIRECTORY, new_rel_path)\n")
        script_content.append("    if os.path.exists(full_old_path):\n")
        script_content.append("        os.makedirs(os.path.dirname(full_new_path), exist_ok=True)\n")
        script_content.append("        try:\n")
        script_content.append("            os.rename(full_old_path, full_new_path)\n")
        script_content.append("            print(f'Renamed {{old_rel_path}} to {{new_rel_path}}')\n")
        script_content.append("        except Exception as e:\n")
        script_content.append("            print(f'Error renaming {{old_rel_path}} to {{new_rel_path}}: {{e}}')\n")
        script_content.append("    else:\n")
        script_content.append("        print(f'Skipping rename: {{full_old_path}} does not exist (perhaps already renamed or original not found).')\n")
        script_content.append("print('File renames complete.\\n')\n\n")

        # Now, content modifications
        script_content.append("# --- Content Modifications ---\n")
        script_content.append("print('Applying content modifications...')\n")
        script_content.append("content_operations = {\n")
        for rel_path, entries in file_operations.items():
            # Skip entries already handled as file_renames for content modification part
            if any(e["type"] == "file_rename" for e in entries):
                # The rel_path for content changes should be the *new* path if it was renamed
                # We already handled file renames above, so here we assume the file is at its final path
                pass
            
            # This is complex because the manual script needs to know the *final* path
            # A simpler way: The manual script works on the *deobfuscated_dir* itself or a copy of it.
            # So, the relative paths in file_operations are already the correct target paths.
            script_content.append(f"    r'{rel_path}': [\n")
            for entry in entries:
                if entry["type"] == "regex_remove":
                    script_content.append(f"        {{'type': 'regex_remove', 'pattern': r'''{entry['pattern']}'''}},\n")
                elif entry["type"] == "string_decrypt":
                    script_content.append(f"        {{'type': 'string_decrypt', 'pattern': r'''{entry['pattern_used']}'''}},\n") # Pattern only, func will be called from global
                elif entry["type"] == "content_rename":
                    script_content.append(f"        {{'type': 'content_rename', 'old': r'''{entry['old_name']}''', 'new': r'''{entry['new_name']}'''}},\n")
            script_content.append("    ],\n")
        script_content.append("}\n\n")

        script_content.append("for rel_path, ops in content_operations.items():\n")
        script_content.append("    filepath = os.path.join(TARGET_DIRECTORY, rel_path)\n")
        script_content.append("    if not os.path.exists(filepath):\n")
        script_content.append("        print(f'Warning: {{filepath}} not found. Skipping content modifications.')\n")
        script_content.append("        continue\n")
        script_content.append("    \n")
        script_content.append("    content = ''\n")
        script_content.append("    try:\n")
        script_content.append("        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:\n")
        script_content.append("            content = f.read()\n")
        script_content.append("    except Exception as e:\n")
        script_content.append("        print(f'Error reading {{filepath}}: {{e}}')\n")
        script_content.append("        continue\n")
        script_content.append("    \n")
        script_content.append("    original_content_for_diff = content # For comparison\n")
        script_content.append("    \n")
        script_content.append("    for op in ops:\n")
        script_content.append("        if op['type'] == 'regex_remove':\n")
        script_content.append("            try:\n")
        script_content.append("                pattern = re.compile(op['pattern'], re.MULTILINE)\n")
        script_content.append("                content = re.sub(pattern, '', content)\n")
        script_content.append("                print(f'  - Removed pattern in {{rel_path}}: {{op[\"pattern\"][:50]}}...')\n")
        script_content.append("            except re.error as e:\n")
        script_content.append("                print(f'  - Invalid regex for removal in {{rel_path}}: {{op[\"pattern\"]}} - {{e}}')\n")
        script_content.append("        elif op['type'] == 'string_decrypt':\n")
        script_content.append("            try:\n")
        script_content.append("                def replacer(match):\n")
        script_content.append("                    encrypted_data = match.group(1)\n")
        script_content.append("                    try:\n")
        script_content.append("                        # Assumes decrypt_string is globally available in the generated script\n")
        script_content.append("                        decrypted = decrypt_string(encrypted_data)\n")
        script_content.append("                        return f'\"{{decrypted}}\"'\n")
        script_content.append("                    except Exception as e:\n")
        script_content.append("                        print(f'    - Decryption failed for {{encrypted_data}} in {{rel_path}}: {{e}}')\n")
        script_content.append("                        return match.group(0)\n")
        script_content.append("                pattern = re.compile(op['pattern'], re.MULTILINE)\n")
        script_content.append("                content = re.sub(pattern, replacer, content)\n")
        script_content.append("                print(f'  - Applied string decryption in {{rel_path}} using pattern: {{op[\"pattern\"][:50]}}...')\n")
        script_content.append("            except re.error as e:\n")
        script_content.append("                print(f'  - Invalid regex for decryption in {{rel_path}}: {{op[\"pattern\"]}} - {{e}}')\n")
        script_content.append("        elif op['type'] == 'content_rename':\n")
        script_content.append("            try:\n")
        script_content.append("                pattern = r'\\\\b' + re.escape(op['old']) + r'\\\\b'\n")
        script_content.append("                content = re.sub(pattern, op['new'], content)\n")
        script_content.append("                print(f'  - Renamed {{op[\"old\"]}} to {{op[\"new\"]}} in {{rel_path}}')\n")
        script_content.append("            except Exception as e:\n")
        script_content.append("                print(f'  - Error renaming content in {{rel_path}}: {{e}}')\n")
        script_content.append("    \n")
        script_content.append("    if content != original_content_for_diff:\n")
        script_content.append("        try:\n")
        script_content.append("            with open(filepath, 'w', encoding='utf-8') as f:\n")
        script_content.append("                f.write(content)\n")
        script_content.append("            print(f'  - Saved modified content for {{rel_path}}')\n")
        script_content.append("        except Exception as e:\n")
        script_content.append("            print(f'  - Error writing modified content to {{filepath}}: {{e}}')\n")
        script_content.append("    else:\n")
        script_content.append("        print(f'  - No changes applied to {{rel_path}} in content pass.')\n")
        script_content.append("print('Content modifications complete.\\n')\n")
        script_content.append("print('Manual deobfuscation script execution finished.')\n")

        with open(script_path, 'w', encoding='utf-8') as f:
            f.writelines(script_content)
        logger.info(f"Manual deobfuscation script generated: {script_path}")


    def run(self):
        """Main execution loop for the deobfuscation agent."""
        logger.info("Starting PBO Deobfuscation Agent.")

        # Step 1: Copy initial extracted content to the deobfuscated_dir
        logger.info(f"Copying initial extracted files from '{self.input_extracted_dir}' to '{self.deobfuscated_dir}' for processing...")
        if os.path.exists(self.deobfuscated_dir): # Clean up previous runs if any
            shutil.rmtree(self.deobfuscated_dir)
        shutil.copytree(self.input_extracted_dir, self.deobfuscated_dir, dirs_exist_ok=True)
        logger.info("Initial copy complete.")

        # Step 2: Initial scan of files in the working directory (deobfuscated_dir)
        if not self._scan_and_prioritize_files(self.deobfuscated_dir):
            logger.warning("No files found in the extracted content directory. Nothing to deobfuscate.")
            return

        # Step 3: Iterative Deobfuscation Loop
        while self.state["current_iteration"] < MAX_DEOBF_ITERATIONS:
            self.state["current_iteration"] += 1
            self.state["obfuscation_detected_this_iter"] = False
            logger.info(f"\n--- Deobfuscation Iteration {self.state['current_iteration']} ---")

            # Re-scan the deobfuscated directory to pick up renamed files etc.
            # We want to process the *latest* version of each file in the working directory.
            self._scan_and_prioritize_files(self.deobfuscated_dir) 

            # Iterate over a *copy* of the file list, as `_analyze_and_deobfuscate_file` might rename files.
            # Store (filepath, relative_path, file_type_hint) as they were at the start of iteration
            files_for_this_iteration = list(self.state["files_to_process"]) 

            for filepath, relative_path, file_type_hint in files_for_this_iteration:
                if file_type_hint in ["SQF (Arma Scripting Language)/Enforce Script", "C++ Source Code", "Plain Text"]:
                    # Pass the *current* path within the deobfuscated_dir
                    self._analyze_and_deobfuscate_file(filepath, relative_path, file_type_hint)
                else:
                    logger.debug(f"Skipping binary/unlikely obfuscated file: {relative_path}")

            if not self.state["obfuscation_detected_this_iter"]:
                logger.info(f"No new obfuscation detected in iteration {self.state['current_iteration']}. Deobfuscation complete or stalled.")
                break
            else:
                logger.info(f"Obfuscation detected and steps taken in iteration {self.state['current_iteration']}. Continuing...")

        logger.info(f"\n--- Deobfuscation Process Finished ---")
        logger.info(f"Total iterations: {self.state['current_iteration']}")
        logger.info(f"Total deobfuscation steps applied: {self.state['total_obfuscation_steps']}")
        logger.info(f"Cleaned files are in: {self.deobfuscated_dir}")

        self.generate_deobfuscation_report()
        self.generate_manual_deobfuscation_script()

        logger.info("Agent job done.")

# --- Main Execution ---
if __name__ == "__main__":
    # --- IMPORTANT ---
    # 1. Ensure Ollama is running and has the specified model downloaded (`ollama pull llama3`).
    # 2. **You must manually extract your PBO file into a directory before running this script.**
    #    For example, if your PBO is `SpawnSystem_Server.pbo`, extract it to a folder like `SpawnSystem_Server_extracted`.
    #    You can use:
    #    - `7z x SpawnSystem_Server.pbo -oSpawnSystem_Server_extracted` (if 7z works for your PBOs)
    #    - `CPB_Unpack.exe SpawnSystem_Server.pbo SpawnSystem_Server_extracted` (if using Arma 3 Tools)
    #    - `pbo_tools` in a separate Python script:
    #      ```python
    #      import pbo_tools
    #      with open('SpawnSystem_Server.pbo', 'rb') as f:
    #          pbo_archive = pbo_tools.PBO.from_stream(f)
    #          pbo_archive.extract_all('SpawnSystem_Server_extracted')
    #      ```

    # --- Configuration for your run ---
    # Replace 'path/to/your/extracted_pbo_content' with the actual path
    # where you extracted your PBO.
    extracted_pbo_content_path = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server" 
    output_directory = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server_cleaned" 

    if os.path.exists(extracted_pbo_content_path) and os.path.isdir(extracted_pbo_content_path):
        try:
            agent = PBO_Deobfuscator_Agent(extracted_pbo_content_path, output_directory)
            agent.run()
        except FileNotFoundError as e:
            logger.critical(f"Error: {e}")
            logger.critical("Please ensure the extracted content directory exists and is a valid path.")
        except Exception as e:
            logger.critical(f"An unexpected error occurred during agent execution: {e}")
            logger.critical("Ensure Ollama is running and the specified model is downloaded.")
    else:
        logger.critical(f"Error: Extracted PBO content directory not found at '{extracted_pbo_content_path}'.")
        logger.critical("Please extract your .pbo file to this location or update the 'extracted_pbo_content_path' variable.")