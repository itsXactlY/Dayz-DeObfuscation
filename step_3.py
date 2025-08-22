import os
import shutil
import subprocess
import json
import logging
import re
import time
from datetime import datetime

# --- Configuration ---
OLLAMA_MODEL = "llama3"  # Or "codellama", "mixtral", etc.
OLLAMA_API_URL = "http://localhost:11434/api/generate" # Default Ollama API endpoint
TEMP_DIR_PREFIX = "pbo_deobf_temp_"
LOG_FILE = "deobfuscator_log.txt"
MAX_DEOBF_ITERATIONS = 5 # How many times to try and re-analyze/deobfuscate
EXTERNAL_PBO_EXTRACTOR = "7z" # Or "pbo_tools" (requires installation) or a custom path to 'CPB_unpack.exe'
# If using 'pbo_tools' python library:
# try:
#     import pbo_tools
#     USE_PBO_TOOLS_LIB = True
# except ImportError:
#     USE_PBO_TOOLS_LIB = False
USE_PBO_TOOLS_LIB = False # Set to True if you have 'pbo_tools' installed and want to use it

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def run_command(command, cwd=None, timeout=300):
    """Executes a shell command and returns stdout, stderr, and return code."""
    logger.info(f"Executing command: {' '.join(command)}")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
        stdout, stderr = process.communicate(timeout=timeout)
        if process.returncode != 0:
            logger.error(f"Command failed with exit code {process.returncode}:\nSTDOUT: {stdout}\nSTDERR: {stderr}")
        else:
            logger.info(f"Command successful. STDOUT (abridged):\n{stdout[:500]}...")
        return process.returncode, stdout, stderr
    except FileNotFoundError:
        logger.error(f"Error: Command '{command[0]}' not found. Is it installed and in your PATH?")
        return -1, "", f"Command '{command[0]}' not found."
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        logger.error(f"Command timed out after {timeout} seconds.")
        return -2, stdout, stderr
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return -3, "", str(e)

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
    elif ext in ['.cpp', '.h']:
        return "C++ Source Code"
    elif ext in ['.txt', '.log', '.md']:
        return "Plain Text"
    elif ext in ['.paa', '.jpg', '.png', '.tga']:
        return "Image File (binary, likely not obfuscated)"
    elif ext in ['.p3d', '.rtm']:
        return "Model/Animation File (binary, likely not obfuscated)"
    elif ext in ['.bisign', '.bikey']:
        return "Signature/Key File (binary)"
    else:
        return "Unknown/Other"

# --- Main Deobfuscator Agent Class ---
class PBO_Deobfuscator_Agent:
    def __init__(self, pbo_filepath, output_dir):
        if not os.path.exists(pbo_filepath):
            raise FileNotFoundError(f"PBO file not found: {pbo_filepath}")

        self.pbo_filepath = os.path.abspath(pbo_filepath)
        self.output_dir = os.path.abspath(output_dir)
        self.temp_extract_dir = os.path.join(self.output_dir, f"{TEMP_DIR_PREFIX}{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.deobfuscated_dir = os.path.join(self.output_dir, "deobfuscated_content")
        self.state = {
            "pbo_extracted": False,
            "current_iteration": 0,
            "files_to_process": [],
            "obfuscation_detected_this_iter": False,
            "total_obfuscation_steps": 0
        }
        os.makedirs(self.temp_extract_dir, exist_ok=True)
        os.makedirs(self.deobfuscated_dir, exist_ok=True)
        logger.info(f"Initialized PBO Deobfuscator for '{self.pbo_filepath}'. Output to '{self.output_dir}'")

    def _cleanup_temp_dir(self):
        """Removes the temporary extraction directory."""
        if os.path.exists(self.temp_extract_dir):
            shutil.rmtree(self.temp_extract_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_extract_dir}")

    def _extract_pbo(self):
        """Extracts the PBO file using an external tool or library."""
        if self.state["pbo_extracted"]:
            logger.info("PBO already extracted. Skipping.")
            return True

        logger.info(f"Attempting to extract PBO: {self.pbo_filepath} to {self.temp_extract_dir}")

        if USE_PBO_TOOLS_LIB:
            try:
                import pbo_tools
                with open(self.pbo_filepath, 'rb') as f:
                    pbo_archive = pbo_tools.PBO.from_stream(f)
                    pbo_archive.extract_all(self.temp_extract_dir)
                logger.info("PBO extracted successfully using pbo_tools library.")
                self.state["pbo_extracted"] = True
                return True
            except ImportError:
                logger.error("pbo_tools library not found. Falling back to external command.")
            except Exception as e:
                logger.error(f"Error extracting PBO with pbo_tools: {e}. Falling back to external command.")

        # Fallback to external command (e.g., 7z or CPB_unpack)
        if EXTERNAL_PBO_EXTRACTOR == "7z":
            cmd = [EXTERNAL_PBO_EXTRACTOR, 'x', self.pbo_filepath, f'-o{self.temp_extract_dir}']
        elif EXTERNAL_PBO_EXTRACTOR: # Assume it's a custom path to a PBO unpacker
            cmd = [EXTERNAL_PBO_EXTRACTOR, 'x', self.pbo_filepath, self.temp_extract_dir] # Adjust command based on your tool's syntax
        else:
            logger.critical("No PBO extraction tool configured. Please set EXTERNAL_PBO_EXTRACTOR or install pbo_tools.")
            return False

        retcode, stdout, stderr = run_command(cmd)
        if retcode == 0:
            logger.info(f"PBO extracted successfully using {EXTERNAL_PBO_EXTRACTOR}.")
            self.state["pbo_extracted"] = True
            return True
        else:
            logger.error(f"Failed to extract PBO. Ensure '{EXTERNAL_PBO_EXTRACTOR}' is installed and in your PATH, or that the path is correct.")
            return False

    def _scan_and_prioritize_files(self, directory):
        """Scans a directory for files, prioritizing code/script files."""
        found_files = []
        for root, _, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                relative_path = os.path.relpath(filepath, directory)
                file_type_hint = get_file_type_hint(filepath)
                if file_type_hint in ["SQF (Arma Scripting Language)", "C++ Source Code", "Plain Text"]:
                    priority = 1 # High priority for code/scripts
                else:
                    priority = 2 # Lower priority for other files
                found_files.append((priority, filepath, relative_path, file_type_hint))
        
        found_files.sort(key=lambda x: x[0]) # Sort by priority
        self.state["files_to_process"] = [(fp, rp, ft) for _, fp, rp, ft in found_files]
        logger.info(f"Found {len(self.state['files_to_process'])} files to process, prioritized.")
        return len(self.state["files_to_process"]) > 0

    def _analyze_and_deobfuscate_file(self, original_filepath, relative_path, file_type_hint):
        """Analyzes a single file for obfuscation and attempts to deobfuscate."""
        logger.info(f"Analyzing file: {relative_path} (Type: {file_type_hint})")
        
        content = read_file_content(original_filepath)
        if content is None:
            return False # Failed to read

        # Max content to send to Ollama to avoid context window limits
        ollama_content = content[:4000] 
        if len(content) > 4000:
            ollama_content += "\n... [content truncated for Ollama analysis] ..."

        deobfuscation_prompt = f"""
        You are an expert reverse engineer analyzing an obfuscated game file.
        The file is part of a Bohemia Interactive PBO archive.
        File Path (relative): {relative_path}
        File Type Hint: {file_type_hint}

        Analyze the following code/text content for signs of obfuscation.
        Look for:
        1.  **File Naming Obfuscation:** Does the file name ({os.path.basename(relative_path)}) seem deliberately scrambled (e.g., random characters, misleading extensions) given its content or common game file conventions? If so, suggest a more logical original name.
        2.  **Junk Code:** Identify any dead code, useless computations, or repetitive assignments that serve no purpose.
        3.  **String/Literal Obfuscation:** Look for encrypted strings, computed strings, or patterns that construct strings at runtime.
        4.  **Variable/Function Obfuscation:** Identify highly randomized or meaningless variable/function names.
        5.  **Control Flow Obfuscation:** Look for complex `if/else`, `switch`, or `goto` structures that obscure the logic. (Note: automated fixing of this is hard, but identification is key).
        6.  **Other Obfuscation:** Any other unusual patterns or anti-tampering techniques.

        Provide your analysis and a step-by-step deobfuscation strategy.
        For each obfuscation type detected, provide:
        -   **Detection:** How you identified it.
        -   **Suggested Action (Python/Regex):** Concrete steps or Python-compatible regular expressions to clean or reverse the obfuscation. Be precise with regex, include capture groups if needed for replacement.
            For renaming, provide `OLD_NAME -> NEW_NAME` pairs.
            For junk code, provide the specific regex to match and remove.
            For string deobfuscation, describe the algorithm or provide a Python snippet if simple.
        -   **Confidence:** (High/Medium/Low)

        If no significant obfuscation is detected, state "No significant obfuscation detected."

        --- FILE CONTENT ---
        {ollama_content}
        --- END FILE CONTENT ---

        Your response should be structured clearly, making it easy for an automated script to parse.
        Example for a regex suggestion:
        ```regex
        ^\\s*_temp\\d+\\s*=\\s*\\d+\\s*[+\\-*\\/]\\s*\\d+;\\s*$
        ```
        Example for renaming:
        ```renames
        OLD_NAME_1 -> NEW_NAME_1
        OLD_NAME_2 -> NEW_NAME_2
        ```
        Example for string decryption (if simple):
        ```python_decrypt_snippet
        def decrypt_string(encrypted_data):
            # Example: simple XOR
            return "".join(chr(ord(c) ^ 0xFF) for c in encrypted_data)
        ```
        """

        ollama_response = ollama_query(deobfuscation_prompt)

        if ollama_response is None:
            logger.error(f"Failed to get Ollama response for {relative_path}. Skipping deobfuscation for this file.")
            return False

        current_content = content
        obfuscation_found_in_file = False

        # --- Process Ollama's Suggestions ---
        logger.info(f"Ollama's analysis for {relative_path}:\n{ollama_response[:1000]}...")

        # 1. File Renaming (Special Case: needs to be done on disk)
        renames_section_match = re.search(r'```renames\n(.*?)\n```', ollama_response, re.DOTALL)
        if renames_section_match:
            rename_suggestions = renames_section_match.group(1).strip().split('\n')
            for rename_line in rename_suggestions:
                parts = rename_line.split(' -> ')
                if len(parts) == 2:
                    old_name_frag = parts[0].strip()
                    new_name_frag = parts[1].strip()
                    # Ensure we are renaming the *current* file
                    if os.path.basename(original_filepath) == old_name_frag:
                        new_filepath = os.path.join(os.path.dirname(original_filepath), new_name_frag)
                        try:
                            os.rename(original_filepath, new_filepath)
                            logger.info(f"Renamed file {os.path.basename(original_filepath)} to {os.path.basename(new_filepath)}")
                            original_filepath = new_filepath # Update the path for subsequent operations
                            obfuscation_found_in_file = True
                            self.state["obfuscation_detected_this_iter"] = True
                            self.state["total_obfuscation_steps"] += 1
                        except Exception as e:
                            logger.warning(f"Could not rename file {original_filepath} to {new_filepath}: {e}")
                    else:
                        logger.debug(f"Ollama suggested renaming {old_name_frag} but current file is {os.path.basename(original_filepath)}. Skipping rename for this file content analysis.")

        # 2. Junk Code Removal / Regex-based cleaning
        regex_matches = re.findall(r'```regex\n(.*?)\n```', ollama_response, re.DOTALL)
        for regex_str in regex_matches:
            try:
                # Add re.MULTILINE for line-by-line matching if applicable
                pattern = re.compile(regex_str, re.MULTILINE)
                new_content = re.sub(pattern, '', current_content)
                if new_content != current_content:
                    logger.info(f"Applied regex removal pattern: '{regex_str}'")
                    current_content = new_content
                    obfuscation_found_in_file = True
                    self.state["obfuscation_detected_this_iter"] = True
                    self.state["total_obfuscation_steps"] += 1
            except re.error as e:
                logger.warning(f"Invalid regex suggested by Ollama: '{regex_str}' - Error: {e}")
            except Exception as e:
                logger.warning(f"Error applying regex '{regex_str}': {e}")

        # 3. String Decryption (if simple and Python snippet provided)
        python_decrypt_snippets = re.findall(r'```python_decrypt_snippet\n(.*?)\n```', ollama_response, re.DOTALL)
        for snippet in python_decrypt_snippets:
            try:
                # This is highly dangerous and requires careful sandboxing in a real scenario.
                # For this example, we'll execute it directly, but **be warned**.
                logger.warning(f"Attempting to execute Python decryption snippet. This is a security risk if the snippet is malicious. Sandbox in production!")
                
                # Create a temporary module/function to execute the snippet
                exec_globals = {}
                exec_locals = {}
                exec(snippet, exec_globals, exec_locals)

                # Now, Ollama should also provide a pattern to find the encrypted strings
                # and how to call the decryption function. This part is complex.
                # Let's assume for now the snippet defines a function like `decrypt_string`.
                if 'decrypt_string' in exec_locals and callable(exec_locals['decrypt_string']):
                    # Ollama would need to tell us how to find encrypted strings.
                    # This is a placeholder for a more complex regex/parsing step.
                    # Example: look for `call compile "encrypted_string"`
                    # Or `_x = "abc".xyz;`
                    
                    # For demonstration, let's assume it identifies patterns like:
                    # `_encrypted = "DEADBEEF";` and applies the function
                    # This requires sophisticated pattern matching *after* the snippet.
                    # This level of automation is extremely difficult with regex only.
                    # A more robust solution would involve AST (Abstract Syntax Tree) analysis.

                    # For now, we'll just log that a decrypt function was identified.
                    # The agent would need another prompt to tell it *how* to use this func.
                    logger.info(f"Decryption function 'decrypt_string' defined by Ollama. Needs further logic to apply.")
                    # Mark as obfuscation found, but it's not fully fixed yet
                    obfuscation_found_in_file = True 
                    self.state["obfuscation_detected_this_iter"] = True
                    self.state["total_obfuscation_steps"] += 1

            except Exception as e:
                logger.warning(f"Error executing Python decryption snippet: {e}")

        # 4. Variable/Function Renaming (simple string replace - dangerous if not careful)
        renames_str_matches = re.search(r'```renames\n(.*?)\n```', ollama_response, re.DOTALL)
        if renames_str_matches:
            rename_lines = renames_str_matches.group(1).strip().split('\n')
            for line in rename_lines:
                try:
                    old_name, new_name = map(str.strip, line.split(' -> '))
                    # Use word boundaries to avoid replacing substrings within other names
                    # This is still very basic and can easily break code. AST is better.
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
                    logger.warning(f"Error applying rename '{line}': {e}")


        # Write the potentially modified content back
        if obfuscation_found_in_file:
            final_output_path = os.path.join(self.deobfuscated_dir, relative_path)
            if write_file_content(final_output_path, current_content):
                logger.info(f"Deobfuscation applied to {relative_path}. Saved to {final_output_path}")
                return True
            else:
                logger.error(f"Failed to save deobfuscated content for {relative_path}.")
                return False
        else:
            logger.info(f"No significant deobfuscation applied to {relative_path} in this iteration.")
            # If no obfuscation was found, copy the original to the deobfuscated dir
            # if not os.path.exists(os.path.join(self.deobfuscated_dir, relative_path)):
            #     shutil.copy2(original_filepath, os.path.join(self.deobfuscated_dir, relative_path))
            return False # Indicate no change for this iteration

    def run(self):
        """Main execution loop for the deobfuscation agent."""
        logger.info("Starting PBO Deobfuscation Agent.")

        # Step 1: Extract PBO
        if not self._extract_pbo():
            logger.critical("Failed to extract PBO. Aborting.")
            self._cleanup_temp_dir()
            return

        # Step 2: Initial scan of extracted files
        if not self._scan_and_prioritize_files(self.temp_extract_dir):
            logger.warning("No files found in extracted PBO. Nothing to deobfuscate.")
            self._cleanup_temp_dir()
            return

        # Copy all files to deobfuscated_dir initially, so we always have a copy
        # and only overwrite if changes are made.
        logger.info(f"Copying initial extracted files to {self.deobfuscated_dir} for processing...")
        shutil.copytree(self.temp_extract_dir, self.deobfuscated_dir, dirs_exist_ok=True)


        # Step 3: Iterative Deobfuscation Loop
        while self.state["current_iteration"] < MAX_DEOBF_ITERATIONS:
            self.state["current_iteration"] += 1
            self.state["obfuscation_detected_this_iter"] = False
            logger.info(f"\n--- Deobfuscation Iteration {self.state['current_iteration']} ---")

            # Re-scan the deobfuscated directory to pick up renamed files etc.
            # We want to process the *latest* version of each file.
            self._scan_and_prioritize_files(self.deobfuscated_dir) 

            for filepath, relative_path, file_type_hint in self.state["files_to_process"]:
                if file_type_hint in ["SQF (Arma Scripting Language)", "C++ Source Code", "Plain Text"]:
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

        self._cleanup_temp_dir()
        logger.info("Agent job done.")

# --- Main Execution ---
if __name__ == "__main__":
    # Example Usage:
    # 1. Create a dummy PBO for testing:
    #    - Create a directory 'test_pbo_content'
    #    - Inside 'test_pbo_content', create 'mission.sqf' with obfuscated content:
    #      ```sqf
    #      // Simple junk code
    #      _temp1 = 1 + 2; _temp2 = _temp1 * 3;
    #      _ = "deadbeef";
    #
    #      // Obfuscated string (example - this is not how SQF strings are usually obfuscated)
    #      _display = call compile ("\x68\x65\x6c\x6c\x6f"); // "hello" in hex
    #
    #      // Simple variable rename
    #      _aJkL_ = 10;
    #      hint str _aJkL_;
    #      ```
    #    - You'll need a PBO packing tool to create the .pbo. For example, using Arma 3 Tools' 'MakePBO.exe' or 'pbo_tools' Python library:
    #      `makepbo.exe test_pbo_content test_pbo.pbo`
    #      OR `pbo_tools.create_pbo(source_dir='test_pbo_content', output_file='test_pbo.pbo')`
    #
    # 2. Make sure Ollama is running and has the specified model downloaded (`ollama pull llama3`).
    # 3. Ensure '7z' is in your system's PATH, or update EXTERNAL_PBO_EXTRACTOR.

    # dummy_pbo_path = "path/to/your/obfuscated_mission.pbo"
    # output_directory = "deobfuscated_output"
    
    # For a quick test, let's try to create a dummy PBO using pbo_tools if available
    dummy_pbo_name = "test_obfuscated.pbo"
    dummy_content_dir = "temp_dummy_pbo_content"
    dummy_output_dir = "deobf_results"

    if USE_PBO_TOOLS_LIB:
        try:
            import pbo_tools
            os.makedirs(dummy_content_dir, exist_ok=True)
            with open(os.path.join(dummy_content_dir, "init.sqf"), "w", encoding="utf-8") as f:
                f.write("""
                // A very simple obfuscation example for testing
                _temp1 = 1 + 2; // Junk code
                _someVar = 10; // Variable to rename

                _obfuscatedString = "";
                for "_i" from 0 to 4 do {
                    _obfuscatedString = _obfuscatedString + toString [97 + _i]; // ASCII for 'abcde'
                };
                hint _obfuscatedString;

                _useless = 20 * 5; // More junk
                private _xYz = "this is a secret"; // Variable to rename
                systemChat _xYz;
                """)
            
            with open(os.path.join(dummy_content_dir, "config.cpp"), "w", encoding="utf-8") as f:
                f.write("""
                class CfgPatches
                {
                    class SomeRandomName_ajsk23 // Rename this
                    {
                        units[] = {};
                        weapons[] = {};
                        requiredVersion = 1.0;
                        requiredAddons[] = {};
                    };
                };
                """)

            pbo_tools.create_pbo(source_dir=dummy_content_dir, output_file=dummy_pbo_name)
            logger.info(f"Dummy PBO '{dummy_pbo_name}' created for testing.")
            # Set the path for the agent
            dummy_pbo_path_for_agent = dummy_pbo_name
            shutil.rmtree(dummy_content_dir) # Clean up source content

        except ImportError:
            logger.warning("pbo_tools library not installed. Cannot create dummy PBO. Please manually create one or install pbo_tools (`pip install pbo_tools`).")
            dummy_pbo_path_for_agent = None
        except Exception as e:
            logger.warning(f"Failed to create dummy PBO with pbo_tools: {e}. Please manually create one.")
            dummy_pbo_path_for_agent = None
    else:
        logger.warning("USE_PBO_TOOLS_LIB is False. Please ensure you have a dummy PBO file ready for testing and set its path below.")
        dummy_pbo_path_for_agent = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/SpawnSystem_Server.pbo" # Replace with your actual PBO path

    if dummy_pbo_path_for_agent and os.path.exists(dummy_pbo_path_for_agent):
        try:
            agent = PBO_Deobfuscator_Agent(dummy_pbo_path_for_agent, dummy_output_dir)
            agent.run()
        except Exception as e:
            logger.critical(f"An error occurred during agent execution: {e}")
            logger.critical("Ensure Ollama is running and the specified model is downloaded.")
            logger.critical("Also, ensure '7z' or your chosen PBO extractor is installed and in PATH.")
    else:
        logger.error("No PBO file specified or found. Aborting.")