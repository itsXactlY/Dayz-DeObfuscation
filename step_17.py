import os
import re
import json
import subprocess
import requests

# --- Configuration ---
PBO_FILE_PATH = r"/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server.pbo"
EXTRACTED_DIR = r"/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/"
BACKUP_DIR = r"/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/backup/"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

# --- Step 1: Extract C# Scripts from .pbo ---
def extract_pbo(pbo_file_path, extracted_dir):
    """Extract contents of .pbo file using PBOProject."""
    print("Extracting .pbo file...")
    os.makedirs(extracted_dir, exist_ok=True)
    try:
        # Use PBOProject CLI to extract (download from https://github.com/KoffeinFlummi/PBOProject)
        subprocess.run([
            "PBOProject.exe",
            "-U",  # Unpack
            "-O", extracted_dir,  # Output dir
            pbo_file_path
        ], check=True)
        print(f"Extracted to: {extracted_dir}")
    except Exception as e:
        print(f"Error extracting .pbo: {e}")
        exit(1)

# --- Step 2: Collect Encrypted Strings ---
def collect_encrypted_strings(extracted_dir):
    """Scan all C# files for encrypted strings."""
    print("Collecting encrypted strings...")
    encrypted_strings = set()
    pattern = r'Ns7IynOBl5RX6MyZ\("(.*?)"'
    
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith("*.*"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        matches = re.findall(pattern, content)
                        encrypted_strings.update(matches)
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    with open("encrypted_strings.txt", 'w') as f:
        for string in sorted(encrypted_strings):
            f.write(string + "\n")
    
    print(f"Collected {len(encrypted_strings)} unique encrypted strings.")
    return "encrypted_strings.txt"

# --- Step 3: Decrypt Strings (Custom Logic Required) ---
def decrypt_strings(encrypted_strings_file):
    """Placeholder: Implement logic for SfFuxbdumezDa91W.Ns7IynOBl5RX6MyZ decryption."""
    print("Decrypting strings (manual logic needed)...")
    # **YOU MUST IMPLEMENT THIS**:
    # 1. Reverse-engineer `Ns7IynOBl5RX6MyZ` method from extracted C# code.
    # 2. Write Python logic to replicate decryption.
    # Example (dummy decryption):
    decrypted_map = {}
    with open(encrypted_strings_file, 'r') as f:
        encrypted_strings = [line.strip() for line in f.readlines()]
    for enc_str in encrypted_strings:
        # **REPLACE THIS WITH ACTUAL DECRYPTION**:
        decrypted_map[enc_str] = f"DECRYPTED_{enc_str}"
        print(f"Decrypted: {enc_str} -> DECRYPTED_{enc_str}")
    
    with open("decrypted_strings.json", 'w') as f:
        json.dump(decrypted_map, f, indent=4)
    
    print("Decrypted strings saved to decrypted_strings.json")
    return "decrypted_strings.json"

# --- Step 4: Replace Encrypted Strings Globally ---
def replace_encrypted_strings(decrypted_map_file, extracted_dir, backup_dir):
    """Replace all occurrences of encrypted strings in the codebase."""
    print("Replacing encrypted strings...")
    os.makedirs(backup_dir, exist_ok=True)
    
    with open(decrypted_map_file, 'r') as f:
        decrypted_map = json.load(f)
    
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith(".cs"):
                filepath = os.path.join(root, file)
                backup_path = os.path.join(backup_dir, file)
                
                # Backup original file
                with open(filepath, 'r') as f:
                    content = f.read()
                with open(backup_path, 'w') as f:
                    f.write(content)
                
                # Replace encrypted strings
                for enc_str, dec_str in decrypted_map.items():
                    old_code = f'Ns7IynOBl5RX6MyZ("{enc_str}"'
                    new_code = f'"{dec_str}" /* Decrypted: {enc_str} */'
                    content = content.replace(old_code, new_code)
                
                # Overwrite file with updated content
                with open(filepath, 'w') as f:
                    f.write(content)
    
    print("Encrypted strings replaced globally.")

# --- Step 5: Rename Obfuscated Symbols (Ollama-Driven) ---
def rename_obfuscated_symbols(extracted_dir):
    """Use Ollama to suggest meaningful names for obfuscated symbols."""
    print("Renaming obfuscated symbols...")
    obfuscated_names = set()
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]{10,})\b'
    
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith(".cs"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r') as f:
                    content = f.read()
                    matches = re.findall(pattern, content)
                    obfuscated_names.update(matches)
    
    # Filter out non-obfuscated (common C# names)
    obfuscated_names = {name for name in obfuscated_names if len(name) > 15}
    
    renamed_map = {}
    for name in obfuscated_names:
        prompt = f"Suggest a meaningful C# name for: {name}"
        response = ollama_query(prompt)
        new_name = response.strip()
        renamed_map[name] = new_name
        print(f"Renamed: {name} -> {new_name}")
    
    with open("renamed_symbols.json", 'w') as f:
        json.dump(renamed_map, f, indent=4)
    
    return "renamed_symbols.json"

def ollama_query(prompt):
    """Send prompt to Ollama API."""
    headers = {"Content-Type": "application/json"}
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 100}
    }
    try:
        response = requests.post(OLLAMA_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except Exception as e:
        print(f"Ollama API error: {e}")
        return prompt  # Fallback to original prompt

# --- Step 6: Replace Obfuscated Names Globally ---
def replace_obfuscated_names(renamed_map_file, extracted_dir):
    """Replace all occurrences of obfuscated names in the codebase."""
    print("Replacing obfuscated names...")
    with open(renamed_map_file, 'r') as f:
        renamed_map = json.load(f)
    
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith(".cs"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r') as f:
                    content = f.read()
                for obf_name, new_name in renamed_map.items():
                    content = content.replace(obf_name, new_name)
                with open(filepath, 'w') as f:
                    f.write(content)
    
    print("Obfuscated names replaced globally.")

# --- Step 7: Cleanup Dead Code ---
def cleanup_dead_code(extracted_dir):
    """Remove unused assignments and simplify operations."""
    print("Cleaning up dead code...")
    unused_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]+)\s*=\s*[^;]+;\s*(?![^\n]*\b\1\b)'
    
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith(".cs"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r') as f:
                    content = f.read()
                cleaned_content = re.sub(unused_pattern, '', content, flags=re.MULTILINE)
                with open(filepath, 'w') as f:
                    f.write(cleaned_content)
    
    print("Dead code removed.")

# --- Repack .pbo (Optional) ---
def repack_pbo(extracted_dir, output_pbo):
    """Repack the deobfuscated files into a new .pbo."""
    print("Repacking .pbo file...")
    try:
        subprocess.run([
            "PBOProject.exe",
            "-P",  # Pack
            "-O", output_pbo,  # Output .pbo
            extracted_dir
        ], check=True)
        print(f"Repacked to: {output_pbo}")
    except Exception as e:
        print(f"Error repacking .pbo: {e}")

# --- Main Workflow ---
def main():
    # Step 1: Extract .pbo
    # extract_pbo(PBO_FILE_PATH, EXTRACTED_DIR)
    
    # Step 2: Collect Encrypted Strings
    encrypted_strings_file = collect_encrypted_strings(EXTRACTED_DIR)
    
    # Step 3: Decrypt Strings (Implement logic in `decrypt_strings`)
    decrypted_map_file = decrypt_strings(encrypted_strings_file)
    
    # Step 4: Replace Encrypted Strings
    replace_encrypted_strings(decrypted_map_file, EXTRACTED_DIR, BACKUP_DIR)
    
    # Step 5: Rename Obfuscated Symbols
    renamed_symbols_file = rename_obfuscated_symbols(EXTRACTED_DIR)
    
    # Step 6: Replace Obfuscated Names
    replace_obfuscated_names(renamed_symbols_file, EXTRACTED_DIR)
    
    # Step 7: Cleanup Dead Code
    cleanup_dead_code(EXTRACTED_DIR)
    
    # Optional: Repack into a new .pbo
    # repack_pbo(EXTRACTED_DIR, "Deobfuscated.pbo")
    
    print("Bulk deobfuscation complete!")

if __name__ == "__main__":
    main()
