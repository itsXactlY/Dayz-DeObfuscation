import re
import asyncio
import aiohttp
import json
import time  # For adding delays in retries

class CodeDeobfuscatorAlgorithm:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.1:8b", max_retries: int = 10, initial_retry_delay: int = 10):
        self.ollama_url = ollama_url  # Ollama API endpoint
        self.model = model  # LLM model to use
        self.session = None  # HTTP session for API calls
        self.max_retries = max_retries  # Maximum number of retries (increased to 10)
        self.initial_retry_delay = initial_retry_delay  # Initial delay in seconds (increased to 10)
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    def extract_and_filter_identifiers(self, content: str) -> list:
        # Extract potential identifiers from the code
        patterns = [
            r'\b[A-Za-z][A-Za-z0-9_]{4,}\b',  # General identifiers
            r'([A-Za-z][A-Za-z0-9_]{4,})\s*\(',  # Function/method calls
            r'\.([A-Za-z][A-Za-z0-9_]{4,})\s*\(',  # Method calls
        ]
        identifiers = set()
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    identifiers.update(match)  # Handle tuple results
                else:
                    identifiers.add(match)
        
        # Filter for identifiers that look obfuscated
        obfuscated = []
        common_words = {'return', 'if', 'else', 'static', 'int', 'ref', 'class'}  # Common non-obfuscated words
        for identifier in identifiers:
            if (len(identifier) > 5 and  # Longer than 5 characters
                identifier not in common_words and
                self.looks_obfuscated(identifier)):
                obfuscated.append(identifier)
        return obfuscated  # Return list of obfuscated identifiers
    
    def looks_obfuscated(self, identifier: str) -> bool:
        # Heuristic to determine if an identifier is likely obfuscated
        indicators = [
            len(identifier) > 10,  # Very long name
            sum(1 for c in identifier if c.isupper()) > len(identifier) * 0.3,  # High uppercase ratio
            sum(1 for c in identifier if c.islower()) > len(identifier) * 0.3,  # Mixed case
            len(set(identifier)) > len(identifier) * 0.6,  # High character diversity
        ]
        return sum(indicators) >= 2  # At least 2 indicators must be true
    
    async def get_ml_suggestions(self, content: str, identifiers: list) -> dict:
        await self.init_session()
        prompt = f"""You are an expert code deobfuscator for DayZ mod code (Enfusion Script/C++). Analyze this specific code snippet and suggest concise, meaningful names for the obfuscated identifiers based on context, DayZ conventions (e.g., IsMultiplayer, GetMission, logical understandable strings in general), and common programming patterns.

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
        
        for attempt in range(1, self.max_retries + 1):
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
                                mappings = json.loads(response_text[json_start:json_end])
                                print(f"Successfully got ML suggestions on attempt {attempt}!")
                                return mappings  # Return successful mappings
                        except json.JSONDecodeError:
                            print(f"Attempt {attempt}: Failed to parse JSON response. Retrying...")
                    else:
                        print(f"Attempt {attempt}: API request failed with status {response.status}. Retrying...")
            except Exception as e:
                print(f"Attempt {attempt}: Error during ML call - {e}. Retrying...")
            
            if attempt < self.max_retries:
                delay = self.initial_retry_delay * (2 ** (attempt - 1))  # Exponential backoff: 10s, 20s, 40s, etc.
                print(f"Retrying in {delay} seconds... (Attempt {attempt} failed)")
                await asyncio.sleep(delay)  # Wait with exponential backoff
        
        print(f"All {self.max_retries} attempts failed. Falling back to heuristics.")
        return {}  # All retries failed, return empty for fallback
    
    def create_fallback_mappings(self, identifiers: list) -> dict:
        # Simple fallback: Generate generic names if ML fails
        mappings = {}
        for idx, identifier in enumerate(identifiers, 1):
            mappings[identifier] = f"UnknownObject{idx}"  # E.g., UnknownObject1
        return mappings
    
    def apply_mappings(self, content: str, mappings: dict) -> str:
        # Apply the mappings to the code content
        result = content
        for obfuscated, meaningful in mappings.items():
            if meaningful and meaningful != obfuscated:
                pattern = rf'\b{re.escape(obfuscated)}\b'  # Use word boundaries for safe replacement
                result = re.sub(pattern, meaningful, result)
        return result
    
    async def run_deobfuscation(self):
        # Hardcoded code snippet to deobfuscate
        obfuscated_snippet = """
        class cHfENVfRPzKyJXBuxnz { static int NeYezhNIBCYplWG() { if (!AfrzZUctcucNjQkvIAA().IsMultiplayer()) return 1; if (AfrzZUctcucNjQkvIAA().IsClient()) { LTXpSFmSkatmzOKnDZM fgptyDuRuewGdCps = khcvEOGvbYurSEsMtQ.asEsJWEBxVifZPReWTd; if (fgptyDuRuewGdCps) { ref DXOlBuzveQrnsAlUGfHM WClEHQgWLyrJgrAZh = fgptyDuRuewGdCps.asEsJWEBxVifZPReWTd; if (WClEHQgWLyrJgrAZh) { return WClEHQgWLyrJgrAZh.prWSpdaVXepJJMArnq(); }} } else if (AfrzZUctcucNjQkvIAA().IsServer()) { KXkHsemBMWGbhbceB ZzTuAJkRReSMEzmnIg = KXkHsemBMWGbhbceB.Cast(AfrzZUctcucNjQkvIAA().GetMission()); if (ZzTuAJkRReSMEzmnIg == dhSOiaCmRInzlSCdrHqn) return -1; return ZzTuAJkRReSMEzmnIg.sntwxxdOBLLflUevhaqv.prWSpdaVXepJJMArnq(); } return -1; }}
        """
        
        print("Starting deobfuscation of the specific code snippet...")
        
        identifiers = self.extract_and_filter_identifiers(obfuscated_snippet)
        if not identifiers:
            print("No obfuscated identifiers found.")
            return obfuscated_snippet
        
        print(f"Obfuscated identifiers detected: {identifiers}")
        
        # Get ML suggestions with retries and exponential backoff
        mappings = await self.get_ml_suggestions(obfuscated_snippet, identifiers)
        
        if not mappings:  # Use fallback if ML still failed after retries
            print("Falling back to heuristic mappings.")
            mappings = self.create_fallback_mappings(identifiers)
        
        print(f"Final mappings: {mappings}")
        
        # Apply mappings to get deobfuscated code
        deobfuscated_code = self.apply_mappings(obfuscated_snippet, mappings)
        
        print("Deobfuscated Code:\n")
        return deobfuscated_code

# Main execution
async def main():
    deobfuscator = CodeDeobfuscatorAlgorithm()
    try:
        deobfuscated_result = await deobfuscator.run_deobfuscation()
        print(deobfuscated_result)  # Output the deobfuscated code
    finally:
        await deobfuscator.close_session()

# Run the script
asyncio.run(main())