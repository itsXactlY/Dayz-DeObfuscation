import os
import shutil
import subprocess
import json
import logging
import re
import time
from datetime import datetime

# --- Configuration ---
OLLAMA_MODEL = "llama3.1:8b"  # Or "codellama", "mixtral", etc.
OLLAMA_API_URL = "http://localhost:11434/api/generate" # Default Ollama API endpoint
LOG_FILE = "deobfuscator_log.txt"
MAX_DEOBF_ITERATIONS = 5 # How many times to try and re-analyze/deobfuscate

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
        """
        logger.info(f"Analyzing file: {relative_path} (Type: {file_type_hint})")
        
        content = read_file_content(current_filepath_in_deobf_dir)
        if content is None:
            return False # Failed to read

        # Max content to send to Ollama to avoid context window limits
        ollama_content = content[:8000] # Increased for more context
        if len(content) > 8000:
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
            *   For **string deobfuscation**, if you can determine the decryption algorithm and it's simple enough for a Python function, provide the `python_decrypt_snippet` AND a `regex_decrypt_target` that captures *only the encrypted string* in group 1.
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
        Example for string decryption (if simple) - **provide the function:**
        ```python_decrypt_snippet
        def decrypt_string(encrypted_data):
            # Example: simple XOR
            # This is a placeholder, Ollama needs to deduce the actual algorithm
            return "".join(chr(ord(c) ^ 0xAB) for c in encrypted_data)
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

        current_content = content
        obfuscation_found_in_file = False

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
                    # Check if Ollama wants to rename THIS file
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

                            os.rename(current_filepath_in_deobf_dir, new_filepath)
                            logger.info(f"Renamed file {current_file_basename} to {os.path.basename(new_filepath)}")
                            current_filepath_in_deobf_dir = new_filepath # Update path for subsequent operations
                            relative_path = os.path.relpath(new_filepath, self.deobfuscated_dir) # Update relative path
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

        if python_decrypt_snippets and regex_decrypt_targets:
            logger.warning(f"Attempting to execute Python decryption snippet. This is a security risk if the snippet is malicious. Sandbox in production!")
            
            exec_globals = {}
            exec_locals = {}
            # Execute all provided snippets to define the decryption function(s)
            for snippet in python_decrypt_snippets:
                try:
                    exec(snippet, exec_globals, exec_locals)
                except Exception as e:
                    logger.warning(f"Error executing Python decryption snippet: {e}")
                    continue

            if 'decrypt_string' in exec_locals and callable(exec_locals['decrypt_string']):
                decrypt_func = exec_locals['decrypt_string']
                for decrypt_regex_str in regex_decrypt_targets:
                    try:
                        # Ensure the regex has a capturing group for the encrypted string
                        # Example: (?:SfFuxbdumezDa91W\s*\.\s*Ns7IynOBl5RX6MyZ\(\s*")([A-Za-z0-9]+)(".*?)
                        # Group 1 is the encrypted string
                        # Group 2 is the rest of the original match after the encrypted string, including the closing quote and context
                        
                        # Use a custom replacer function for re.sub
                        def replace_encrypted_string_with_decrypted(match):
                            encrypted_data = match.group(1) # This is the string captured by group 1
                            # The 'rest_of_call' captures the closing quote and arguments after the string, e.g., '", HBxPZfXX0BhgSqUF)'
                            rest_of_call = match.group(2) if len(match.groups()) > 1 else "" 
                            
                            try:
                                decrypted_string = decrypt_func(encrypted_data)
                                logger.info(f"Decrypted '{encrypted_data}' to '{decrypted_string}'")
                                # Replace the original encrypted string within its context
                                # Example: SfFuxbdumezDa91W.Ns7IynOBl5RX6MyZ("ENCRYPTED", KEY) -> "DECRYPTED"
                                # Or if it's a lookup, maybe `Config.GetValue("PlaintextKey")`
                                
                                # Ollama needs to guide this replacement. For now, we replace the ENCRYPTED_STRING itself
                                # and leave the surrounding call structure, unless the regex itself replaces the whole call.
                                # The current regex_decrypt_target example would replace the entire `SfFuxbdumezDa91W.Ns7IynOBl5RX6MyZ("ENCRYPTED"...)`
                                # with `"DECRYPTED_STRING"`.
                                
                                # The regex for `SfFuxbdumezDa91W.Ns7IynOBl5RX6MyZ("...", ...)` might be more like:
                                # (SfFuxbdumezDa91W\s*\.\s*Ns7IynOBl5RX6MyZ\(\s*)"([A-Za-z0-9]+)"([^)]*\))
                                # Group 1: "(SfFuxbdumezDa91W.Ns7IynOBl5RX6MyZ("
                                # Group 2: "ENCRYPTED_STRING"
                                # Group 3: ", KEY)"
                                # Then return `match.group(1) + '"' + decrypted_string + '"' + match.group(3)`

                                # Let's assume Ollama designs the regex_decrypt_target such that group(1) is the string
                                # and the *replacement* should be the simple string literal.
                                return f'"{decrypted_string}"' # Surround with quotes for string literals
                            except Exception as e:
                                logger.warning(f"Error during decryption of '{encrypted_data}': {e}. Keeping original.")
                                return match.group(0) # Return original full match if decryption fails

                        pattern = re.compile(decrypt_regex_str, re.MULTILINE)
                        new_content = re.sub(pattern, replace_encrypted_string_with_decrypted, current_content)
                        
                        if new_content != current_content:
                            logger.info(f"Applied string decryption using pattern: '{decrypt_regex_str}'.")
                            current_content = new_content
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
                    if os.path.basename(current_filepath_in_deobf_dir) == old_name: 
                        continue 

                    # Use word boundaries for precise replacement of identifiers
                    pattern = r'\b' + re.escape(old_name) + r'\b'
                    new_content = re.sub(pattern, new_name, current_content)
                    if new_content != current_content:
                        logger.info(f"Renamed '{old_name}' to '{new_name}' in content.")
                        current_content = new_content
                        obfuscation_found_in_file = True
                        self.state["obfuscation_detected_this_iter"] = True
                        self.state["total_obfuscation_steps"] += 1
                except ValueError:
                    logger.warning(f"Invalid rename format: {line}")
                except Exception as e:
                    logger.warning(f"Error applying in-content rename '{line}': {e}")

        # Write the potentially modified content back
        if obfuscation_found_in_file:
            if write_file_content(current_filepath_in_deobf_dir, current_content):
                logger.info(f"Deobfuscation applied to {relative_path}. Saved to {current_filepath_in_deobf_dir}")
                return True
            else:
                logger.error(f"Failed to save deobfuscated content for {relative_path}.")
                return False
        else:
            logger.info(f"No significant deobfuscation applied to {relative_path} in this iteration.")
            return False # Indicate no change for this iteration

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
            # The next iteration's `_scan_and_prioritize_files` will pick up the new names.
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

        logger.info("Agent job done.")

# --- Main Execution ---
if __name__ == "__main__":
    # --- Configuration for your run ---
    # Replace 'path/to/your/extracted_pbo_content' with the actual path
    # where you extracted your PBO.
    extracted_pbo_content_path = "/run/media/alca/store/dayz server/EXTRACTED BACKUP!!!!/_AdvancedGroups_Server/" 
    output_directory = "/home/alca/deobf_results"

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