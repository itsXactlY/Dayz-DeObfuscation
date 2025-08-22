import os
import shutil
import subprocess
import json
import logging
import re
import sys
import time
from datetime import datetime
import difflib

# --- Configuration ---
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
LOG_FILE = "deobfuscator_log.txt"
MAX_DEOBF_ITERATIONS = 5
PROOF_REPORT_FILE = "deobfuscation_proof_report.txt"
DEOBF_SCRIPT_FILE = "generated_deobfuscation_script.py"

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

def ollama_query(prompt, model=OLLAMA_MODEL, api_url=OLLAMA_API_URL):
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

def get_file_type_hint(filepath):
    """Guesses file type based on extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.sqf', '.fsm', '.c']:
        return "SQF/Enforce Script"
    elif ext in ['.cpp', '.h']:
        return "C++ Source Code"
    elif ext in ['.txt', '.log', '.md', '.html', '.xml', '.json']:
        return "Plain Text"
    elif ext in ['.paa', '.jpg', '.png', '.tga', '.dds']:
        return "Image File"
    elif ext in ['.p3d', '.rtm', '.ebo', '.rvmat']:
        return "Model/Material File"
    else:
        return "Unknown/Other"

class DeobfuscationScriptGenerator:
    def __init__(self, input_dir):
        self.input_dir = input_dir
        self.deobfuscation_steps = []
        self.script_content = []
        
    def analyze_file(self, filepath):
        """Analyzes a file and generates deobfuscation steps."""
        file_type = get_file_type_hint(filepath)
        relative_path = os.path.relpath(filepath, self.input_dir)
        
        # Generate analysis prompt for Ollama
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
        
        response = ollama_query(analysis_prompt)
        if response:
            self.deobfuscation_steps.append({
                'file': relative_path,
                'type': file_type,
                'analysis': response
            })

    def generate_script_header(self):
        """Generates the header section of the deobfuscation script."""
        self.script_content.extend([
            "#!/usr/bin/env python3",
            "import os",
            "import re",
            "import logging",
            "from typing import Dict, List, Tuple",
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

    def generate_analysis_functions(self):
        """Generates the analysis and detection functions."""
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
            "",
            "    def analyze_content(self, filepath: str) -> Dict:",
            "        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:",
            "            content = f.read()",
            "",
            "        patterns = {",
            "            'string_encryption': [",
            "                r'decrypt\\([\"\']([^\"\']+)[\"\'](?:,\\s*[^)]+)?\\)',",
            "                r'StringDecoder\\.decode\\([\"\']([^\"\']+)[\"\'](?:,\\s*[^)]+)?\\)'",
            "            ],",
            "            'junk_code': [",
            "                r'_[a-zA-Z0-9]+\\s*=\\s*[0-9]+\\s*[+\\-*/]\\s*[0-9]+;',",
            "                r'if\\s*\\([^)]+\\)\\s*{\\s*}\\s*else\\s*{\\s*}'",
            "            ],",
            "            'obfuscated_names': [",
            "                r'\\b[a-zA-Z][a-zA-Z0-9]{30,}\\b',",
            "                r'\\b[A-Z0-9]{32}\\b'",
            "            ]",
            "        }",
            "",
            "        results = {category: [] for category in patterns}",
            "        for category, pattern_list in patterns.items():",
            "            for pattern in pattern_list:",
            "                matches = re.finditer(pattern, content)",
            "                for match in matches:",
            "                    results[category].append({",
            "                        'match': match.group(0),",
            "                        'position': match.span()",
            "                    })",
            "",
            "        return results",
            ""
        ])

    def generate_deobfuscation_functions(self):
        """Generates the deobfuscation functions."""
        self.script_content.extend([
            "    def deobfuscate_strings(self, content: str, patterns: List[Dict]) -> str:",
            "        def decrypt_string(encrypted: str, key: str = None) -> str:",
            "            # Placeholder for actual decryption logic",
            "            # This should be customized based on the actual encryption used",
            "            return f'DECRYPTED_{encrypted}'",
            "",
            "        modified_content = content",
            "        for pattern in patterns:",
            "            match = pattern['match']",
            "            # Extract the encrypted string and decrypt it",
            "            encrypted = re.search(r'[\"\']([^\"\']+)[\"\']', match)",
            "            if encrypted:",
            "                decrypted = decrypt_string(encrypted.group(1))",
            "                modified_content = modified_content.replace(match, f'\"{decrypted}\"')",
            "        return modified_content",
            "",
            "    def remove_junk_code(self, content: str, patterns: List[Dict]) -> str:",
            "        modified_content = content",
            "        for pattern in patterns:",
            "            modified_content = modified_content.replace(pattern['match'], '')",
            "        return modified_content",
            "",
            "    def rename_identifiers(self, content: str, patterns: List[Dict]) -> str:",
            "        modified_content = content",
            "        for pattern in patterns:",
            "            obfuscated_name = pattern['match']",
            "            # Generate a meaningful name based on context",
            "            new_name = f'deobfuscated_{hash(obfuscated_name) % 1000}'",
            "            modified_content = re.sub(r'\\b' + re.escape(obfuscated_name) + r'\\b',",
            "                                     new_name, modified_content)",
            "        return modified_content",
            ""
        ])

    def generate_main_process(self):
        """Generates the main deobfuscation process."""
        self.script_content.extend([
            "    def process_file(self, filepath: str) -> None:",
            "        self.logger.info(f'Processing {filepath}')",
            "        # Analyze filename",
            "        filename_analysis = self.analyze_filename(filepath)",
            "        if filename_analysis['is_obfuscated']:",
            "            new_name = f'deobfuscated_{os.path.basename(filepath)}'",
            "            self.logger.info(f'Renaming {filepath} to {new_name}')",
            "",
            "        # Analyze and deobfuscate content",
            "        content_analysis = self.analyze_content(filepath)",
            "        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:",
            "            content = f.read()",
            "",
            "        # Apply deobfuscation steps",
            "        if content_analysis['string_encryption']:",
            "            content = self.deobfuscate_strings(content, ",
            "                                              content_analysis['string_encryption'])",
            "",
            "        if content_analysis['junk_code']:",
            "            content = self.remove_junk_code(content, ",
            "                                           content_analysis['junk_code'])",
            "",
            "        if content_analysis['obfuscated_names']:",
            "            content = self.rename_identifiers(content, ",
            "                                             content_analysis['obfuscated_names'])",
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
            "                if get_file_type_hint(filepath) in ['SQF/Enforce Script', ",
            "                                                    'C++ Source Code', ",
            "                                                    'Plain Text']:",
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

    def generate_script(self):
        """Generates the complete deobfuscation script."""
        self.generate_script_header()
        self.generate_analysis_functions()
        self.generate_deobfuscation_functions()
        self.generate_main_process()
        
        return '\n'.join(self.script_content)


def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <input_dir> <output_dir>")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

    # Create script generator
    generator = DeobfuscationScriptGenerator(input_dir)
    
    # Generate the deobfuscation script
    script_content = generator.generate_script()
    
    # Write the script to file
    script_path = os.path.join(output_dir, DEOBF_SCRIPT_FILE)
    os.makedirs(output_dir, exist_ok=True)
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    logger.info(f"Generated deobfuscation script: {script_path}")

if __name__ == "__main__":
    main()