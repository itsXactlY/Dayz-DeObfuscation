import re
import os

def clean_dayz_enforce_script(obfuscated_content):
    cleaned_content = obfuscated_content

    # --- Pass 0: Initial Cleanup (Handle common non-printable and repetitive junk) ---
    # Remove null bytes and other common control characters
    cleaned_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\xA0]+', '', cleaned_content)
    
    # Remove common repeating junk patterns
    cleaned_content = re.sub(r'(�+ ?)+', ' ', cleaned_content) # � followed by space, repeated
    cleaned_content = re.sub(r'(\s?[_?/\\]\s?)+', ' ', cleaned_content) # _ ? / \ and spaces repeated
    cleaned_content = re.sub(r'(\s{2,})', ' ', cleaned_content) # Multiple spaces to single space
    cleaned_content = re.sub(r'(~<)', ' ', cleaned_content) # ~<
    cleaned_content = re.sub(r'(\s?\uFFFD\s?)+', ' ', cleaned_content) # Unicode replacement character
    cleaned_content = re.sub(r'(\s?[0-9][a-zA-Z]\s?)+', ' ', cleaned_content) # "4st", "16h" - could be junk
    cleaned_content = re.sub(r'(\s?[a-zA-Z][0-9]\s?)+', ' ', cleaned_content) # "C3"
    cleaned_content = re.sub(r'(BqqCh�PBbQubDk�FRXIsjM<�YJiCiyts�OuMrpJzG�> dsulGF�OyHiPjsZ�ݑ)', '', cleaned_content) # Specific block of junk
    
    # --- Pass 1: String Deobfuscation (Prioritize before identifier cleaning) ---
    # This is tricky. We'll try to extract the likely readable parts from within quotes.
    # We assume the readable part is mostly alphanumeric and common symbols,
    # while the junk is the weird characters.
    
    def clean_quoted_string(match):
        original_string = match.group(1)
        # Keep letters, numbers, common punctuation, spaces. Remove other non-ASCII and specific junk.
        cleaned_inner = re.sub(r'[^\x20-\x7E]+', '', original_string) # Remove non-printable ASCII
        cleaned_inner = re.sub(r'[�?|\\#&%]+', '', cleaned_inner) # Remove specific obfuscator-added junk
        cleaned_inner = re.sub(r'\s{2,}', ' ', cleaned_inner).strip() # Clean extra spaces
        return f'"{cleaned_inner}"'

    # Apply string cleaning to all quoted strings
    cleaned_content = re.sub(r'"([^"]*)"', clean_quoted_string, cleaned_content)


    # --- Pass 2: Identifier and Keyword Reconstruction ---
    # Map mangled identifiers to generic, readable ones
    # This requires state to ensure consistent mapping
    
    # Common Enforce Script keywords and types that should NOT be touched
    keywords_and_types = [
        r'void', r'bool', r'int', r'float', r'string', r'array', r'class', r'static',
        r'if', r'else', r'return', r'new', r'true', r'false', r'this', r'super',
        r'override', r'private', r'protected', r'public', r'typename', r'auto',
        r'switch', r'case', r'default', r'break', r'continue', r'for', r'foreach',
        r'while', r'do', r'const', r'enum', r'union', r'struct', r'vector', r'color',
        r'entity', r'object', r'inventory', r'item', r'player', r'dayzPlayer',
        r'playerBase', r'itemBase', r'weapon', r'magazine', r'map', r'set',
        r'json', r'rpc', r'callback', r'param', r'message', r'instance',
        r'event', r'sync', r'component', r'componentBase', r'widget', r'anim',
        r'game', r'world', r'getGame', r'getDayZGame', r'getEnv', r'getResource',
        r'getWeaponManager', r'getUIManager', r'getInventory', r'getActions',
        r'getAmmoManager', r'getCharacter', r'getMovement', r'getHealth',
        r'getModifiers', r'getItemType', r'getObject', r'getChildren', r'getParent',
        r'getPos', r'setPos', r'spawn', r'delete', r'print', r'log', r'error',
        r'debug', r'dbody', r'config', r'mission', r'server', r'client', r'call',
        r'input', r'action', r'register', r'unregister', r'send', r'receive',
        r'add', r'remove', r'find', r'count', r'clear', r'resize', r'get', r'set',
        r'isAlive', r'isServer', r'isClient', r'isDedicated', r'isModded',
        r'onInit', r'onUpdate', r'onDestroy', r'onEnter', r'onExit', r'onRPC',
        r'onPlayerConnected', r'onPlayerDisconnected', r'onDamage', r'onHit',
        r'onTakeDamage', r'onRespawn', r'onStoreSave', r'onStoreLoad', r'onLogin',
        r'onLogout', r'onJump', r'onLand', r'onRun', r'onWalk', r'onSprint',
        r'onCrouch', r'onProne', r'onWeaponFired', r'onBulletHit', r'onInput',
        r'onSelect', r'onDeselect', r'onInteraction', r'onCommand', r'onAction',
        r'onAnimFinish', r'onAnimEvent', r'onCollision', r'onTriggerEnter', r'onTriggerExit',
        r'onParticleEvent', r'onCameraChange', r'onWeatherChange', r'onTemperatureChange',
        r'onLiquidDecay', r'onLoadoutChanged', r'onHairLevelChanged', r'onDryWetChanged',
        r'onFuelChanged', r'onBandageEffect', r'onBleedingEffect', r'onShockEffect',
        r'onStaminaChanged', r'onWaterChanged', r'onFoodChanged', r'onBloodChanged',
        r'onHealthChanged', r'onImmunityChanged', r'onInfectedChanged', r'onLootChange',
        r'OnEachFrame', r'OnAfterMissionStart', r'GetP' # Keep common partials like GetP
    ]
    # Build a regex to match these keywords exactly (word boundaries)
    keyword_regex = r'\b(' + '|'.join(keywords_and_types) + r')\b'

    # Dictionary to store identifier mappings (e.g., 'mangled1' -> 'ObfVar_001')
    identifier_map = {}
    identifier_counter = {'var': 0, 'func': 0, 'class': 0}

    def clean_identifier(match):
        original_id = match.group(0)
        
        # If it's a known keyword, return it as is
        if re.fullmatch(keyword_regex, original_id, re.IGNORECASE):
            return original_id
        
        # Remove junk characters within identifiers
        cleaned_id = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\xA0�?\-/_.,|<=>!@#$%^&*()\[\]{}]+', '', original_id)
        
        # If the cleaned_id is empty or too short, return the original (maybe it was just junk)
        if not cleaned_id or len(cleaned_id) < 2:
             return original_id # Better to leave some junk than break syntax
        
        # Check if already mapped
        if original_id in identifier_map:
            return identifier_map[original_id]

        # Determine type based on common patterns (heuristic, may not be perfect)
        if re.search(r'^\s*class\s+' + re.escape(original_id), cleaned_content) or re.search(r'\bnew\s+' + re.escape(original_id), cleaned_content):
            identifier_counter['class'] += 1
            new_id = f"ObfClass_{identifier_counter['class']}"
        elif '(' in cleaned_id or ')' in cleaned_id: # Simple heuristic for functions
            identifier_counter['func'] += 1
            new_id = f"ObfFunc_{identifier_counter['func']}"
        else:
            identifier_counter['var'] += 1
            new_id = f"ObfVar_{identifier_counter['var']}"
        
        identifier_map[original_id] = new_id
        return new_id

    # Regex for identifiers: Starts with letter/underscore, followed by letters/numbers/underscores
    # It also includes the junk characters to capture them for cleaning inside the function.
    # This pattern is aggressive to capture mangled names.
    identifier_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*[^\s\(\)\{\}\[\]\.,;:\'"\/\\`~!@#\$%\^&\*|+=\-<>?]*'
    
    # Use a custom replacement function with re.sub
    # We must be careful not to match keywords. This will be an iterative process.
    # First, replace known keywords with placeholders to avoid matching them.
    # Then run identifier replacement. Then restore keywords.
    
    # Placeholder for keywords to prevent accidental renaming
    keyword_placeholders = {}
    def replace_keywords_with_placeholders(match):
        keyword = match.group(0)
        placeholder = f"__KEYWORD_{len(keyword_placeholders)}__"
        keyword_placeholders[placeholder] = keyword
        return placeholder

    temp_content = re.sub(keyword_regex, replace_keywords_with_placeholders, cleaned_content, flags=re.IGNORECASE)

    # Now replace the non-keyword identifiers
    temp_content = re.sub(identifier_pattern, clean_identifier, temp_content)
    
    # Restore keywords
    for placeholder, keyword in keyword_placeholders.items():
        temp_content = temp_content.replace(placeholder, keyword)
    
    cleaned_content = temp_content

    # --- Pass 3: Formatting and Syntax Tidying ---
    # Add newlines after curly braces for readability
    cleaned_content = re.sub(r'\{', '{\n', cleaned_content)
    cleaned_content = re.sub(r'\}', '}\n', cleaned_content)
    
    # Ensure semicolons after statements (if missing in places due to obfuscation)
    # This is a bit risky and might add extra semicolons, but can help parse.
    # cleaned_content = re.sub(r'(?<!;)\s*\n', ';\n', cleaned_content) # Too aggressive
    
    # Basic indentation (simple, not a full AST parser)
    lines = cleaned_content.split('\n')
    indented_lines = []
    indent_level = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('}'):
            indent_level = max(0, indent_level - 1)
        
        indented_lines.append('    ' * indent_level + line)
        
        if line.endswith('{'):
            indent_level += 1
            
    cleaned_content = '\n'.join(indented_lines)
    
    # Remove empty lines that might result from cleaning
    cleaned_content = re.sub(r'\n\s*\n', '\n', cleaned_content)

    return cleaned_content

# --- Main script logic ---
if __name__ == "__main__":
    dump_file_path = "dump_v3.pbo" # <--- IMPORTANT: Update this to your chosen dump file!

    if not os.path.exists(dump_file_path):
        print(f"Error: Dump file not found at '{dump_file_path}'. Please update the path.")
        exit(1)

    with open(dump_file_path, 'r', encoding='latin-1', errors='ignore') as f:
        obfuscated_data = f.read()

    print("[*] Performing multi-pass cleaning...")
    cleaned_script = clean_dayz_enforce_script(obfuscated_data)

    output_file_path = dump_file_path + ".cleaned.sqf"
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_script)

    print(f"[*] Cleaned script saved to: {output_file_path}")
    print("\n--- Snippet of Cleaned Script ---")
    print(cleaned_script[:2000]) # Print first 2000 characters for a quick look
    print("\n---------------------------------")
    print("Further manual inspection and refinement will likely be needed.")
    print("Consider using `arma3pbo unpack` on the most promising (e.g., .delayed_3) dump BEFORE cleaning with this script,")
    print("and then running this script on the *extracted* .sqf or .bin file.")