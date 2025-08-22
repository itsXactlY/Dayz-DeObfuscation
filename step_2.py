import os
import subprocess
import shutil
import logging
import sys
import time
from pathlib import Path
import zipfile
import re
import tempfile
import json
import base64

# --- Configuration and Setup ---

# Configure logging for persistence and clarity
LOG_FILE = "ollama_deobfuscation.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configuration for external tools (UPDATE THESE PATHS!)
TOOL_CONFIG = {
    # PBO Unpacking Tool (e.g., ExtractPBO for Windows, or pbo_tools for Linux)
    "extract_pbo": "ExtractPBO",  # Example for Windows: "C:\\Tools\\ExtractPBO\\ExtractPBO.exe"
                                 # Example for Linux (if using pbo_tools): "pbo_tools" or full path
    # Ghidra Headless Analyzer
    "ghidra_headless": "ghidra_analyzeHeadless", # Example: "/opt/ghidra/ghidra_10.3.3_PUBLIC/support/analyzeHeadless"
    # IDA Pro (64-bit)
    "ida_pro": "idat64",         # Example: "C:\\Program Files\\IDA Pro 8.3\\idat64.exe"
    # Radare2
    "radare2": "r2",             # Assumes it's in PATH. Example: "/usr/bin/r2"
    # File type identification (optional, uses system 'file' command if available)
    "file_cmd": "file",          # Assumes it's in PATH on Linux/WSL. Windows needs alternatives or Python libraries.
}

# Maximum iterations for the main deobfuscation loop to prevent infinite loops
MAX_DEOBFUSCATION_ITERATIONS = 10

class OllamaReverseEngineer:
    def __init__(self, pbo_file_path: str, output_dir: str):
        self.pbo_file_path = Path(pbo_file_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="pbo_deobf_")).resolve()
        self.tools = TOOL_CONFIG

        # State tracking for the agent
        self.processed_files = set()  # Files that have gone through a deobfuscation attempt
        self.known_obfuscated_files = set() # Files that were identified as obfuscated and need attention
        self.pending_files = set()    # Files newly found or needing re-evaluation
        self.deobfuscation_progress = {} # Store state of deobfuscated files (path: success_status)
        self.iteration_count = 0

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Initialized OllamaReverseEngineer for {self.pbo_file_path}")
        logging.info(f"Output will be saved to: {self.output_dir}")
        logging.info(f"Temporary files in: {self.temp_dir}")

    def run_command(self, command: list, cwd: Path = None, timeout: int = 300) -> (str, str):
        """
        Executes a shell command and captures its output.
        Returns (stdout, stderr) or (None, None) on error/timeout.
        """
        cmd_str = " ".join(command) if isinstance(command, list) else command
        logging.debug(f"Executing command: {cmd_str} in CWD: {cwd or os.getcwd()}")
        try:
            process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='ignore')
            stdout, stderr = process.communicate(timeout=timeout)
            
            if process.returncode != 0:
                logging.error(f"Command failed (Exit Code {process.returncode}): {cmd_str}")
                logging.error(f"STDOUT:\n{stdout}")
                logging.error(f"STDERR:\n{stderr}")
                return None, None
            
            logging.info(f"Command succeeded: {cmd_str}")
            return stdout, stderr
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            logging.error(f"Command timed out after {timeout}s: {cmd_str}")
            logging.error(f"STDOUT (partial):\n{stdout.decode(errors='ignore')}")
            logging.error(f"STDERR (partial):\n{stderr.decode(errors='ignore')}")
            return None, None
        except FileNotFoundError:
            logging.error(f"Command not found: '{command[0]}'. Please check TOOL_CONFIG paths.")
            return None, None
        except Exception as e:
            logging.error(f"Exception while running command '{cmd_str}': {e}")
            return None, None

    def unpack_pbo(self) -> Path | None:
        """
        Unpacks the .pbo file using configured tools.
        Returns the path to the unpacked directory on success, None otherwise.
        """
        logging.info(f"Attempting to unpack {self.pbo_file_path}...")
        unpacked_target_dir = self.temp_dir / self.pbo_file_path.stem
        unpacked_target_dir.mkdir(parents=True, exist_ok=True)

        # Strategy 1: Use ExtractPBO
        if self.tools.get("extract_pbo") and Path(self.tools["extract_pbo"]).exists():
            cmd = [
                str(self.tools["extract_pbo"]),
                "-P",  # Preserve path
                str(self.pbo_file_path),
                "-O",  # Output directory
                str(unpacked_target_dir)
            ]
            stdout, stderr = self.run_command(cmd)
            if stdout:
                logging.info(f"Successfully unpacked {self.pbo_file_path} using ExtractPBO to {unpacked_target_dir}")
                return unpacked_target_dir
            logging.warning(f"ExtractPBO failed for {self.pbo_file_path}. Trying other methods.")
        else:
            logging.warning(f"ExtractPBO tool not found or configured: {self.tools.get('extract_pbo')}")

        # Strategy 2: Try as a ZIP file (some PBOs are just ZIPs with a different extension)
        try:
            if zipfile.is_zipfile(self.pbo_file_path):
                with zipfile.ZipFile(self.pbo_file_path, 'r') as zip_ref:
                    zip_ref.extractall(unpacked_target_dir)
                logging.info(f"Successfully unpacked {self.pbo_file_path} as a ZIP file to {unpacked_target_dir}")
                return unpacked_target_dir
        except Exception as e:
            logging.error(f"Failed to unpack {self.pbo_file_path} as ZIP: {e}")

        logging.error("Failed to unpack .pbo file using any known method. Aborting PBO processing.")
        return None

    def identify_file_type(self, file_path: Path) -> str:
        """
        Identifies the file type using the 'file' command or by extension heuristics.
        Returns a string representing the file type (e.g., "text", "binary", "archive", "unknown").
        """
        # Prioritize 'file' command for accuracy
        if self.tools.get("file_cmd"):
            stdout, _ = self.run_command([self.tools["file_cmd"], "-b", str(file_path)])
            if stdout:
                file_info = stdout.strip().lower()
                if "text" in file_info or "script" in file_info or "ascii" in file_info:
                    return "text"
                elif "executable" in file_info or "elf" in file_info or "pe32" in file_info or "dll" in file_info or "mach-o" in file_info:
                    return "binary"
                elif "archive" in file_info or "zip" in file_info or "gzip" in file_info:
                    return "archive"
                elif "data" in file_info: # Generic data, could be anything
                    return "binary" # Assume binary for further inspection
                return "unknown" # Fallback if file command output is not specific
        
        # Fallback to extension-based heuristics
        ext = file_path.suffix.lower()
        if ext in [".sqf", ".sqm", ".hpp", ".cpp", ".h", ".json", ".txt", ".ini", ".cfg", ".xml"]:
            return "text"
        elif ext in [".exe", ".dll", ".so", ".bin", ".p3d", ".wrp", ".rpt", ".pak", ".ebo"]: # .ebo is often encrypted binary
            return "binary"
        elif ext in [".zip", ".rar", ".7z"]:
            return "archive"
        
        return "unknown"

    def is_obfuscated_text(self, content: str) -> bool:
        """
        Heuristically checks if text content appears obfuscated.
        """
        # Common obfuscation patterns
        if (re.search(r'\\x[0-9A-Fa-f]{2}', content) or      # Hex escapes
            re.search(r'\\u[0-9A-Fa-f]{4}', content) or      # Unicode escapes
            re.search(r'[A-Za-z0-9+/=]{30,}', content) and    # Long base64-like strings (30+ chars)
            re.search(r'eval\s*\(|execute\s*\(|compile\s*\(', content, re.IGNORECASE) or # Script execution functions
            re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b:\d+', content) or # IP:Port often obfuscated
            re.search(r'\b(?!_)\w{1,3}(?!\w)\b', content) and len(content) > 1000 # Many very short variable names, potentially packed
           ):
            return True
        return False

    def deobfuscate_text_file(self, file_path: Path) -> Path | None:
        """
        Attempts to deobfuscate various forms of text-based obfuscation.
        Returns path to deobfuscated file or None if not successful/applicable.
        """
        logging.info(f"Attempting text deobfuscation for: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_content = f.read()

            if not self.is_obfuscated_text(original_content):
                logging.info(f"No obvious text obfuscation found in {file_path}. Copying as-is.")
                shutil.copy(file_path, self.output_dir / file_path.relative_to(self.temp_dir / self.pbo_file_path.stem))
                return file_path

            deobfuscated_content = original_content
            
            # Layer 1: Hex/Unicode/Base64 Decoding
            try:
                # Hex/Unicode escapes
                deobfuscated_content = re.sub(r'\\x([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), deobfuscated_content)
                deobfuscated_content = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), deobfuscated_content)
                
                # Base64 decoding (look for patterns that are likely base64)
                # This is tricky: need to ensure it's actual base64 and not just random characters.
                # A common pattern is 'variable = "base64_string"; eval(decode(variable))'
                
                # Find all potential base64 strings and try to decode them
                # Regex for base64-like strings (multiples of 4, ends with == or =)
                b64_matches = re.findall(r'\"([A-Za-z0-9+/]+={0,2})\"', deobfuscated_content)
                for match in b64_matches:
                    if len(match) % 4 == 0: # Base64 strings are always multiples of 4
                        try:
                            decoded_str = base64.b64decode(match).decode('utf-8', errors='ignore')
                            # Heuristic: If decoded string looks more readable (e.g., contains spaces, common keywords)
                            if ' ' in decoded_str or any(kw in decoded_str.lower() for kw in ['class', 'function', 'return', 'if', 'while']):
                                logging.info(f"Decoded a Base64 string in {file_path}")
                                # Replace only if it makes sense, or log for manual inspection
                                # For now, just print and note. Actual replacement is complex.
                                # deobfuscated_content = deobfuscated_content.replace(match, decoded_str)
                                pass # This replacement is complex and needs context.
                        except Exception:
                            pass # Not valid base64 or other decoding issue

            except Exception as e:
                logging.warning(f"Error during initial decoding for {file_path}: {e}")

            # Layer 2: Eval/Execute/Compile Deobfuscation (requires dynamic analysis or sophisticated static analysis)
            # This is the most challenging part for an automated script.
            # A true "Ollama agent" might spin up a controlled sandbox (e.g., using QEMU, Docker)
            # to execute the script and dump its output after obfuscation is peeled.
            # For this script, we'll note it and perhaps log the eval content.
            eval_matches = re.findall(r'(eval|execute|compile)\s*\((.*?)\)', deobfuscated_content, re.IGNORECASE | re.DOTALL)
            if eval_matches:
                logging.warning(f"Detected eval/execute/compile patterns in {file_path}. This often requires dynamic analysis or specific decompiler for script language.")
                for func, content_to_eval in eval_matches:
                    logging.debug(f"Potential {func} content: {content_to_eval[:200]}...") # Log first 200 chars
                    # In a real setup, you'd integrate a sandbox here
                    # For example, if it's SQF, you'd need an SQF deobfuscator/evaluator.
                    # This cannot be generalized for all script types.

            # Save the currently deobfuscated content
            relative_output_path = file_path.relative_to(self.temp_dir / self.pbo_file_path.stem)
            output_file_path = self.output_dir / relative_output_path
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(deobfuscated_content)
            
            # Re-check for obfuscation after this pass
            if self.is_obfuscated_text(deobfuscated_content):
                logging.warning(f"File {file_path} still appears obfuscated after text deobfuscation. Adding to known_obfuscated_files.")
                self.known_obfuscated_files.add(file_path)
            else:
                logging.info(f"Text deobfuscation for {file_path} seems successful. Saved to {output_file_path}")
                if file_path in self.known_obfuscated_files:
                    self.known_obfuscated_files.remove(file_path)
            
            return output_file_path

        except Exception as e:
            logging.error(f"Error during text file processing for {file_path}: {e}")
            return None

    def deobfuscate_binary_file(self, file_path: Path) -> Path | None:
        """
        Attempts to deobfuscate (decompile) binary files using Ghidra, IDA Pro, or Radare2.
        Returns path to decompiled output (e.g., .c file) or None if unsuccessful.
        """
        logging.info(f"Attempting binary deobfuscation for: {file_path}")
        
        # Define common output paths for decompiled code
        decompiled_c_file = self.output_dir / file_path.relative_to(self.temp_dir / self.pbo_file_path.stem).with_suffix(".c")
        decompiled_c_file.parent.mkdir(parents=True, exist_ok=True)

        # Strategy 1: Ghidra Headless Decompilation
        if self.tools.get("ghidra_headless") and Path(self.tools["ghidra_headless"]).exists():
            logging.info(f"Trying Ghidra for {file_path}...")
            ghidra_project_name = f"{file_path.name}_project"
            ghidra_project_dir = self.temp_dir / "ghidra_projects" / ghidra_project_name
            ghidra_project_dir.mkdir(parents=True, exist_ok=True)

            # Ghidra script to export to C. You'll need to create this script.
            # Example Ghidra script (save as `ExportDecompiledC.java` in Ghidra scripts directory):
            # import ghidra.app.decompiler.DecompInterface;
            # import ghidra.program.model.listing.Function;
            # import ghidra.program.model.listing.Program;
            # import ghidra.util.task.TaskMonitor;
            # import java.io.FileWriter;
            # import java.io.File;
            # import java.util.List;
            #
            # public class ExportDecompiledC extends GhidraScript {
            #     @Override
            #     protected void run() throws Exception {
            #         Program program = getCurrentProgram();
            #         DecompInterface decompiler = new DecompInterface();
            #         decompiler.openProgram(program);
            #         StringBuilder sb = new StringBuilder();
            #         for (Function func : program.getFunctionManager().getFunctions(true)) {
            #             if (monitor.isCancelled()) {
            #                 break;
            #             }
            #             if (!func.isThunk()) {
            #                 sb.append("// Function: ").append(func.getName()).append("\n");
            #                 sb.append("// Address: ").append(func.getEntryPoint()).append("\n");
            #                 try {
            #                     sb.append(decompiler.decompileFunction(func, 0, TaskMonitor.DUMMY).getDecompiledFunction().getC()).append("\n\n");
            #                 } catch (Exception e) {
            #                     sb.append("// Decompilation failed: ").append(e.getMessage()).append("\n\n");
            #                 }
            #             }
            #         }
            #         File outputFile = new File(program.getDomainFile().getParentFolder().getPathname() + File.separator + program.getName() + "_decompiled.c");
            #         try (FileWriter writer = new FileWriter(outputFile)) {
            #             writer.write(sb.toString());
            #             printf("Decompiled C written to: %s\n", outputFile.getAbsolutePath());
            #         }
            #     }
            # }

            ghidra_script_name = "ExportDecompiledC.java" # Make sure this script exists in Ghidra's scripts dir
            
            cmd = [
                str(self.tools["ghidra_headless"]),
                str(ghidra_project_dir.parent),  # Directory containing projects
                ghidra_project_name,             # Project name
                "-import", str(file_path),
                "-analysisPreset", "Default",    # Or "GhidraState" for more robust analysis
                "-postScript", ghidra_script_name, # Script to run after analysis
                "-deleteProject"                 # Clean up the project after export
            ]
            
            # Capture output to find the decompiled file path
            stdout, stderr = self.run_command(cmd, cwd=ghidra_project_dir.parent, timeout=1200) # Increased timeout for Ghidra
            
            if stdout:
                # Ghidra script should print the path to the decompiled file
                match = re.search(r"Decompiled C written to: (.+?_decompiled\.c)", stdout)
                if match:
                    ghidra_output_c = Path(match.group(1))
                    if ghidra_output_c.exists():
                        shutil.copy(ghidra_output_c, decompiled_c_file)
                        logging.info(f"Ghidra decompilation succeeded for {file_path}. Output copied to {decompiled_c_file}")
                        return decompiled_c_file
                    else:
                        logging.error(f"Ghidra reported success but output file not found: {ghidra_output_c}")
                else:
                    logging.error(f"Could not find decompiled C output path in Ghidra logs for {file_path}.")
            logging.warning(f"Ghidra failed for {file_path}. Trying other tools.")
        else:
            logging.warning(f"Ghidra headless tool not found or configured: {self.tools.get('ghidra_headless')}")

        # Strategy 2: IDA Pro Decompilation (requires Hex-Rays decompiler plugin and script)
        if self.tools.get("ida_pro") and Path(self.tools["ida_pro"]).exists():
            logging.info(f"Trying IDA Pro for {file_path}...")
            # IDA script to decompile to C. Save as `ida_decompile_script.py` somewhere accessible.
            # import idc
            # import idaapi
            # import os
            #
            # def decompile_to_c_all_functions(output_path):
            #     if not idaapi.init_hexrays_plugin():
            #         print("Hex-Rays decompiler not available.")
            #         return
            #     
            #     with open(output_path, "w") as f:
            #         for func_ea in idc.get_next_func(0):
            #             f.write(f"// Function: {idc.get_func_name(func_ea)}\n")
            #             f.write(f"// Address: {hex(func_ea)}\n")
            #             try:
            #                 c_code = idaapi.decompile(func_ea)
            #                 if c_code:
            #                     f.write(str(c_code))
            #                 else:
            #                     f.write("// Decompilation failed or no C code generated.\n")
            #             except Exception as e:
            #                 f.write(f"// Error decompiling function: {e}\n")
            #             f.write("\n\n")
            #     print(f"Decompiled C written to: {output_path}")
            #
            # output_file = idc.get_idb_path() + "_decompiled.c"
            # decompile_to_c_all_functions(output_file)
            # idc.qexit(0) # Exit IDA after script execution

            ida_script_path = self.temp_dir / "ida_decompile_script.py" # You'd put the content here
            # Create a dummy script content for demonstration, in reality it should be the actual IDA script
            with open(ida_script_path, 'w') as f:
                f.write(
                    """
import idc
import idaapi
import os

def decompile_to_c_all_functions(output_path):
    if not idaapi.init_hexrays_plugin():
        print("Hex-Rays decompiler not available.")
        return
    
    with open(output_path, "w") as f:
        for func_ea in idc.get_next_func(0):
            if idc.is_func(func_ea):
                f.write(f"// Function: {idc.get_func_name(func_ea)}\n")
                f.write(f"// Address: {hex(func_ea)}\n")
                try:
                    c_code = idaapi.decompile(func_ea)
                    if c_code:
                        f.write(str(c_code))
                    else:
                        f.write("// Decompilation failed or no C code generated.\n")
                except Exception as e:
                    f.write(f"// Error decompiling function: {e}\n")
                f.write("\\n\\n")
    print(f"IDA_DECOMPILE_SUCCESS: Decompiled C written to: {output_path}")

output_file = idc.get_idb_path() + "_decompiled.c"
decompile_to_c_all_functions(output_file)
idc.qexit(0)
"""
                )

            # Ensure IDB is generated in a temp location
            ida_idb_path = self.temp_dir / f"{file_path.name}.idb"
            
            cmd = [
                str(self.tools["ida_pro"]),
                "-A", # Auto-analyze
                f"-L{self.temp_dir / 'ida_log.txt'}", # IDA log file
                f"-o{ida_idb_path}", # Output IDB file
                f"-S{ida_script_path}", # Script to run
                str(file_path)
            ]
            stdout, stderr = self.run_command(cmd, cwd=self.temp_dir, timeout=1200) # Increased timeout for IDA

            if stdout:
                match = re.search(r"IDA_DECOMPILE_SUCCESS: Decompiled C written to: (.+?_decompiled\.c)", stdout)
                if match:
                    ida_output_c = Path(match.group(1))
                    if ida_output_c.exists():
                        shutil.copy(ida_output_c, decompiled_c_file)
                        logging.info(f"IDA Pro decompilation succeeded for {file_path}. Output copied to {decompiled_c_file}")
                        return decompiled_c_file
                    else:
                        logging.error(f"IDA reported success but output file not found: {ida_output_c}")
                else:
                    logging.error(f"Could not find decompiled C output path in IDA logs for {file_path}.")
            logging.warning(f"IDA Pro failed for {file_path}. Trying other tools.")
        else:
            logging.warning(f"IDA Pro tool not found or configured: {self.tools.get('ida_pro')}")

        # Strategy 3: Radare2 Decompilation
        if self.tools.get("radare2") and Path(self.tools["radare2"]).exists():
            logging.info(f"Trying Radare2 for {file_path}...")
            # Radare2 command to analyze and decompile to pseudo-C
            radare2_output_file = self.temp_dir / f"{file_path.name}_r2_decompiled.c"
            # Using shell=True for complex r2 commands with pipes/redirection
            cmd = [
                str(self.tools["radare2"]),
                "-q", "-c", f"aaa; pdc > {radare2_output_file}", # Analyze all, then print decompiled C to file
                str(file_path)
            ]
            # Radare2 can be verbose, sometimes its output goes to stderr for progress.
            # We care about the output file it generates.
            stdout, stderr = self.run_command(cmd, timeout=600) # Shorter timeout for Radare2 typically

            if radare2_output_file.exists() and radare2_output_file.stat().st_size > 0:
                shutil.copy(radare2_output_file, decompiled_c_file)
                logging.info(f"Radare2 decompilation succeeded for {file_path}. Output copied to {decompiled_c_file}")
                return decompiled_c_file
            logging.warning(f"Radare2 failed or produced empty output for {file_path}.")
        else:
            logging.warning(f"Radare2 tool not found or configured: {self.tools.get('radare2')}")

        logging.error(f"Failed to deobfuscate (decompile) binary file {file_path} with all available tools.")
        return None

    def process_file(self, file_path: Path):
        """
        Orchestrates the deobfuscation attempt for a single file.
        Updates internal state based on success/failure.
        """
        if file_path in self.processed_files:
            logging.debug(f"Skipping already processed file: {file_path}")
            return

        logging.info(f"Processing: {file_path} (Iteration {self.iteration_count})")
        original_relative_path = file_path.relative_to(self.temp_dir / self.pbo_file_path.stem)
        final_output_path = self.output_dir / original_relative_path

        file_type = self.identify_file_type(file_path)
        deobfuscated_output_path = None

        if file_type == "text":
            deobfuscated_output_path = self.deobfuscate_text_file(file_path)
        elif file_type == "binary":
            deobfuscated_output_path = self.deobfuscate_binary_file(file_path)
        elif file_type == "archive":
            logging.info(f"Detected nested archive: {file_path}. Attempting to unpack.")
            nested_unpacked_dir = self.temp_dir / f"{file_path.name}_nested"
            nested_unpacked_dir.mkdir(exist_ok=True)
            try:
                if zipfile.is_zipfile(file_path):
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(nested_unpacked_dir)
                    logging.info(f"Successfully unpacked nested archive {file_path}. Adding contents to pending_files.")
                    for root, _, files in os.walk(nested_unpacked_dir):
                        for f in files:
                            self.pending_files.add(Path(root) / f)
                    deobfuscated_output_path = file_path # Indicate it was processed (unpacked)
                else:
                    logging.warning(f"Cannot unpack nested archive {file_path} (not a standard ZIP). Copying as-is.")
                    shutil.copy(file_path, final_output_path)
                    deobfuscated_output_path = file_path
            except Exception as e:
                logging.error(f"Failed to unpack nested archive {file_path}: {e}")
                shutil.copy(file_path, final_output_path) # Copy original if unpacking fails
                deobfuscated_output_path = file_path

        else: # "unknown" or other types
            logging.info(f"Unknown or non-actionable file type for {file_path}. Copying as-is.")
            final_output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(file_path, final_output_path)
            deobfuscated_output_path = file_path

        self.processed_files.add(file_path)

        if deobfuscated_output_path:
            self.deobfuscation_progress[file_path] = True
        else:
            self.deobfuscation_progress[file_path] = False
            self.known_obfuscated_files.add(file_path) # Mark for potential re-evaluation

    def check_remaining_obfuscation(self):
        """
        Re-scans files in the output directory to see if any still look obfuscated.
        This is part of the "shall not stop" mechanism.
        """
        newly_obfuscated_files = set()
        for root, _, files in os.walk(self.output_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                if file_path.suffix.lower() in [".sqf", ".cpp", ".txt", ".hpp"]: # Only re-check text files
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if self.is_obfuscated_text(content):
                                newly_obfuscated_files.add(file_path)
                    except Exception as e:
                        logging.warning(f"Could not read {file_path} for re-checking obfuscation: {e}")
        
        # Add newly found obfuscated files (from output_dir) to pending for another pass
        # This is where the iterative refinement happens.
        for f in newly_obfuscated_files:
            # Only add if it hasn't been recently processed AND is still obfuscated
            if f not in self.known_obfuscated_files: # And not in current pending
                self.known_obfuscated_files.add(f)
                self.pending_files.add(f) # Add back to pending for another pass

        if len(newly_obfuscated_files) > 0:
            logging.info(f"Found {len(newly_obfuscated_files)} files still exhibiting obfuscation patterns in output. Will re-attempt.")
            return True
        else:
            logging.info("No further obvious obfuscation patterns detected in output files.")
            return False

    def run(self):
        """
        Main execution loop for the Ollama Reverse Engineering Agent.
        It orchestrates the entire deobfuscation process, iterating until "done".
        """
        logging.info(f"Starting deobfuscation of {self.pbo_file_path}...")

        # Step 1: Initial PBO Unpacking
        unpacked_root = self.unpack_pbo()
        if not unpacked_root:
            logging.critical("Initial PBO unpacking failed. Cannot proceed.")
            self.cleanup()
            return

        # Populate initial pending files
        for root, _, files in os.walk(unpacked_root):
            for file_name in files:
                self.pending_files.add(Path(root) / file_name)

        logging.info(f"Initial files to process: {len(self.pending_files)}")
        
        # Step 2: Iterative Deobfuscation Loop (the "shall not stop until done" part)
        while self.pending_files and self.iteration_count < MAX_DEOBFUSCATION_ITERATIONS:
            self.iteration_count += 1
            logging.info(f"\n--- Starting Deobfuscation Iteration {self.iteration_count} ---")
            
            current_pending = list(self.pending_files)
            self.pending_files.clear() # Clear for next iteration

            files_processed_in_this_iteration = 0
            for file_path in current_pending:
                self.process_file(file_path)
                files_processed_in_this_iteration += 1

            logging.info(f"Iteration {self.iteration_count} processed {files_processed_in_this_iteration} files.")

            # After processing current batch, re-evaluate the output directory for remaining obfuscation
            # This is crucial for multi-layered obfuscation or nested structures.
            if not self.check_remaining_obfuscation() and not self.pending_files:
                # If no new obfuscated files found and no pending files from nested archives, we might be done.
                logging.info("No more new obfuscated patterns found and no pending files. Considering job done for now.")
                break
            
            if not self.pending_files and self.known_obfuscated_files:
                logging.info(f"All current pending files processed. {len(self.known_obfuscated_files)} files still appear obfuscated. Retrying a new pass on these.")
                # Add known obfuscated files back to pending for another attempt, if they haven't been successfully processed
                for f in self.known_obfuscated_files.copy(): # Iterate on a copy as set might change
                    if not self.deobfuscation_progress.get(f, False): # If not marked as successfully deobfuscated
                        self.pending_files.add(f)
                        logging.debug(f"Re-adding {f} to pending queue for another pass.")

            if not self.pending_files and self.iteration_count < MAX_DEOBFUSCATION_ITERATIONS:
                logging.info("No more files in pending queue. Re-scanning entire output directory for deeper obfuscation...")
                # A full re-scan might reveal something if nested archives were extracted in previous pass
                self.check_remaining_obfuscation()
                if not self.pending_files and self.known_obfuscated_files:
                    logging.info("Still identified obfuscated files, but no new progress after re-scan. Agent might be stuck or requires manual intervention.")
                    break # Break if we can't make progress anymore

        if self.iteration_count >= MAX_DEOBFUSCATION_ITERATIONS:
            logging.warning(f"Maximum deobfuscation iterations ({MAX_DEOBFUSCATION_ITERATIONS}) reached. Some files might still be obfuscated.")
        
        logging.info(f"Deobfuscation process finished. Results are in: {self.output_dir}")
        self.cleanup()
        logging.info("Temporary files cleaned up.")

    def cleanup(self):
        """Cleans up temporary directories."""
        if self.temp_dir.exists():
            logging.info(f"Cleaning up temporary directory: {self.temp_dir}")
            try:
                shutil.rmtree(self.temp_dir)
            except OSError as e:
                logging.error(f"Error removing temporary directory {self.temp_dir}: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python ollama_deobfuscator.py <pbo_file_path> <output_directory>")
        sys.exit(1)

    pbo_file = sys.argv[1]
    output_dir = sys.argv[2]

    # Check if input PBO exists
    if not Path(pbo_file).is_file():
        logging.critical(f"Input PBO file not found: {pbo_file}")
        sys.exit(1)

    # Instantiate and run the agent
    agent = OllamaReverseEngineer(pbo_file, output_dir)
    try:
        agent.run()
    except Exception as e:
        logging.critical(f"An unhandled critical error occurred during deobfuscation: {e}", exc_info=True)
    finally:
        agent.cleanup() # Ensure cleanup even if errors occur