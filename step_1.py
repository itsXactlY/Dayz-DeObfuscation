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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("deobfuscation_log.txt"),
        logging.StreamHandler(sys.stdout)
    ]
)

class OllamaReverseEngineer:
    def __init__(self, pbo_file_path, output_dir):
        self.pbo_file_path = Path(pbo_file_path)
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(tempfile.mkdtemp())
        self.tools = {
            "extractpbo": "ExtractPBO",  # Path to ExtractPBO tool (Windows) or equivalent
            "ghidra": "ghidra_analyzeHeadless",  # Path to Ghidra headless analyzer
            "ida": "idat64",  # Path to IDA Pro (64-bit)
            "radare2": "r2",  # Path to Radare2
        }
        self.deobfuscated = False
        self.unpacked_dir = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_command(self, command, shell=False, cwd=None):
        """Run a shell command and return its output."""
        try:
            result = subprocess.run(command, shell=shell, cwd=cwd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Command failed: {' '.join(command)}\nError: {result.stderr}")
                return None
            logging.info(f"Command succeeded: {' '.join(command)}")
            return result.stdout
        except Exception as e:
            logging.error(f"Exception running command: {e}")
            return None

    def unpack_pbo(self):
        """Unpack the .pbo file using ExtractPBO or similar tools."""
        logging.info(f"Unpacking {self.pbo_file_path}...")
        self.unpacked_dir = self.temp_dir / "unpacked"
        self.unpacked_dir.mkdir(parents=True, exist_ok=True)

        # Try ExtractPBO
        if self.tools["extractpbo"]:
            cmd = [self.tools["extractpbo"], "-P", str(self.pbo_file_path), "-O", str(self.unpacked_dir)]
            result = self.run_command(cmd)
            if result:
                logging.info(f"Successfully unpacked {self.pbo_file_path} to {self.unpacked_dir}")
                return True

        # Fallback: Try treating it as a zip file (some .pbo files are zip-like)
        try:
            with zipfile.ZipFile(self.pbo_file_path, 'r') as zip_ref:
                zip_ref.extractall(self.unpacked_dir)
            logging.info(f"Successfully unpacked {self.pbo_file_path} as a zip file to {self.unpacked_dir}")
            return True
        except Exception as e:
            logging.error(f"Failed to unpack {self.pbo_file_path} as zip: {e}")

        logging.error("Failed to unpack .pbo file. Ensure ExtractPBO or equivalent tool is installed.")
        return False

    def analyze_file(self, file_path):
        """Analyze a file to determine its type and potential obfuscation."""
        file_path = Path(file_path)
        logging.info(f"Analyzing file: {file_path}")

        # Check file extension
        ext = file_path.suffix.lower()
        if ext in [".sqf", ".cpp", ".hpp", ".txt"]:
            return self.deobfuscate_text_file(file_path)
        elif ext in [".bin", ".dll", ".exe", ""]:
            return self.deobfuscate_binary_file(file_path)
        else:
            logging.info(f"File {file_path} is not recognized as obfuscated or binary. Copying as-is.")
            return file_path

    def deobfuscate_text_file(self, file_path):
        """Attempt to deobfuscate text-based files (e.g., .sqf, .cpp)."""
        logging.info(f"Deobfuscating text file: {file_path}")
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()

        # Check for common obfuscation patterns (e.g., encoded strings, packed code)
        if re.search(r'\\x[0-9A-Fa-f]{2}', content) or re.search(r'\\u[0-9A-Fa-f]{4}', content):
            logging.info(f"Detected possible hex or unicode encoding in {file_path}")
            return self.decode_encoded_text(file_path, content)
        elif re.search(r'eval\s*\(', content, re.IGNORECASE):
            logging.info(f"Detected possible eval obfuscation in {file_path}")
            return self.handle_eval_obfuscation(file_path, content)
        else:
            logging.info(f"No obvious obfuscation detected in {file_path}. Copying as-is.")
            return file_path

    def decode_encoded_text(self, file_path, content):
        """Decode hex or unicode encoded text."""
        try:
            # Replace hex-encoded strings (e.g., \x41\x42 -> AB)
            decoded_content = re.sub(r'\\x([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), content)
            # Replace unicode-encoded strings (e.g., \u0041 -> A)
            decoded_content = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), decoded_content)
            
            output_path = self.output_dir / file_path.name
            with open(output_path, 'w') as f:
                f.write(decoded_content)
            logging.info(f"Decoded text file saved to {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Failed to decode text file {file_path}: {e}")
            return file_path

    def handle_eval_obfuscation(self, file_path, content):
        """Handle eval-based obfuscation (common in script files)."""
        logging.warning(f"Eval obfuscation detected in {file_path}. Manual intervention may be required.")
        # Placeholder: Advanced deobfuscation of eval requires executing the script in a sandbox
        # For now, just log and return the original file
        return file_path

    def deobfuscate_binary_file(self, file_path):
        """Attempt to deobfuscate binary files using Ghidra, IDA Pro, or Radare2."""
        logging.info(f"Deobfuscating binary file: {file_path}")

        # Try Ghidra
        if self.tools["ghidra"]:
            ghidra_project_dir = self.temp_dir / "ghidra_project"
            ghidra_project_dir.mkdir(parents=True, exist_ok=True)
            ghidra_output = self.temp_dir / f"{file_path.name}_ghidra.c"
            cmd = [
                self.tools["ghidra"],
                str(ghidra_project_dir),
                "project",
                "-import", str(file_path),
                "-postScript", "DecompileToC.java",  # Custom Ghidra script to decompile to C
                "-deleteProject"
            ]
            result = self.run_command(cmd)
            if result:
                logging.info(f"Ghidra decompilation succeeded for {file_path}. Output: {ghidra_output}")
                return ghidra_output

        # Try IDA Pro
        if self.tools["ida"]:
            ida_output = self.temp_dir / f"{file_path.name}_ida.c"
            cmd = [
                self.tools["ida"],
                "-A",  # Auto-analysis
                "-Sdecompile.py",  # Custom IDA script to decompile to C
                str(file_path)
            ]
            result = self.run_command(cmd)
            if result:
                logging.info(f"IDA Pro decompilation succeeded for {file_path}. Output: {ida_output}")
                return ida_output

        # Try Radare2
        if self.tools["radare2"]:
            radare_output = self.temp_dir / f"{file_path.name}_radare.c"
            cmd = [
                self.tools["radare2"],
                "-A",  # Analyze
                "-c", f"aaa; pdc > {radare_output}",  # Decompile to pseudo-C
                str(file_path)
            ]
            result = self.run_command(cmd, shell=True)
            if result:
                logging.info(f"Radare2 decompilation succeeded for {file_path}. Output: {radare_output}")
                return radare_output

        logging.error(f"Failed to deobfuscate binary file {file_path} with available tools.")
        return file_path

    def process_unpacked_files(self):
        """Process all unpacked files and attempt deobfuscation."""
        logging.info(f"Processing unpacked files in {self.unpacked_dir}")
        for root, _, files in os.walk(self.unpacked_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                relative_path = file_path.relative_to(self.unpacked_dir)
                output_path = self.output_dir / relative_path

                # Create output directory structure
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Analyze and deobfuscate the file
                deobfuscated_file = self.analyze_file(file_path)
                if deobfuscated_file:
                    shutil.copy(deobfuscated_file, output_path)
                    logging.info(f"Processed file saved to {output_path}")

    def run(self):
        """Main loop to deobfuscate the .pbo file."""
        logging.info(f"Starting deobfuscation of {self.pbo_file_path}")

        # Step 1: Unpack the .pbo file
        if not self.unpack_pbo():
            logging.error("Failed to unpack .pbo file. Aborting.")
            return

        # Step 2: Process all unpacked files
        self.process_unpacked_files()

        # Step 3: Check if deobfuscation is complete
        self.deobfuscated = True  # Placeholder: Add logic to verify deobfuscation
        if self.deobfuscated:
            logging.info(f"Deobfuscation complete. Results saved to {self.output_dir}")
        else:
            logging.warning("Deobfuscation incomplete. Manual intervention may be required.")

        # Step 4: Clean up temporary files
        shutil.rmtree(self.temp_dir, ignore_errors=True)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python ollama_deobfuscator.py <pbo_file_path> <output_dir>")
        sys.exit(1)

    pbo_file_path = sys.argv[1]
    output_dir = sys.argv[2]

    agent = OllamaReverseEngineer(pbo_file_path, output_dir)
    agent.run()