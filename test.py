import os
import shutil

# === Decryption Constants ===
HGS0YYmtehRNsqu0 = 65
FKvfMYJxCW20yYBF = 0xf
TfLX6A3wPjCFybhs = 65
R0xMkh5k90T1essw = 4
YIv48kTc2kMWJ5qx = 7777
UGiapRt2QI0mOmEw = 47474747
K1Rl3Ma2QJMSudzZ = 0
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
        self.DoIeHgDE2mVRoHSc = 0
        self.AQT3lGGVuJj5kIVr = Pa3J3Ke8FDLpogWd()

    @staticmethod
    def DOpXQxB1HYIBBK8X(seed):
        obj = T4QPEBrB2xOEx7Qc()
        obj.DoIeHgDE2mVRoHSc = 2  # arbitrary default
        obj.AQT3lGGVuJj5kIVr.BrzP4IgclV4CTfv0[obj.AQT3lGGVuJj5kIVr.YrRTHyWKeHzd5Ldt] = seed & RFt5KMqoxnRzIul5
        obj.AQT3lGGVuJj5kIVr.YrRTHyWKeHzd5Ldt += 1
        if (seed & UyCqLg5K2D7l15ws) != seed:
            obj.AQT3lGGVuJj5kIVr.BrzP4IgclV4CTfv0[obj.AQT3lGGVuJj5kIVr.YrRTHyWKeHzd5Ldt] = (seed >> WT03173n05poC7GA) & RtbwvL9dPiWbCT2z
            obj.AQT3lGGVuJj5kIVr.YrRTHyWKeHzd5Ldt += 1
            obj.DoIeHgDE2mVRoHSc = 3
        return obj

# === Decoder Core ===
def CX2ZzCFXgWXJazJn(s):
    checksum = 1337
    for i in range(3):
        h = ord(s[len(s) - 3 + i])
        checksum += ((h - 65) & 0x3f) << (i * 4)
    return checksum

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

    return result if checksum == entropy_sum else ""

# === Recursive Renamer and File Deobfuscator ===
def recursively_deobfuscate(path, seed):
    entropy_obj = T4QPEBrB2xOEx7Qc.DOpXQxB1HYIBBK8X(seed)

    for root, dirs, files in os.walk(path, topdown=False):
        # Deobfuscate files
        for filename in files:
            obf_file_path = os.path.join(root, filename)
            deobf_name = decode_string(filename, entropy_obj)
            if deobf_name:
                new_file_path = os.path.join(root, deobf_name)
                os.rename(obf_file_path, new_file_path)
                try:
                    with open(new_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    new_content = decode_string(content, entropy_obj)
                    with open(new_file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                except Exception as e:
                    print(f"[!] Could not decode file content: {new_file_path} — {e}")

        # Deobfuscate folders
        for dirname in dirs:
            obf_dir_path = os.path.join(root, dirname)
            deobf_dirname = decode_string(dirname, entropy_obj)
            if deobf_dirname:
                new_dir_path = os.path.join(root, deobf_dirname)
                os.rename(obf_dir_path, new_dir_path)

# === Entry Point ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Recursive DayZ PBO Deobfuscator")
    parser.add_argument("path", help="Path to root of extracted obfuscated folder")
    parser.add_argument("--seed", type=lambda x: int(x, 0), required=True, help="Decryption seed (e.g., 0xDEADBEEF)")

    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print("[!] Provided path is not a directory.")
        exit(1)

    recursively_deobfuscate(args.path, args.seed)
    print("[+] Deobfuscation complete.")
