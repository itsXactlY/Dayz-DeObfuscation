import os
import shutil
import subprocess
import json
import logging
import re
import time
from datetime import datetime

# --- Configuration ---
OLLAMA_MODEL = "deepseek-r1:8b"#"llama3.1:8b"  # Or "codellama", "mixtral", etc.
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
    if ext in ['.sqf', '.fsm']:
        return "SQF (Arma Scripting Language)"
    elif ext in ['.cpp', '.h', '.hpp']:
        return "C++ Source Code"
    elif ext in ['.txt', '.log', '.md', '.html', '.xml', '.json']:
        return "Plain Text/Markup"
    elif ext in ['.paa', '.jpg', '.png', '.tga', '.dds']:
        return "Image File (binary, likely not obfuscated)"
    elif ext in ['.p3d', '.rtm', '.ebo']:
        return "Model/Animation File (binary, likely not obfuscated)"
    elif ext in ['.bisign', '.bikey']:
        return "Signature/Key File (binary)"
    else:
        return "Unknown/Other (treat as text if possible)"

# --- Main Deobfuscator Agent Class ---
class ExtractedContent_Deobfuscator_Agent:
    def __init__(self, extracted_source_directory, output_dir):
        if not os.path.isdir(extracted_source_directory):
            raise FileNotFoundError(f"Source directory not found: {extracted_source_directory}")

        self.source_dir = os.path.abspath(extracted_source_directory)
        self.output_dir = os.path.abspath(output_dir)
        self.deobfuscated_dir = os.path.join(self.output_dir, "deobfuscated_content")
        
        # State to manage the process
        self.state = {
            "current_iteration": 0,
            "files_to_process": [],
            "obfuscation_detected_this_iter": False,
            "total_obfuscation_steps": 0
        }
        
        os.makedirs(self.deobfuscated_dir, exist_ok=True)
        logger.info(f"Initialized Deobfuscator for extracted content from '{self.source_dir}'. Output to '{self.output_dir}'")

    def _copy_initial_content(self):
        """Copies the initial extracted content to the deobfuscated directory."""
        logger.info(f"Copying initial extracted files from '{self.source_dir}' to '{self.deobfuscated_dir}' for processing...")
        
        # Clear previous contents if exists, then copy
        if os.path.exists(self.deobfuscated_dir):
            shutil.rmtree(self.deobfuscated_dir)
        shutil.copytree(self.source_dir, self.deobfuscated_dir)
        logger.info("Initial content copied successfully.")

    def _scan_and_prioritize_files(self, directory_to_scan):
        """Scans a directory for files, prioritizing code/script files."""
        found_files = []
        for root, _, files in os.walk(directory_to_scan):
            for filename in files:
                filepath = os.path.join(root, filename)
                relative_path = os.path.relpath(filepath, directory_to_scan)
                file_type_hint = get_file_type_hint(filepath)
                
                # Prioritize based on likelihood of containing code/scripts
                if file_type_hint in ["SQF (Arma Scripting Language)", "C++ Source Code", "Plain Text/Markup"]:
                    priority = 1 # High priority
                else:
                    priority = 2 # Lower priority for binary or less likely obfuscated files
                found_files.append((priority, filepath, relative_path, file_type_hint))
        
        found_files.sort(key=lambda x: x[0]) # Sort by priority
        self.state["files_to_process"] = [(fp, rp, ft) for _, fp, rp, ft in found_files]
        logger.info(f"Found {len(self.state['files_to_process'])} files to process, prioritized.")
        return len(self.state["files_to_process"]) > 0

    def _analyze_and_deobfuscate_file(self, current_filepath, relative_path, file_type_hint):
        """Analyzes a single file for obfuscation and attempts to deobfuscate."""
        logger.info(f"Analyzing file: {relative_path} (Type: {file_type_hint})")
        
        content = read_file_content(current_filepath)
        if content is None:
            return False # Failed to read

        # Max content to send to Ollama to avoid context window limits
        ollama_content = content[:4000] 
        if len(content) > 4000:
            ollama_content += "\n... [content truncated for Ollama analysis] ..."

        deobfuscation_prompt = rf"""
        You are an expert reverse engineer analyzing an obfuscated game file.
        The file is part of a Bohemia Interactive game mod, originally from a PBO archive.
        File Path (relative to the extracted root): {relative_path}
        File Type Hint: {file_type_hint}

        Analyze the following code/text content for signs of obfuscation.
        Look for:
        1.  **File Naming Obfuscation:** Does the file name ({os.path.basename(current_filepath)}) seem deliberately scrambled (e.g., random characters, misleading extensions) given its content or common game file conventions? If so, suggest a more logical original name. This suggestion should be for the CURRENT file being analyzed.
        2.  **Junk Code:** Identify any dead code, useless computations, or repetitive assignments that serve no purpose.
        3.  **String/Literal Obfuscation:** Look for encrypted strings, computed strings, or patterns that construct strings at runtime. Common in SQF for `call compile` on hex/base64 encoded strings.
        4.  **Variable/Function Obfuscation:** Identify highly randomized or meaningless variable/function names.
        5.  **Control Flow Obfuscation:** Look for complex `if/else`, `switch`, or `goto` structures that obscure the logic.
        6.  **Other Obfuscation:** Any other unusual patterns or anti-tampering techniques.

        Provide your analysis and a step-by-step deobfuscation strategy.
        For each obfuscation type detected, provide:
        -   **Detection:** How you identified it.
        -   **Suggested Action (Python/Regex):** Concrete steps or Python-compatible regular expressions to clean or reverse the obfuscation.
            For renaming, provide `OLD_NAME -> NEW_NAME` pairs specifically for the CURRENT file's base name.
            For junk code, provide the specific regex to match and remove.
            For string deobfuscation, describe the algorithm or provide a simple Python snippet if applicable.
            For variable/function renames within the file content, provide `OLD_VAR_NAME -> NEW_VAR_NAME` pairs.
        -   **Confidence:** (High/Medium/Low)

        If no significant obfuscation is detected, state "No significant obfuscation detected."

        --- FILE CONTENT ---
        {ollama_content}
        --- END FILE CONTENT ---

        Your response should be structured clearly, making it easy for an automated script to parse.
        Example for a regex suggestion (to remove lines starting with `_temp` and ending with `;`):

        ^\s*_temp\d+\s*=\s*.*?;\s*$

        Example for renaming the current file:

        {os.path.basename(current_filepath)} -> new_meaningful_name.sqf

        Example for renaming variables within the file:

        _xYz -> _secretMessage
        _aJkL_ -> _userCount

        Example for string decryption (if simple and identifies an `_x = call compile (hex)` pattern):

        # Example pattern for SQF hex-encoded strings
        # Look for patterns like `call compile "\\x68\\x65\\x6c\\x6c\\x6f"`
        def apply_hex_decode(content):
            def replace_hex_string(match):
                hex_encoded = match.group(1).replace('\\x', '')
                try:
                    decoded = bytes.fromhex(hex_encoded).decode('utf-8')
                    return f'"{{decoded}}"'
                except Exception:
                    return match.group(0)

            return re.sub(r'call compile "\\\\x([0-9a-fA-F]+)"', replace_hex_string, content)
        """

        ollama_response = ollama_query(deobfuscation_prompt)

        if ollama_response is None:
            logger.error(f"Failed to get Ollama response for {relative_path}. Skipping deobfuscation for this file.")
            return False

        modified_content = content
        obfuscation_found_in_file = False

        # --- Process Ollama's Suggestions ---
        logger.info(f"Ollama's analysis for {relative_path}:\n{ollama_response[:1000]}...")

        # 1. File Renaming (Special Case: needs to be done on disk, before saving content)
        renames_file_section_match = re.search(r'```renames_file\n(.*?)\n```', ollama_response, re.DOTALL)
        if renames_file_section_match:
            rename_suggestions = renames_file_section_match.group(1).strip().split('\n')
            for rename_line in rename_suggestions:
                parts = rename_line.split(' -> ')
                if len(parts) == 2:
                    old_name_frag = parts[0].strip()
                    new_name_frag = parts[1].strip()
                    # Ensure we are renaming the *current* file
                    if os.path.basename(current_filepath) == old_name_frag:
                        new_filepath = os.path.join(os.path.dirname(current_filepath), new_name_frag)
                        try:
                            os.rename(current_filepath, new_filepath)
                            logger.info(f"Renamed file {os.path.basename(current_filepath)} to {os.path.basename(new_filepath)}")
                            current_filepath = new_filepath # Update the path for subsequent operations
                            relative_path = os.path.relpath(new_filepath, self.deobfuscated_dir) # Update relative path
                            obfuscation_found_in_file = True
                            self.state["obfuscation_detected_this_iter"] = True
                            self.state["total_obfuscation_steps"] += 1
                        except Exception as e:
                            logger.warning(f"Could not rename file {os.path.basename(current_filepath)} to {os.path.basename(new_filepath)}: {e}")
                    else:
                        logger.debug(f"Ollama suggested renaming '{old_name_frag}' but current file is '{os.path.basename(current_filepath)}'. Skipping rename for this file content analysis.")

        # 2. Junk Code Removal / Regex-based cleaning
        regex_matches = re.findall(r'```regex_remove\n(.*?)\n```', ollama_response, re.DOTALL)
        for regex_str in regex_matches:
            try:
                # Add re.MULTILINE for line-by-line matching if applicable
                pattern = re.compile(regex_str, re.MULTILINE)
                new_content = re.sub(pattern, '', modified_content)
                if new_content != modified_content:
                    logger.info(f"Applied regex removal pattern: '{regex_str}'")
                    modified_content = new_content
                    obfuscation_found_in_file = True
                    self.state["obfuscation_detected_this_iter"] = True
                    self.state["total_obfuscation_steps"] += 1
            except re.error as e:
                logger.warning(f"Invalid regex suggested by Ollama: '{regex_str}' - Error: {e}")
            except Exception as e:
                logger.warning(f"Error applying regex '{regex_str}': {e}")

        # 3. String Decryption (if simple and Python snippet provided with apply logic)
        python_apply_decrypt_snippets = re.findall(r'```python_apply_decrypt\n(.*?)\n```', ollama_response, re.DOTALL)
        for snippet in python_apply_decrypt_snippets:
            try:
                logger.warning(f"Attempting to execute and apply Python decryption snippet. This is a security risk if the snippet is malicious. Sandbox in production!")
                
                exec_globals = {}
                exec_locals = {}
                exec(snippet, exec_globals, exec_locals)

                # Assuming the snippet defines a function that takes content and returns modified content
                if 'apply_hex_decode' in exec_locals and callable(exec_locals['apply_hex_decode']): # Example func name
                    new_content = exec_locals['apply_hex_decode'](modified_content)
                    if new_content != modified_content:
                        logger.info(f"Applied string decryption/decoding using Python snippet.")
                        modified_content = new_content
                        obfuscation_found_in_file = True
                        self.state["obfuscation_detected_this_iter"] = True
                        self.state["total_obfuscation_steps"] += 1
                else:
                    logger.warning("Python decryption snippet did not define an 'apply_hex_decode' (or similar) function as expected.")

            except Exception as e:
                logger.warning(f"Error executing/applying Python decryption snippet: {e}")

        # 4. Variable/Function Renaming (simple string replace - dangerous if not careful, AST is better)
        renames_vars_matches = re.search(r'```renames_vars\n(.*?)\n```', ollama_response, re.DOTALL)
        if renames_vars_matches:
            rename_lines = renames_vars_matches.group(1).strip().split('\n')
            for line in rename_lines:
                try:
                    old_name, new_name = map(str.strip, line.split(' -> '))
                    # Use word boundaries to avoid replacing substrings within other names
                    # This is still very basic and can easily break code if names clash or contexts differ.
                    pattern = r'\b' + re.escape(old_name) + r'\b'
                    new_content = re.sub(pattern, new_name, modified_content)
                    if new_content != modified_content:
                        logger.info(f"Renamed '{old_name}' to '{new_name}' in content.")
                        modified_content = new_content
                        obfuscation_found_in_file = True
                        self.state["obfuscation_detected_this_iter"] = True
                        self.state["total_obfuscation_steps"] += 1
                except ValueError:
                    logger.warning(f"Invalid variable rename format: {line}")
                except Exception as e:
                    logger.warning(f"Error applying variable rename '{line}': {e}")


        # Write the potentially modified content back
        if obfuscation_found_in_file:
            final_output_path = current_filepath # Path might have changed due to rename
            if write_file_content(final_output_path, modified_content):
                logger.info(f"Deobfuscation applied to {relative_path}. Saved to {final_output_path}")
                return True
            else:
                logger.error(f"Failed to save deobfuscated content for {relative_path}.")
                return False
        else:
            logger.info(f"No significant deobfuscation applied to {relative_path} in this iteration.")
            return False # Indicate no change for this iteration

    def run(self):
        """Main execution loop for the deobfuscation agent."""
        logger.info("Starting Deobfuscation Agent (Operating on pre-extracted content).")

        # Step 1: Copy initial content to working directory
        self._copy_initial_content()

        # Step 2: Initial scan of copied files
        if not self._scan_and_prioritize_files(self.deobfuscated_dir):
            logger.warning("No files found in the copied content. Nothing to deobfuscate.")
            return

        # Step 3: Iterative Deobfuscation Loop
        while self.state["current_iteration"] < MAX_DEOBF_ITERATIONS:
            self.state["current_iteration"] += 1
            self.state["obfuscation_detected_this_iter"] = False
            logger.info(f"\n--- Deobfuscation Iteration {self.state['current_iteration']} ---")

            # Re-scan the deobfuscated directory to pick up renamed files etc.
            # We want to process the *latest* version of each file in the working directory.
            self._scan_and_prioritize_files(self.deobfuscated_dir) 

            for filepath, relative_path, file_type_hint in self.state["files_to_process"]:
                if file_type_hint in ["SQF (Arma Scripting Language)", "C++ Source Code", "Plain Text/Markup"]:
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
    # --- IMPORTANT ---
    # 1. Ensure Ollama is running and has the specified model downloaded (`ollama pull llama3`).
    # 2. **Manually extract your PBO file first** to a directory, e.g., 'path/to/my_extracted_pbo'.
    #    You can use:
    #    - Your preferred PBO unpacker (e.g., Arma 3 Tools' `CPB_Unpack.exe` or `PBO Manager`).
    #    - The `pbo_tools` Python library if you have it installed:
    #      ```python
    #      import pbo_tools
    #      with open("SpawnSystem_Server.pbo", 'rb') as f:
    #          pbo_archive = pbo_tools.PBO.from_stream(f)
    #          pbo_archive.extract_all("path/to/my_extracted_pbo")
    #      ```
    # 3. Set the `extracted_source_path` variable below to the path of this extracted directory.
    # -----------------

    extracted_source_path = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/" # <--- REPLACE WITH YOUR ACTUAL EXTRACTED PATH
    output_directory = "/home/alca/deobf_results_pre_extracted" # Where the deobfuscated files will be saved

    # --- For a quick test, let's try to create a dummy extracted directory if it doesn't exist ---
    dummy_extracted_dir = "temp_dummy_extracted_content"
    if not os.path.exists(extracted_source_path):
        logger.warning(f"The specified extracted source path '{extracted_source_path}' does not exist.")
        logger.warning(f"Creating a dummy extracted directory '{dummy_extracted_dir}' for testing purposes.")
        os.makedirs(dummy_extracted_dir, exist_ok=True)
        with open(os.path.join(dummy_extracted_dir, "jUnK.sqf"), "w", encoding="utf-8") as f:
            f.write("""
            // My heavily obfuscated script
            _tMpVaR = 1 + 1; // junk
            _anotherUselessLine = "abc" + "def"; // more junk

            _secretMsg = call compile ("\\x48\\x65\\x6c\\x6c\\x6f\\x20\\x57\\x6f\\x72\\x6c\\x64\\x21"); // "Hello World!" in hex
            hint _secretMsg;

            _rAnDoM_NaMe = 12345; // variable to rename
            diag_log str _rAnDoM_NaMe;
            """)
        with open(os.path.join(dummy_extracted_dir, "config.ext"), "w", encoding="utf-8") as f:
            f.write("""
            // This is a config file
            class ObfusCated_ClasS_NaMe {
                displayName = "Obfuscated Module";
            };
            """)
        extracted_source_path = dummy_extracted_dir
        logger.info(f"Dummy extracted content created at: {extracted_source_path}")

    # --- Run the Agent ---
    if os.path.isdir(extracted_source_path):
        try:
            agent = ExtractedContent_Deobfuscator_Agent(extracted_source_path, output_directory)
            agent.run()
        except Exception as e:
            logger.critical(f"An error occurred during agent execution: {e}")
            logger.critical("Ensure Ollama is running and the specified model is downloaded.")
    else:
        logger.critical(f"The specified extracted source directory '{extracted_source_path}' does not exist.")
        logger.critical("Please extract your PBO file first and provide the correct path.")