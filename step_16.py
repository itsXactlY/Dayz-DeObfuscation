import os
import logging
import sys
from datetime import datetime
from typing import Dict, List

# --- Configuration ---
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
LOG_FILE = "deobfuscator_log.txt"
DEOBF_SCRIPT_FILE = "generated_deobfuscation_script.py"

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

class OllamaClient:
    """Handles interactions with the Ollama API."""
    
    @staticmethod
    def query(prompt: str, model: str = OLLAMA_MODEL, api_url: str = OLLAMA_API_URL) -> str:
        """Sends a query to the Ollama API and returns the response content."""
        headers = {"Content-Type": "application/json"}
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": -1
            }
        }
        try:
            import requests
            response = requests.post(api_url, headers=headers, json=data, timeout=600)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return None

class FileAnalyzer:
    """Provides utilities for analyzing files."""
    
    @staticmethod
    def get_file_type_hint(filepath: str) -> str:
        """Guesses file type based on extension."""
        ext = os.path.splitext(filepath)[1].lower()
        file_types = {
            '.sqf': "SQF/Enforce Script",
            '.fsm': "SQF/Enforce Script",
            '.c': "SQF/Enforce Script",
            '.cpp': "C++ Source Code",
            '.h': "C++ Source Code",
            '.txt': "Plain Text",
            '.log': "Plain Text",
            '.md': "Plain Text",
            '.html': "Plain Text",
            '.xml': "Plain Text",
            '.json': "Plain Text",
            '.paa': "Image File",
            '.jpg': "Image File",
            '.png': "Image File",
            '.tga': "Image File",
            '.dds': "Image File",
            '.p3d': "Model/Material File",
            '.rtm': "Model/Material File",
            '.ebo': "Model/Material File",
            '.rvmat': "Model/Material File"
        }
        return file_types.get(ext, "Unknown/Other")

class DeobfuscationStep:
    """Represents a single deobfuscation step."""
    
    def __init__(self, file_path: str, file_type: str, analysis: str):
        self.file_path = file_path
        self.file_type = file_type
        self.analysis = analysis

class DeobfuscationScriptGenerator:
    """Generates a Python script for deobfuscating files based on analysis results."""
    
    def __init__(self, input_dir: str):
        self.input_dir = input_dir
        self.deobfuscation_steps: List[DeobfuscationStep] = []
        self.script_content: List[str] = []
        
    def analyze_file(self, filepath: str) -> None:
        """Analyzes a file using the Ollama API and stores the deobfuscation step."""
        file_type = FileAnalyzer.get_file_type_hint(filepath)
        relative_path = os.path.relpath(filepath, self.input_dir)
        
        analysis_prompt = f"""
        Analyze this file for obfuscation patterns:
        Path: {relative_path}
        Type: {file_type}
        
        Generate Python code that would:
        1. Detect obfuscated patterns
        2. Generate deobfuscation steps
        3. Provide functions to reverse the obfuscation
        
        Focus on:
        - File/folder name obfuscation
        - String encryption
        - Variable/function name obfuscation
        - Control flow obfuscation
        - Dead code/junk code
        
        Return the analysis as executable Python code.
        """
        
        response = OllamaClient.query(analysis_prompt)
        if response:
            self.deobfuscation_steps.append(DeobfuscationStep(relative_path, file_type, response))

    def _generate_script_header(self) -> None:
        """Generates the header section of the deobfuscation script."""
        self.script_content.extend([
            "#!/usr/bin/env python3",
            "import os",
            "import re",
            "import logging",
            "from typing import Dict, List",
            "",
            "# Deobfuscation Script Generated for PBO Content",
            f"# Generated on: {datetime.now()}",
            "",
            "class PBODeobfuscator:",
            "    def __init__(self, input_dir: str, output_dir: str):",
            "        self.input_dir = input_dir",
            "        self.output_dir = output_dir",
            "        self.logger = logging.getLogger('PBODeobfuscator')",
            "",
            "    def setup_logging(self):",
            "        logging.basicConfig(",
            "            level=logging.INFO,",
            "            format='%(asctime)s - %(levelname)s - %(message)s'",
            "        )",
            ""
        ])

    def _generate_dynamic_analysis_functions(self) -> None:
        """Generates analysis functions based on the results from Ollama API."""
        if not self.deobfuscation_steps:
            logger.warning("No deobfuscation steps found. Using default analysis functions.")
            self.script_content.extend([
                "    def analyze_filename(self, filepath: str) -> Dict:",
                "        filename = os.path.basename(filepath)",
                "        patterns = {",
                "            r'^[a-f0-9]{32}$': 'MD5 hash filename',",
                "            r'^[A-Z0-9_]{20,}$': 'Randomized uppercase name',",
                "            r'^[a-z]{1,2}\\d{6,}$': 'Short prefix with numbers'",
                "        }",
                "        matches = []",
                "        for pattern, desc in patterns.items():",
                "            if re.match(pattern, os.path.splitext(filename)[0]):",
                "                matches.append(desc)",
                "        return {",
                "            'filepath': filepath,",
                "            'is_obfuscated': len(matches) > 0,",
                "            'patterns_found': matches",
                "        }",
                ""
            ])
            return
        
        # Dynamically generate analysis functions based on Ollama responses
        for step in self.deobfuscation_steps:
            func_name = f"analyze_{step.file_path.replace('/', '_').replace('.', '_')}"
            self.script_content.extend([
                f"    def {func_name}(self, filepath: str) -> Dict:",
                "        # Placeholder for dynamic analysis from Ollama API",
                f"        # Analysis for {step.file_path} ({step.file_type}):",
                "        " + "\n        ".join(step.analysis.splitlines()),
                ""
            ])

    def _generate_deobfuscation_functions(self) -> None:
        """Generates generic deobfuscation functions."""
        self.script_content.extend([
            "    def deobfuscate_strings(self, content: str) -> str:",
            "        # Implement string deobfuscation logic here",
            "        return content",
            "",
            "    def remove_junk_code(self, content: str) -> str:",
            "        # Implement junk code removal logic here",
            "        return content",
            "",
            "    def rename_identifiers(self, content: str) -> str:",
            "        # Implement identifier renaming logic here",
            "        return content",
            ""
        ])

    def _generate_main_process(self) -> None:
        """Generates the main deobfuscation process."""
        self.script_content.extend([
            "    def process_file(self, filepath: str) -> None:",
            "        self.logger.info(f'Processing {filepath}')",
            "        # Dynamically call analysis function based on file path",
            "        analysis_func_name = 'analyze_' + filepath.replace('/', '_').replace('.', '_')",
            "        if hasattr(self, analysis_func_name):",
            "            analysis_result = getattr(self, analysis_func_name)(filepath)",
            "            self.logger.info(f'Analysis result: {analysis_result}')",
            "",
            "        # Apply generic deobfuscation steps",
            "        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:",
            "            content = f.read()",
            "",
            "        content = self.deobfuscate_strings(content)",
            "        content = self.remove_junk_code(content)",
            "        content = self.rename_identifiers(content)",
            "",
            "        # Write deobfuscated content",
            "        output_path = os.path.join(self.output_dir, os.path.relpath(filepath, self.input_dir))",
            "        os.makedirs(os.path.dirname(output_path), exist_ok=True)",
            "        with open(output_path, 'w', encoding='utf-8') as f:",
            "            f.write(content)",
            "",
            "    def process_directory(self) -> None:",
            "        self.setup_logging()",
            "        self.logger.info(f'Starting deobfuscation of {self.input_dir}')",
            "",
            "        for root, _, files in os.walk(self.input_dir):",
            "            for file in files:",
            "                filepath = os.path.join(root, file)",
            "                if FileAnalyzer.get_file_type_hint(filepath) in ['SQF/Enforce Script', ",
            "                                                                'C++ Source Code', ",
            "                                                                'Plain Text']:",
            "                    self.process_file(filepath)",
            "",
            "        self.logger.info('Deobfuscation complete')",
            "",
            "if __name__ == '__main__':",
            "    import sys",
            "    if len(sys.argv) != 3:",
            "        print('Usage: python script.py <input_dir> <output_dir>')",
            "        sys.exit(1)",
            "",
            "    deobfuscator = PBODeobfuscator(sys.argv[1], sys.argv[2])",
            "    deobfuscator.process_directory()",
            ""
        ])

    def generate_script(self) -> str:
        """Generates the complete deobfuscation script."""
        self._generate_script_header()
        self._generate_dynamic_analysis_functions()
        self._generate_deobfuscation_functions()
        self._generate_main_process()
        
        return '\n'.join(self.script_content)

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <input_dir> <output_dir>")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

    generator = DeobfuscationScriptGenerator(input_dir)
    
    # Walk through the directory and analyze files
    for root, _, files in os.walk(input_dir):
        for file in files:
            filepath = os.path.join(root, file)
            if FileAnalyzer.get_file_type_hint(filepath) in ['SQF/Enforce Script', 'C++ Source Code', 'Plain Text']:
                generator.analyze_file(filepath)
    
    # Generate and save the deobfuscation script
    script_content = generator.generate_script()
    script_path = os.path.join(output_dir, DEOBF_SCRIPT_FILE)
    os.makedirs(output_dir, exist_ok=True)
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    logger.info(f"Generated deobfuscation script: {script_path}")

if __name__ == "__main__":
    main()