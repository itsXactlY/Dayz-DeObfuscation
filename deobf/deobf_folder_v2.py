import re
import asyncio
import aiohttp
import json
import time
import os

class CodeDeobfuscatorAlgorithm:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.1:8b", max_retries: int = 10, initial_retry_delay: int = 10):
        self.ollama_url = ollama_url
        self.model = model
        self.session = None
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    def extract_and_filter_identifiers(self, content: str) -> list:
        # Extract potential identifiers from the code
        patterns = [
            r'\b[A-Za-z][A-Za-z0-9_]{4,}\b',  # General identifiers (at least 5 chars)
            r'([A-Za-z][A-Za-z0-9_]{4,})\s*\(',  # Function/method calls (capturing the name)
            r'\.([A-Za-z][A-Za-z0-9_]{4,})\s*\(',  # Method calls (capturing the name after dot)
        ]
        identifiers = set()
        for pattern in patterns:
            matches = re.findall(pattern, content) 
            for match in matches:
                if isinstance(match, tuple):
                    identifiers.update(match)
                else:
                    identifiers.add(match)
        
        # Filter for identifiers that look obfuscated
        obfuscated = []
        # Expanded common words for better filtering of non-obfuscated terms
        # This list covers common C++/Enfusion Script keywords and frequently used engine functions/classes.
        common_words = {
            'return', 'if', 'else', 'static', 'int', 'ref', 'class', 'void', 'bool',
            'string', 'float', 'private', 'protected', 'public', 'enum', 'true', 'false',
            'null', 'this', 'super', 'new', 'delete', 'const', 'typename', 'typedef',
            'while', 'for', 'switch', 'case', 'break', 'continue', 'default', 'try',
            'catch', 'finally', 'throw', 'using', 'namespace', 'struct', 'union',
            'virtual', 'override', 'abstract', 'interface', 'template', 'operator',
            # DayZ/Enfusion specific (lowercase for better matching)
            'getgame', 'getmission', 'ismultiplayer', 'isserver', 'isclient', 'cast',
            'dayzplayer', 'playerbase', 'itembase', 'enablesimulation', 'disabledamage',
            'eventhandler', 'scriptcall', 'scriptmodule', 'scriptdata', 'scriptrpc',
            'gettime', 'getpos', 'setpos', 'getorientation', 'setorientation',
            'createobject', 'deleteobject', 'spawnentity', 'unregister', 'register',
            'input', 'output', 'vector', 'array', 'map', 'set', 'config', 'modulename',
            'gettype', 'settype', 'getname', 'setname', 'isenabled', 'setenabled',
            'override', 'overridefn', 'call', 'member', 'variable', 'function',
            'scope', 'param', 'params', 'register', 'unregister', 'log', 'debug',
            'error', 'warning', 'info', 'getinstance', 'setinstance', 'getchild',
            'getparent', 'find', 'findall', 'add', 'remove', 'clear', 'count', 'size',
            'isempty', 'notnull', 'check', 'init', 'update', 'destroy', 'postinit',
            'preinit', 'onupdate', 'onload', 'onsave', 'onconnect', 'ondisconnect',
            'onplayerconnect', 'onplayerdisconnect', 'onrespawn', 'onspawn', 'damage',
            'hit', 'killed', 'killedby', 'sethealth', 'gethealth', 'isalive', 'isdead',
            'issurvivor', 'isenemy', 'isfriendly', 'isinfected', 'setinfected',
            'getstate', 'setstate', 'getvelocity', 'setvelocity', 'getspeed', 'setspeed',
            'getdirection', 'setdirection', 'getrotation', 'setrotation', 'getscale',
            'setscale', 'setview', 'getview', 'getcamera', 'setcamera', 'getlight',
            'setlight', 'getanimation', 'setanimation', 'playanimation', 'stopanimation',
            'attach', 'detach', 'send', 'receive', 'getmessage', 'setmessage',
            'serialize', 'deserialize', 'read', 'write', 'file', 'filesystem', 'path',
            'exists', 'open', 'close', 'readall', 'writeall', 'append', 'remove',
            'directory', 'createdirectory', 'removedirectory', 'getfiles', 'getdirectories',
            'json', 'parse', 'stringify', 'load', 'save', 'getparam', 'setparam',
            'getproperty', 'setproperty', 'getattribute', 'setattribute', 'getcomponent',
            'addcomponent', 'removecomponent', 'findcomponent', 'getentity', 'setentity',
            'getobject', 'setobject', 'gethandle', 'sethandle', 'getid', 'setid',
            'gettypeid', 'settypeid', 'getworld', 'setworld', 'getregion', 'setregion',
            'getzone', 'setzone', 'getlevel', 'setlevel', 'getlayer', 'setlayer',
            'getposition', 'setposition', 'getorientation', 'setorientation', 'getrotation',
            'setrotation', 'getscale', 'setscale', 'getbounds', 'setbounds',
            'getboundingbox', 'setboundingbox', 'getsphere', 'setsphere', 'getcapsule',
            'setcapsule', 'getcollider', 'setcollider', 'getrigidbody', 'setrigidbody',
            'gettexture', 'settexture', 'getmaterial', 'setmaterial', 'getmesh', 'setmesh',
            'getshader', 'setshader', 'getlight', 'setlight', 'getcamera', 'setcamera',
            'getaudio', 'setaudio', 'getparticle', 'setparticle', 'geteffect', 'seteffect',
            'getbehavior', 'setbehavior', 'getscript', 'setscript', 'getcomponent',
            'addcomponent', 'removecomponent', 'findcomponent', 'getentity', 'setentity',
            'getobject', 'setobject', 'gethandle', 'sethandle', 'getid', 'setid',
            'gettypeid', 'settypeid', 'getworld', 'setworld', 'getregion', 'setregion',
            'getzone', 'setzone', 'getlevel', 'setlevel', 'getlayer', 'setlayer',
        }
        
        common_words_lower = {word.lower() for word in common_words}

        for identifier in identifiers:
            if identifier.lower() in common_words_lower:
                continue

            if (len(identifier) > 5 and 
                self.looks_obfuscated(identifier)):
                obfuscated.append(identifier)
        return obfuscated
    
    def looks_obfuscated(self, identifier: str) -> bool:
        indicators = []
        
        # 1. Very long name
        if len(identifier) > 12: # Increased threshold for more confidence
            indicators.append(True)
        
        # 2. High uppercase ratio (e.g., 'ABCDEF', 'SomeBIGName')
        upper_count = sum(1 for c in identifier if c.isupper())
        if len(identifier) > 0 and upper_count / len(identifier) > 0.4: # More than 40% uppercase
            indicators.append(True)
            
        # 3. Mixed case with specific patterns (e.g., 'aBcDeFg', 'rANDOMName')
        has_upper = any(c.isupper() for c in identifier)
        has_lower = any(c.islower() for c in identifier)
        if has_upper and has_lower and len(identifier) > 5: # Must have both cases and be long enough
            indicators.append(True)
            
        # 4. High character diversity (e.g., 'a1B2c3D4') - presence of numbers/mix of char types
        has_digit = any(c.isdigit() for c in identifier)
        if has_digit and has_upper and has_lower and len(identifier) > 5: # Needs to be mixed and long enough
            indicators.append(True)
        
        return sum(indicators) >= 2
    
    async def get_ml_suggestions(self, content: str, identifiers: list) -> dict:
        await self.init_session()

        prompt = f"""You are an expert code deobfuscator for DayZ mod code (Enfusion Script/C++). Analyze this specific code snippet and suggest concise, meaningful names for the obfuscated identifiers based on context, DayZ conventions (e.g., IsMultiplayer, GetMission, logical understandable strings in general), and common programming patterns.

Code snippet:
{content}

Obfuscated identifiers to rename: {', '.join(identifiers)}

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
                    },
                    timeout=600 
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_text = result.get('response', '')
                        
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(1)
                        else:
                            json_start = response_text.find('{')
                            json_end = response_text.rfind('}') + 1
                            json_str = response_text[json_start:json_end] if json_start >= 0 else ""

                        if json_str:
                            try:
                                mappings = json.loads(json_str)
                                valid_mappings = {k: v for k, v in mappings.items() if k in identifiers and isinstance(v, str)}
                                return valid_mappings
                            except json.JSONDecodeError:
                                print(f"  Attempt {attempt}: Failed to parse JSON response. Response snippet: \n{response_text[:200]}...")
                        else:
                            print(f"  Attempt {attempt}: No valid JSON found in response. Response snippet: \n{response_text[:200]}...")
                    else:
                        print(f"  Attempt {attempt}: API request failed with status {response.status}. Response: {await response.text()[:200]}...")
            except asyncio.TimeoutError:
                print(f"  Attempt {attempt}: Ollama API call timed out. Retrying...")
            except aiohttp.ClientError as e:
                print(f"  Attempt {attempt}: AIOHTTP client error during ML call - {e}. Retrying...")
            except Exception as e:
                print(f"  Attempt {attempt}: Unexpected error during ML call - {e}. Retrying...")
            
            if attempt < self.max_retries:
                delay = self.initial_retry_delay * (2 ** (attempt - 1))
                print(f"  Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
        
        print(f"  All {self.max_retries} attempts failed to get ML suggestions.")
        return {}

    def create_fallback_mappings(self, identifiers: list) -> dict:
        mappings = {}
        for idx, identifier in enumerate(identifiers, 1):
            if identifier.isupper():
                mappings[identifier] = f"UNKNOWN_{idx}"
            elif identifier[0].isupper():
                mappings[identifier] = f"Unknown{idx}"
            else:
                mappings[identifier] = f"unknown_{idx}"
        return mappings

    def apply_mappings(self, content: str, mappings: dict) -> str:
        result = content
        sorted_mappings = sorted(mappings.items(), key=lambda item: len(item[0]), reverse=True)

        for obfuscated, meaningful in sorted_mappings:
            if meaningful and meaningful != obfuscated:
                pattern = rf'\b{re.escape(obfuscated)}\b'
                result = re.sub(pattern, meaningful, result)
        return result

    def clean_junk(self, content: str) -> str:
        """
        Aggressively removes non-printable characters, non-ASCII, and common junk patterns
        that often result from misinterpreting binary data as text.
        """
        # 1. Replace null bytes (common in binary files) with space
        content = content.replace('\0', ' ')
        
        # 2. Replace the Unicode replacement character (�) with space, as it indicates an encoding error
        content = content.replace('�', ' ')

        # 3. Remove ALL non-ASCII characters. Truly obfuscated code shouldn't rely on non-ASCII.
        # This will eliminate Mojibake (e.g., ÿ, õ, ÷, é, ß)
        content = re.sub(r'[^\x00-\x7F]+', ' ', content)
        
        # 4. Remove a broad set of control characters and other unprintable ASCII
        # Characters allowed: alphanumeric, common punctuation/symbols used in code, and whitespace.
        # Anything else is replaced with a space.
        allowed_ascii_code_chars = r'[a-zA-Z0-9_ \t\n\r!@#$%^&*()_=+\[\]{}\\|;:\'",<.>/?-]'
        content = re.sub(f'[^{allowed_ascii_code_chars}]+', ' ', content)

        # 5. Normalize whitespace: replace multiple spaces/tabs with single space
        content = re.sub(r'[ \t]+', ' ', content) 

        # 6. Apply specific junk pattern removal based on the example provided
        # These are highly specific and may need adjustment based on other junk you encounter.
        content = re.sub(r'BO;MMj wBnWBFBU "', '', content, flags=re.IGNORECASE)
        content = re.sub(r'LBm aster_Gr oupsServ er unit s\[\] = \{\} ; weapon require dVersion \* 0\.1 Add 2', '', content, flags=re.IGNORECASE)
        content = re.sub(r'#ifdef GAMELAB Sb "Game Labs_Scr ipts",', '', content, flags=re.IGNORECASE)
        content = re.sub(r'# endif D LCPlotpo le\' N Aird ropUpgra dedU T H eliCrash Mis s \( XUQAqH2 MJxAJWDJ R\' DZ_Da ta"', '', content, flags=re.IGNORECASE)
        content = re.sub(r': / \d+ x Modu u d irq " p\?icture% act\{ hid#eNU P3 n " E uth oy', '', content)
        content = re.sub(r'l c / ID \d+ \$\" \d+\. typ m od depN e ncie % %C WGorl ! \"N \d+ @ F g\? :# uleT val u\" obfu scated fil n\.', '', content)
        # This regex tries to catch the very last, most corrupted line
        content = re.sub(r'\d+/\s*NUL\.tyhm\s*.*', '', content, flags=re.DOTALL) # Match from 4/ NUL.tyhm to end

        # 7. Split into lines, filter out lines that are too short or have low alphanumeric content
        lines = content.split('\n')
        filtered_lines = []
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line: # Keep truly empty lines to preserve some structure
                filtered_lines.append('')
                continue
            
            alphanumeric_chars = len(re.findall(r'[a-zA-Z0-9]', stripped_line))
            total_chars = len(stripped_line)
            
            # Criteria for a line to be considered junk:
            # - Very short (e.g., < 10 characters) AND very low alphanumeric content (< 30%)
            # This helps remove "a b c ;" or "() ; ." type junk lines
            if total_chars > 0 and (alphanumeric_chars / total_chars < 0.3 and total_chars < 15):
                continue 
            
            filtered_lines.append(stripped_line)
        
        # 8. Rejoin lines and normalize multiple blank lines
        cleaned_content = '\n'.join(filtered_lines)
        cleaned_content = re.sub(r'\n{2,}', '\n\n', cleaned_content).strip()
        
        return cleaned_content


    def is_valuable_code(self, content: str) -> bool:
        """
        Heuristic to determine if the file contains valuable code or is likely junk/empty
        AFTER it has been through the clean_junk process.
        """
        # 1. Minimum content length and lines after cleaning
        code_lines = [line.strip() for line in content.split('\n') if line.strip()]
        if len(content.strip()) < 50: # Minimum 50 meaningful characters after cleaning
            return False
        if len(code_lines) < 7:  # Minimum 7 non-empty lines of code
            return False

        # 2. Density of "code-like" characters (alphanumeric, common symbols)
        # Remove comments first for a more accurate density check
        code_without_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.MULTILINE|re.DOTALL)
        code_without_comments = re.sub(r'//.*$', '', code_without_comments, flags=re.MULTILINE)
        
        # Count characters that are typical of code (letters, numbers, common operators/punctuation)
        # This regex is stricter, focuses on code structure components
        meaningful_chars = len(re.findall(r'[a-zA-Z0-9_(){}\[\];.,<>!=\-+\*/&|:~#]', code_without_comments))
        total_chars_in_code_segment = len(code_without_comments.strip())

        code_density = meaningful_chars / total_chars_in_code_segment if total_chars_in_code_segment > 0 else 0

        # If after cleaning, the content is still mostly whitespace or non-meaningful chars
        if code_density < 0.20: # At least 20% code-like characters are expected
            return False

        # 3. Presence of structural indicators
        valuable_indicators = {
            'has_class_structure': bool(re.search(r'class\s+\w+\s*{', content)),
            'has_function_structure': bool(re.search(r'(static|void|int|bool|string|float)\s+\w+\s*\(', content)),
            'has_logic_flow': bool(re.search(r'(if|else|for|while|switch)\s*\(', content)),
            'has_dayz_patterns': bool(re.search(r'(GetGame|GetMission|IsMultiplayer|IsServer|IsClient|Cast|DayZPlayer|PlayerBase|ItemBase)\s*\(', content, re.IGNORECASE)),
            'has_ref_patterns': bool(re.search(r'\bref\s+\w+', content)),
            'has_obfuscated_identifiers': len(self.extract_and_filter_identifiers(content)) > 0,
            'has_include_directives': bool(re.search(r'^#include\s+"', content, re.MULTILINE)), # Common in C++
            'has_define_directives': bool(re.search(r'^#define\s+', content, re.MULTILINE)), # Common in C++
        }

        valuable_score = sum(valuable_indicators.values())

        # Decision: It's valuable if it meets basic density/length checks AND 
        # has at least 2 strong structural indicators OR clearly has obfuscated identifiers.
        is_valuable = (
            valuable_score >= 2 or valuable_indicators['has_obfuscated_identifiers']
        )
        
        return is_valuable

    async def _process_single_file(self, input_file: str, input_root: str, output_root: str, semaphore: asyncio.Semaphore):
        """Helper to process a single file, intended to be run concurrently."""
        async with semaphore:
            processed_successfully = False
            status_message = "Failed"
            original_raw_content = "" # Store the raw content after decoding
            cleaned_content = ""

            # Derive output path
            rel_path = os.path.relpath(os.path.dirname(input_file), input_root)
            output_dir = os.path.join(output_root, rel_path)
            os.makedirs(output_dir, exist_ok=True) # Ensure output directory exists before any writing attempt
            output_file = os.path.join(output_dir, os.path.basename(input_file))

            try:
                # Read file content in binary mode
                file_bytes = None
                with open(input_file, 'rb') as f:
                    file_bytes = f.read()

                # Try common encodings, always replacing errors.
                # If none work well, Latin-1 is a byte-for-byte mapping, so it won't error,
                # but might produce mojibake which clean_junk will handle.
                decoded_content = None
                encodings_to_try = ['utf-8', 'cp1252', 'latin1', 'ascii', 'iso-8859-1', 'utf-16']
                for encoding in encodings_to_try:
                    try:
                        decoded_content = file_bytes.decode(encoding, errors='replace')
                        if '�' not in decoded_content or encoding == 'latin1': # Prefer decoding without replacement chars, but Latin-1 is a fallback.
                            break
                    except (UnicodeDecodeError, TypeError):
                        continue
                if decoded_content is None: # Should not happen with latin1 as final fallback, but for safety
                    decoded_content = file_bytes.decode('latin1', errors='replace')

                original_raw_content = decoded_content # Keep this for potential logging/fallback copy

                # --- STEP 1: Aggressively Clean Junk from the raw decoded content ---
                cleaned_content = self.clean_junk(original_raw_content)
                
                # --- STEP 2: Assess if the cleaned content is valuable code ---
                if not self.is_valuable_code(cleaned_content):
                    print(f"[SKIP] {input_file} (identified as junk/non-valuable after cleaning)")
                    status_message = "Skipped (junk)"
                    return (False, input_file, status_message)

                print(f"[PROC] {input_file}")
                
                # --- STEP 3: Deobfuscate the valuable, cleaned code ---
                identifiers = self.extract_and_filter_identifiers(cleaned_content)
                deobfuscated_content = cleaned_content # Default to cleaned content

                if identifiers:
                    print(f"  Found {len(identifiers)} obfuscated identifiers.")
                    mappings = await self.get_ml_suggestions(cleaned_content, identifiers)
                    if not mappings:
                        mappings = self.create_fallback_mappings(identifiers)
                        print(f"  Using fallback mappings for {len(mappings)} identifiers.")
                    else:
                        print(f"  Received ML suggestions for {len(mappings)} identifiers.")
                    deobfuscated_content = self.apply_mappings(cleaned_content, mappings)
                else:
                    print(f"  No obfuscated identifiers found.")

                # --- STEP 4: Write the final (cleaned and/or deobfuscated) content ---
                # Always write as UTF-8 with errors replaced to ensure valid output files.
                with open(output_file, 'wb') as f:
                    f.write(deobfuscated_content.encode('utf-8', errors='replace'))
                print(f"[SAVE] {output_file}")
                processed_successfully = True
                status_message = "Processed"
                        
            except Exception as e:
                print(f"[ERROR] {input_file}: {e}")
                # If processing fails, try to copy the *cleaned* file. If cleaning itself failed, copy original raw.
                try:
                    if cleaned_content: # If cleaning was successful, save the cleaned version
                        with open(output_file, 'wb') as f:
                            f.write(cleaned_content.encode('utf-8', errors='replace'))
                        print(f"[COPY] {output_file} (cleaned only due to processing error)")
                    elif original_raw_content: # If cleaning failed or not possible, save original raw
                        with open(output_file, 'wb') as f:
                            f.write(original_raw_content.encode('utf-8', errors='replace'))
                        print(f"[COPY] {output_file} (original raw due to processing error)")
                    status_message = "Copied (error)"
                except Exception as copy_error:
                    print(f"  [ERROR] Failed to copy original/cleaned {input_file}: {copy_error}")
                    status_message = "Failed (copy also failed)"
            
            return (processed_successfully, input_file, status_message)

    async def process_folder(self, input_path: str, output_path: str):
        await self.init_session()
        
        file_extensions = ('.c', '.cpp', '.h', '.hpp', '.cs', '.sqf')
        files_to_process = []

        print(f"--- Starting folder scan: {input_path} ---")
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.endswith(file_extensions):
                    files_to_process.append(os.path.join(root, file))

        total_files = len(files_to_process)
        print(f"Found {total_files} relevant code files for processing.")

        if not files_to_process:
            print("No code files found to process. Exiting.")
            return

        MAX_CONCURRENT_TASKS = 5 # Adjust this based on your Ollama server's capacity and network bandwidth.
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

        tasks = []
        for input_file in files_to_process:
            tasks.append(self._process_single_file(input_file, input_path, output_path, semaphore))

        results = await asyncio.gather(*tasks)

        # Summarize results
        processed_count = 0
        skipped_count = 0
        failed_count = 0
        copied_on_error_count = 0

        for success, _, status in results:
            if status == "Processed":
                processed_count += 1
            elif status == "Skipped (junk)":
                skipped_count += 1
            elif status == "Copied (error)":
                failed_count += 1
                copied_on_error_count += 1
            else:
                failed_count += 1

        print("\n--- Processing Summary ---")
        print(f"Total files scanned: {total_files}")
        print(f"Successfully deobfuscated and saved: {processed_count}")
        print(f"Skipped (identified as junk/non-valuable): {skipped_count}")
        print(f"Files where deobfuscation failed: {failed_count}")
        print(f"  (Original/cleaned file copied in {copied_on_error_count} of these cases)")
        print("--------------------------")
        print(f"Deobfuscation complete. Output saved to: {output_path}")


async def main(): 
    # IMPORTANT: Replace these with your actual input and output folders 
    input_folder = "/home/alca/Schreibtisch/test/AdvancedGroups_Server_latest/" 
    output_folder = "/home/alca/Schreibtisch/test/algo_cleaned/"

    # Ensure the top-level output folder exists before starting processing
    os.makedirs(output_folder, exist_ok=True)

    deobfuscator = CodeDeobfuscatorAlgorithm()
    try:
        await deobfuscator.process_folder(input_folder, output_folder)
    finally:
        await deobfuscator.close_session()

if __name__ == "__main__":
    asyncio.run(main())