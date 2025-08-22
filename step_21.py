import os
import shutil

# === Decryption Constants ===
HGS0YYmtehRNsqu0 = 65
FKvfMYJxCW20yYBF = 0xf
TfLX6A3wPjCFybhs = 65
R0xMkh5k90T1essw = 4
YIv48kTc2kMWJ5qx = 7777
UGiapRt2QI0mOmEw = 47474747
RFt5KMqoxnRzIul5 = 0xff
UyCqLg5K2D7l15ws = 0xff
WT03173n05poC7GA = 8
RtbwvL9dPiWbCT2z = 0xff
LA1A0HRK5veKI5tW = 2048

# === Seed-Based Entropy Builder ===
class Pa3J3Ke8FDLpogWd:
    def __init__(self):
        self.BrzP4IgclV4CTfv0 = [0] * LA1A0HRK5veKI5tW
        self.YrRTHyWKeHzd5Ldt = 0

class T4QPEBrB2xOEx7Qc:
    def __init__(self):
        self.DoIeHgDE2mVRoHSc = LA1A0HRK5veKI5tW  # full buffer length 2048
        self.AQT3lGGVuJj5kIVr = Pa3J3Ke8FDLpogWd()
        
    @staticmethod
    def DOpXQxB1HYIBBK8X(seed):
        obj = T4QPEBrB2xOEx7Qc()
        buf = obj.AQT3lGGVuJj5kIVr.BrzP4IgclV4CTfv0
        
        # Initialize first 4 bytes from seed (assuming 32-bit seed)
        buf[0] = (seed >> 0) & 0xFF
        buf[1] = (seed >> 8) & 0xFF
        buf[2] = (seed >> 16) & 0xFF
        buf[3] = (seed >> 24) & 0xFF
        
        # Fill the rest using a simple XOR-based PRNG to expand entropy buffer
        for i in range(4, LA1A0HRK5veKI5tW):
            buf[i] = (buf[i-4] ^ buf[i-3] ^ 0xA5) & 0xFF  # arbitrary operation to mix bytes
        
        return obj

# === Checksum Calculator ===
def CX2ZzCFXgWXJazJn(s):
    if len(s) < 3:
        return 0
    checksum = 1337
    for i in range(3):
        h = ord(s[len(s) - 3 + i])
        checksum += ((h - HGS0YYmtehRNsqu0) & 0x3f) << (i * 4)
    return checksum

# === Decoder Core ===
def decode_string(obf_str, entropy_obj):
    if not obf_str or len(obf_str) < 4:
        return obf_str

    PtbMF1gjJOheSVEP = len(obf_str) - 3
    checksum = CX2ZzCFXgWXJazJn(obf_str)
    result = ""
    entropy_sum = 1337
    half = PtbMF1gjJOheSVEP // 2

    for i in range(half):
        a = (ord(obf_str[i * 2]) - HGS0YYmtehRNsqu0) & FKvfMYJxCW20yYBF
        b = (ord(obf_str[i * 2 + 1]) - TfLX6A3wPjCFybhs) << R0xMkh5k90T1essw

        entropy_index = (i * YIv48kTc2kMWJ5qx + PtbMF1gjJOheSVEP * UGiapRt2QI0mOmEw)
        if entropy_index < 0:
            entropy_index = -entropy_index
        entropy = entropy_obj.AQT3lGGVuJj5kIVr.BrzP4IgclV4CTfv0[entropy_index % entropy_obj.DoIeHgDE2mVRoHSc]

        value = ((a + b) ^ (777 * entropy + i * 0x9b3d)) & 0xff
        result += chr(value)
        entropy_sum += (a + b) * (i + 1) * 777

    print(f"Decoded intermediate: {repr(result)}")
    if checksum != entropy_sum:
        print(f"[!] Checksum failed: expected {checksum}, got {entropy_sum} for string: {obf_str}")
        return ""

    return result

# === Recursive Folder Traversal + Deobfuscation ===
def recursively_deobfuscate(input_path, output_path, seed):
    entropy_obj = T4QPEBrB2xOEx7Qc.DOpXQxB1HYIBBK8X(seed)

    for root, dirs, files in os.walk(input_path):
        # Compute relative path to preserve structure in output
        rel_dir = os.path.relpath(root, input_path)
        target_dir = os.path.join(output_path, rel_dir)
        os.makedirs(target_dir, exist_ok=True)

        # Deobfuscate folders
        new_dirs = []
        for dirname in dirs:
            deobf_dirname = decode_string(dirname, entropy_obj)
            if deobf_dirname:
                new_dirs.append(deobf_dirname)
            else:
                new_dirs.append(dirname)
        # Modify dirs in place so os.walk continues with renamed folders
        dirs[:] = new_dirs

        # Deobfuscate files
        for filename in files:
            deobf_name = decode_string(filename, entropy_obj)
            if not deobf_name:
                deobf_name = filename

            src_file_path = os.path.join(root, filename)
            dest_file_path = os.path.join(target_dir, deobf_name)

            # Read and decode file content if possible
            try:
                with open(src_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                decoded_content = decode_string(content, entropy_obj)
                if decoded_content == "":
                    # If decoding fails checksum, fallback to original content
                    decoded_content = content
                with open(dest_file_path, "w", encoding="utf-8") as f:
                    f.write(decoded_content)
            except Exception as e:
                # Binary or unreadable files get copied as-is
                shutil.copy2(src_file_path, dest_file_path)
                print(f"[!] Could not decode file content: {src_file_path} ({e}), copied as-is.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Recursive deobfuscator for extracted files")
    parser.add_argument("input_path", help="Path to extracted obfuscated folder")
    parser.add_argument("output_path", help="Path to save decoded files/folders")
    parser.add_argument("--seed", type=lambda x: int(x, 0), required=True, help="Decryption seed (e.g., 0x1234)")

    args = parser.parse_args()

    if not os.path.isdir(args.input_path):
        print("[!] Input path is not a directory.")
        exit(1)

    os.makedirs(args.output_path, exist_ok=True)

    print(f"[*] Starting deobfuscation with seed {hex(args.seed)}")
    recursively_deobfuscate(args.input_path, args.output_path, args.seed)
    print("[+] Deobfuscation complete.")
