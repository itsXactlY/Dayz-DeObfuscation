import os
import re
import asyncio
import aiohttp
import json
import shutil
from pathlib import Path

class FolderDeobfuscator:
    def __init__(self, input_folder: str, output_folder: str, ollama_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.ollama_url = ollama_url
        self.model = model
        self.session = None
        self.processed_files = 0
        self.total_files = 0

    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()

    def extract_and_filter_identifiers(self, content: str) -> list:
        patterns = [
            r'\b[A-Za-z][A-Za-z0-9_]{4,}\b',
            r'([A-Za-z][A-Za-z0-9_]{4,})\s*\(',
            r'\.([A-Za-z][A-Za-z0-9_]{4,})\s*\(',
        ]
        identifiers = set()
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    identifiers.update(match)
                else:
                    identifiers.add(match)
        
        obfuscated = []
        common_words = {'return', 'if', 'else', 'static', 'int', 'ref', 'class', 'void', 'string', 'bool', 'float', 'double'}
        for identifier in identifiers:
            if (len(identifier) > 5 and
                identifier not in common_words and
                self.looks_obfuscated(identifier)):
                obfuscated.append(identifier)
        return obfuscated

    def looks_obfuscated(self, identifier: str) -> bool:
        indicators = [
            len(identifier) > 10,
            sum(1 for c in identifier if c.isupper()) > len(identifier) * 0.3,
            sum(1 for c in identifier if c.islower()) > len(identifier) * 0.3,
            len(set(identifier)) > len(identifier) * 0.6,
        ]
        return sum(indicators) >= 2

    async def get_ml_suggestions(self, content: str, identifiers: list) -> dict:
        if not identifiers:
            return {}

        await self.init_session()
        prompt = f"""You are an expert code deobfuscator for DayZ mod code (Enfusion Script/C++). Analyze this specific code snippet and suggest concise, meaningful names for the obfuscated identifiers based on context, DayZ conventions, and common programming patterns.

Code snippet:
{content}

Obfuscated identifiers to rename:
{', '.join(identifiers)}

Respond only in JSON format:
{{
    "obfuscated_name1": "meaningful_name1",
    "obfuscated_name2": "meaningful_name2"
}}
"""
        
        try:
            async with self.session.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "top_p": 0.9}
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    response_text = result.get('response', '')
                    try:
                        json_start = response_text.find('{')
                        json_end = response_text.rfind('}') + 1
                        if json_start >= 0:
                            return json.loads(response_text[json_start:json_end])
                    except json.JSONDecodeError:
                        print("Failed to parse JSON response")
        except Exception as e:
            print(f"Error during ML call: {e}")
        
        return {}

    def apply_mappings(self, content: str, mappings: dict) -> str:
        result = content
        for obfuscated, meaningful in mappings.items():
            if meaningful and meaningful != obfuscated:
                pattern = rf'\b{re.escape(obfuscated)}\b'
                result = re.sub(pattern, meaningful, result)
        return result

    async def process_file(self, file_path: str, relative_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # Skip if file is empty or too small
            if len(content.strip()) < 10:
                return

            print(f"\nProcessing: {relative_path}")
            
            identifiers = self.extract_and_filter_identifiers(content)
            if identifiers:
                print(f"Found {len(identifiers)} obfuscated identifiers")
                mappings = await self.get_ml_suggestions(content, identifiers)
                if mappings:
                    print(f"Generated {len(mappings)} mappings")
                    deobfuscated = self.apply_mappings(content, mappings)
                else:
                    deobfuscated = content
            else:
                deobfuscated = content

            # Create output directory structure
            output_path = os.path.join(self.output_folder, relative_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write deobfuscated content
            with open(output_path, 'w', encoding='utf-8') as file:
                file.write(deobfuscated)

            self.processed_files += 1
            print(f"Progress: {self.processed_files}/{self.total_files} files")

        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    async def process_folder(self):
        # Count total files first
        for root, _, files in os.walk(self.input_folder):
            for file in files:
                if file.endswith(('.c', '.cpp', '.h', '.hpp', '.cs', '.sqf', '.c++', '.cc')):
                    self.total_files += 1

        # Create output folder
        os.makedirs(self.output_folder, exist_ok=True)

        # Process all files
        tasks = []
        for root, _, files in os.walk(self.input_folder):
            for file in files:
                if file.endswith(('.c', '.cpp', '.h', '.hpp', '.cs', '.sqf', '.c++', '.cc')):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.input_folder)
                    tasks.append(self.process_file(file_path, relative_path))

        await asyncio.gather(*tasks)

# Main execution
async def main():
    input_folder = "/home/alca/Schreibtisch/test/AdvancedGroups_Server_latest/"  # Replace with your input folder path
    output_folder = "/home/alca/Schreibtisch/test/AdvancedGroups_Server_latest_algoclean"  # Replace with your output folder path
    
    deobfuscator = FolderDeobfuscator(input_folder, output_folder)
    try:
        print(f"Starting deobfuscation of folder: {input_folder}")
        await deobfuscator.process_folder()
        print("\nDeobfuscation complete!")
        print(f"Processed {deobfuscator.processed_files} files")
        print(f"Output folder: {output_folder}")
    finally:
        await deobfuscator.close_session()

if __name__ == "__main__":
    asyncio.run(main())
