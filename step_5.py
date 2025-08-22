import re
import os

ENCODE_PATTERN = re.compile(r'Ns7IynOBl5RX6MyZ\("([A-Z]+)"\s*,\s*([^)]+)\)')
EXTENSIONS = ('.c', '.cpp', '.h', '.sqf')

def fake_decrypt(ciphertext, context_var=None):
    # 🔧 Replace this with the real logic once you reverse Ns7IynOBl5RX6MyZ
    return f'"{ciphertext[::-1]}"'  # simple mock: reverse the string

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    modified = False
    def repl(match):
        nonlocal modified
        encrypted = match.group(1)
        context = match.group(2)
        decrypted = fake_decrypt(encrypted, context)
        modified = True
        return decrypted

    new_content = ENCODE_PATTERN.sub(repl, content)

    if modified:
        print(f"[+] Decrypted strings in: {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

def walk_folder(root):
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(EXTENSIONS):
                fullpath = os.path.join(dirpath, name)
                process_file(fullpath)

# === Run ===
if __name__ == "__main__":
    FOLDER_TO_SCAN = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/"
    walk_folder(FOLDER_TO_SCAN)
