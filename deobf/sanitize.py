import re
import os
from pathlib import Path

# Configuration
PBO_PATH = "Server.pbo"  # Change to your actual .pbo path if needed
OUTPUT_DIR = "recovered_assets"
EXTRACT_SIZE = 64 * 1024  # 64 KB per file chunk

# Regex pattern to find fake/obfuscated embedded file paths
FILE_PATH_PATTERN = re.compile(
    rb"(?:[A-Z]:|LPT\d|COM\d)[^\\\n\r]{0,20}\\[^\\\n\r]{0,64}\\[^\\\n\r]{0,64}\.[a-z0-9]{3,5}",
    re.IGNORECASE
)

# Junk/obfuscation patterns to filter out
JUNK_PATTERNS = {
    # Windows reserved device names
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    "CON", "PRN", "AUX", "NUL",
    
    # Suspicious extensions
    "ogkyf", "bapMz", "mtmog", "fxy", "ObOhp", "TyYvBTEqjzVDdrMxiwq"
}

# Valid DayZ file extensions
VALID_EXTENSIONS = {
    # Scripts
    'c', 'cpp', 'hpp', 'sqf', 'fsm', 'bikb',
    # Config
    'cfg', 'rvmat', 'bisurf',
    # Models
    'p3d', 'mlod', 'lod', 'rtm', 'skeleton',
    # Textures/Images
    'paa', 'pac', 'jpg', 'jpeg', 'png', 'tga', 'dds', 'edds',
    # World
    'wrp', 'tm', 'xyz', 'asc', 'shp', 'eto',
    # Audio
    'ogg', 'wav', 'wss', 'lip',
    # Animation
    'anm',
    # Misc
    'bin', 'bisign', 'txt', 'xml', 'json'
}

def is_junk_path(path: str) -> bool:
    """
    Returns True if the path is considered junk/obfuscated
    based on various heuristics.
    """
    # Check for reserved device names
    parts = path.replace('\\', '/').split('/')
    for part in parts:
        if part.upper() in JUNK_PATTERNS:
            return True
    
    # Check for suspicious random-looking strings
    for part in parts:
        # Skip extension check for this
        if '.' in part:
            name_part = part.split('.')[0]
        else:
            name_part = part
            
        # Check for very random looking strings (mix of upper/lower with numbers)
        if len(name_part) > 8:
            upper_count = sum(1 for c in name_part if c.isupper())
            lower_count = sum(1 for c in name_part if c.islower())
            digit_count = sum(1 for c in name_part if c.isdigit())
            
            # If it has a chaotic mix, likely obfuscated
            if upper_count > 0 and lower_count > 0 and digit_count > 0:
                if upper_count + lower_count + digit_count == len(name_part):
                    return True
    
    # Check file extension
    if '.' in path:
        ext = path.split('.')[-1].lower()
        if ext not in VALID_EXTENSIONS:
            return True
    
    # Check for null bytes or other suspicious characters
    if '\x00' in path or len(path) > 200:
        return True
    
    # Check for too many nested levels (likely obfuscated)
    if path.count('\\') > 5:
        return True
    
    return False

def has_valid_content(data_chunk: bytes) -> bool:
    """
    Basic check to see if the extracted data looks like valid file content.
    """
    if len(data_chunk) < 10:
        return False
    
    # Check for common file headers
    file_headers = [
        b'\x89PNG',      # PNG
        b'\xFF\xD8\xFF', # JPEG  
        b'DDS ',         # DDS texture
        b'RIFF',         # WAV/other RIFF
        b'OggS',         # OGG
        b'ODOL',         # P3D model
        b'MLOD',         # MLOD model
        b'#define',      # Config files
        b'class ',       # Config files
        b'/*',           # C++ comments
        b'//',           # C++ comments
    ]
    
    for header in file_headers:
        if data_chunk.startswith(header):
            return True
    
    # Check if it's mostly printable (script files)
    try:
        text = data_chunk[:1024].decode('utf-8', errors='ignore')
        printable_ratio = sum(1 for c in text if c.isprintable() or c.isspace()) / len(text)
        if printable_ratio > 0.7:  # 70% printable characters
            return True
    except:
        pass
    
    # Check for too many null bytes (likely padding/junk)
    null_count = data_chunk[:1024].count(b'\x00')
    if null_count > 512:  # More than 50% null bytes
        return False
    
    return True

def get_dayz_folder_by_extension(filename: str) -> str:
    """Maps file extensions to DayZ addon folder structure."""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    extension_mapping = {
        # Scripts
        'c': '5_Scripts',
        'cpp': '5_Scripts', 
        'hpp': '5_Scripts',
        'sqf': '5_Scripts',
        'fsm': '5_Scripts',
        'bikb': '5_Scripts',
        
        # Config files
        'cfg': '1_Config',
        'rvmat': '1_Config',
        'bisurf': '1_Config',
        
        # Models and animations
        'p3d': '2_Models',
        'mlod': '2_Models',
        'lod': '2_Models',
        'rtm': '2_Models',
        'skeleton': '2_Models',
        
        # Game data
        'paa': '3_Game/data',
        'pac': '3_Game/data',
        'jpg': '3_Game/data',
        'jpeg': '3_Game/data',
        'png': '3_Game/data',
        'tga': '3_Game/data',
        'dds': '3_Game/data',
        'edds': '3_Game/data',
        
        # World/terrain
        'wrp': '4_World',
        'tm': '4_World',
        'xyz': '4_World',
        'asc': '4_World',
        'shp': '4_World',
        'eto': '4_World',
        
        # Audio
        'ogg': '6_Audio',
        'wav': '6_Audio',
        'wss': '6_Audio',
        'lip': '6_Audio',
        
        # Anims
        'anm': '8_Anims',
        
        # Misc
        'bin': '9_Misc',
        'bisign': '9_Misc',
        'txt': '9_Misc',
        'xml': '9_Misc',
        'json': '9_Misc',
    }
    
    return extension_mapping.get(ext, '9_Misc')

def sanitize_path(path: str) -> Path:
    """Removes problematic characters and converts to a safe nested path with DayZ structure."""
    # Remove null bytes and other problematic characters
    safe_path = path.replace(";", "").replace("\x00", "").replace("\r", "").replace("\n", "")
    
    # Filter out any remaining non-printable characters
    safe_path = ''.join(c for c in safe_path if c.isprintable() or c in ['\\', '/'])
    
    parts = safe_path.split("\\")
    # Filter out empty parts
    parts = [part for part in parts if part]
    
    if not parts:
        return Path(OUTPUT_DIR) / "9_Misc" / "unknown_file"
    
    # Get the filename (last part)
    filename = parts[-1]
    
    # Determine DayZ folder based on file extension
    dayz_folder = get_dayz_folder_by_extension(filename)
    
    # Create the path: OUTPUT_DIR/DayZ_folder/sanitized_filename
    safe_filename = ''.join(c for c in filename if c.isalnum() or c in '._-')
    return Path(OUTPUT_DIR) / dayz_folder / safe_filename

def create_dayz_structure():
    """Creates the standard DayZ addon folder structure."""
    dayz_folders = [
        "1_Config",
        "2_Models", 
        "3_Game/data",
        "4_World",
        "5_Scripts",
        "6_Audio",
        "7_UI",
        "8_Anims",
        "9_Misc"
    ]
    
    for folder in dayz_folders:
        os.makedirs(Path(OUTPUT_DIR) / folder, exist_ok=True)
    
    print("[+] Created DayZ addon folder structure")

def extract_embedded_files():
    create_dayz_structure()
    
    with open(PBO_PATH, "rb") as f:
        data = f.read()
    
    matches = list(FILE_PATH_PATTERN.finditer(data))
    print(f"[+] Found {len(matches)} embedded file path(s).")
    
    junk_count = 0
    extracted_count = 0
    
    for match in matches:
        raw_path = match.group(0).decode("ascii", errors="replace")
        
        # Filter out junk paths
        if is_junk_path(raw_path):
            junk_count += 1
            print(f"[!] Filtered junk path: {raw_path}")
            continue
        
        offset = match.start()
        chunk = data[offset : offset + EXTRACT_SIZE]
        
        # Check if content looks valid
        if not has_valid_content(chunk):
            junk_count += 1
            print(f"[!] Filtered invalid content: {raw_path}")
            continue
        
        try:
            target_path = sanitize_path(raw_path)
            os.makedirs(target_path.parent, exist_ok=True)
            
            with open(target_path, "wb") as out_file:
                out_file.write(chunk)
            
            extracted_count += 1
            print(f"[✓] Extracted: {target_path}")
            
        except (ValueError, OSError) as e:
            junk_count += 1
            print(f"[!] Skipped problematic path '{raw_path}': {e}")
    
    print(f"\n[+] Extraction complete:")
    print(f"    - Extracted: {extracted_count} files")
    print(f"    - Filtered out: {junk_count} junk files")

if __name__ == "__main__":
    extract_embedded_files()