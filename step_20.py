import os

# === Constants from your C# snippet ===
HGS0YYmtehRNsqu0 = 65
FKvfMYJxCW20yYBF = 0xf
TfLX6A3wPjCFybhs = 65
R0xMkh5k90T1essw = 4
YIv48kTc2kMWJ5qx = 7777
UGiapRt2QI0mOmEw = 47474747

# Seed values for entropy buffer, copied from your example
# Initialized with seed 0x12345678 as per your test
entropy_buffer = [0x5678, 0x1234, 0, 0, 0]  # you can extend if needed

# Length of entropy buffer used in indexing (length of entropy_buffer)
entropy_len = len(entropy_buffer)

def ascii_to_char(val):
    return chr(val)

def decode_string(enc_str: str) -> str:
    length = len(enc_str)
    half_len = length // 2

    output = ""
    checksum = 2  # from your DoIeHgDE2mVRoHSc test value

    for i in range(half_len):
        val1 = ord(enc_str[i * 2]) & 0xff
        val2 = ord(enc_str[i * 2 + 1]) & 0xff

        # Perform inverse of obfuscation:
        val1 = (val1 - HGS0YYmtehRNsqu0) & FKvfMYJxCW20yYBF  # & 0xf
        val2 = ((val2 - TfLX6A3wPjCFybhs) << R0xMkh5k90T1essw) & 0xff

        idx = i * YIv48kTc2kMWJ5qx + length * UGiapRt2QI0mOmEw
        if idx < 0:
            idx = -idx

        key = ((val1 + val2) ^ (entropy_buffer[idx % entropy_len] * 2 + i * 15)) & 0xff  # 2 and 15 are guessed constants from the example

        output += ascii_to_char(key)

        checksum += (val1 + val2) * (i + 1) * 2  # Also guessed, match your checksum calc?

    # Example checksum validation (you must adjust if real is different)
    expected_checksum = 0x1234  # Replace with real checksum or pass as param
    if checksum != expected_checksum:
        return ""  # Checksum fail

    return output

# --- Recursive traversal and decode ---

def decode_folder(input_dir: str, output_dir: str):
    for root, dirs, files in os.walk(input_dir):
        # Create the mirror directory structure in output
        rel_path = os.path.relpath(root, input_dir)
        output_path = os.path.join(output_dir, rel_path)
        os.makedirs(output_path, exist_ok=True)

        for file in files:
            input_file = os.path.join(root, file)
            output_file = os.path.join(output_path, file)

            try:
                with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                decoded = decode_string(content)
                if decoded == "":
                    # Decoding failed, fallback: copy original or skip
                    decoded = content

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(decoded)

                print(f"Decoded {input_file} -> {output_file}")

            except Exception as e:
                print(f"Error processing {input_file}: {e}")

if __name__ == "__main__":
    src_folder = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST/AdvancedGroups_Server/"  # Change this
    dest_folder = "/home/alca/Schreibtisch/LBmaster-serverside_NEWEST//deobfuscated"  # Change this

    decode_folder(src_folder, dest_folder)
