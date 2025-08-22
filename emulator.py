# pbo_vm_emulator.py
import os
import struct
import re
from pathlib import Path

# === STEP 1: Basic .PBO Parser ===
class PBOFile:
    def __init__(self, path):
        self.path = Path(path)
        self.entries = []
        self.data = {}
        self._parse()

    def _parse(self):
        with open(self.path, 'rb') as f:
            while True:
                name = b""
                while (b := f.read(1)) != b'\x00':
                    name += b
                if not name:
                    break  # terminator
                orig_size = struct.unpack('<I', f.read(4))[0]
                _ = f.read(12)  # reserved
                self.entries.append((name.decode(), orig_size))

            for name, size in self.entries:
                self.data[name] = f.read(size)

    def extract_all(self, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        for name, content in self.data.items():
            out_path = Path(output_dir) / name
            os.makedirs(out_path.parent, exist_ok=True)
            with open(out_path, 'wb') as f:
                f.write(content)


# === STEP 2: Minimal Script Emulator with Heuristics ===
class FakeVM:
    def __init__(self):
        self.context = {
            'player': 'mockPlayer',
            'missionNamespace': {},
        }
        self.heuristics = {
            'call_compile_count': 0,
            'remote_urls': set(),
        }

    def run_script(self, script, source_name='unknown'):
        for line in script.splitlines():
            self.eval_line(line.strip(), source_name)

    def eval_line(self, line, src):
        if not line or line.startswith('//'):
            return

        if 'compile preprocessFileLineNumbers' in line:
            match = re.search(r'"(.*?)"', line)
            if match:
                file = match.group(1)
                print(f"[DETECTED] compile-preprocess: {file} in {src}")

        if 'call compile' in line or 'compile (' in line:
            self.heuristics['call_compile_count'] += 1
            print(f"[HEURISTIC] call compile in {src}: {line}")

        if 'http://' in line or 'https://' in line:
            urls = re.findall(r'https?://\S+",?', line)
            for url in urls:
                self.heuristics['remote_urls'].add(url.strip('"'))
                print(f"[REMOTE URL] {url} in {src}")

        if line.startswith("diag_log"):
            msg = line.split(None, 1)[-1].strip("();\"")
            print(f"[LOG] {msg}")
        elif "loadFile" in line:
            print(f"[LOAD FILE] {line}")
        elif "call" in line:
            print(f"[CALL] {line}")
        elif "compile" in line:
            print(f"[COMPILE] {line}")
        else:
            print(f"[UNHANDLED] {line}")

    def report(self):
        print("\n=== HEURISTIC REPORT ===")
        print(f"call compile count: {self.heuristics['call_compile_count']}")
        if self.heuristics['remote_urls']:
            print("remote urls:")
            for url in self.heuristics['remote_urls']:
                print(f"  - {url}")
        print("========================")


# === STEP 3: Main Loader with Obfuscation Emulation ===
def emulate_decryption(s):
    if re.match(r'"[A-Za-z0-9+/=]{20,}"', s):
        print(f"[DECRYPT EMU] Detected base64-like encrypted string: {s}")
        return "<decrypted_string>"
    return s

def main(pbo_path, extract_dir):
    print(f"[*] Parsing {pbo_path}...")
    pbo = PBOFile(pbo_path)
    pbo.extract_all(extract_dir)
    print(f"[*] Extracted to {extract_dir}")

    vm = FakeVM()
    for filename, content in pbo.data.items():
        if filename.endswith(".sqf") or filename.endswith(".fsm"):
            print(f"[*] Running {filename}...")
            try:
                decoded = content.decode(errors='ignore')
                decoded = emulate_decryption(decoded)
                vm.run_script(decoded, filename)
            except Exception as e:
                print(f"[ERROR] in {filename}: {e}")

    vm.report()


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <input.pbo> <extract_dir>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])