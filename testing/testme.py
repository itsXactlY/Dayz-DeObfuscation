#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path
from dayz_dev_tools import pbo_reader
import io
import re
import typing
from dayz_dev_tools import config_cpp, pbo_file

INVALID_FILENAME_RE = re.compile(b"[\t?*\x80-\xff;]")  # Added semicolon
OBFUSCATE_RE = re.compile(
    b'^(?:(?://[^\\r\\n]*|/\\*(?:\\*(?!\\/)|[^*])*\\*/)\\r\\n)?#include "([^"]+)"\\r\\n$')

def _invalid_filename(filename: bytes) -> bool:
    return INVALID_FILENAME_RE.search(filename) is not None

def _safe_filename_parts(parts):
    """Convert bytes filename parts to safe string parts with aggressive cleaning"""
    string_parts = []
    for part in parts:
        if isinstance(part, bytes):
            try:
                string_part = part.decode('utf-8', errors='replace')
            except:
                string_part = part.decode('latin-1', errors='replace')
            
            # More aggressive character replacement
            replacements = {
                '?': '_', '*': '_', '<': '_', '>': '_', 
                '|': '_', ':': '_', '"': '_', '\t': '_',
                '/': '_', '\\': '_', ';': '_', ' ': '_',
                '\n': '_', '\r': '_', '\x00': '_'
            }
            
            for old, new in replacements.items():
                string_part = string_part.replace(old, new)
            
            # Remove any remaining problematic characters
            string_part = re.sub(r'[^\w\-_.]', '_', string_part)
            
            # Ensure it's not empty and doesn't start/end with dots
            if not string_part or string_part in ['.', '..']:
                string_part = 'unnamed_file'
            
            string_part = string_part.strip('.')
            if not string_part:
                string_part = 'unnamed_file'
                
            string_parts.append(string_part)
        else:
            string_parts.append(str(part))
    
    return string_parts

_deobfs_count = 0

def _extract_file_safe(
    reader: pbo_reader.PBOReader, pbofile: pbo_file.PBOFile, verbose: bool, 
    deobfuscate: bool, cfgconvert: typing.Optional[str], ignored: typing.List[bytes]
) -> None:
    global _deobfs_count
    
    try:
        # Skip problematic obfuscated files
        if deobfuscate and (
                (pbofile.filename in ignored)
                or (_invalid_filename(pbofile.filename) and not pbofile.filename.endswith(b".c"))):
            if verbose:
                print(f"Skipping obfuscation file: {pbofile.normalized_filename()}")
            return

        prefix = reader.prefix()
        parts = pbofile.split_filename()

        if len(parts) == 0 or len(parts[-1]) == 0:
            if verbose:
                print("Skipping empty filename")
            return

        # Convert to safe filename parts
        safe_parts = _safe_filename_parts(parts)

        # Create directory structure with error handling
        if len(safe_parts) > 1:
            dir_path = os.path.join(*safe_parts[:-1])
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                # If directory creation fails, flatten the structure
                if verbose:
                    print(f"Directory creation failed, flattening: {e}")
                safe_parts = ['_'.join(safe_parts[:-1]) + '_' + safe_parts[-1]]

        # Handle config.bin conversion
        if parts[-1].lower() == b"config.bin" and cfgconvert is not None:
            converted_filename = os.path.join(
                os.path.dirname(os.path.join(*safe_parts)), "config.cpp")

            if verbose:
                print(f"Converting {pbofile.normalized_filename()} -> {converted_filename}")

            buffer = io.BytesIO()
            pbofile.unpack(buffer)
            try:
                cpp_content = config_cpp.bin_to_cpp(buffer.getvalue(), cfgconvert)
                with open(converted_filename, "w+b") as out_file:
                    out_file.write(cpp_content)
                    return
            except Exception as error:
                if verbose:
                    print(f"Failed to convert {pbofile.normalized_filename()}: {error}")

        renamed_filename: typing.Optional[str] = None

        # Handle obfuscated .c files
        if deobfuscate and _invalid_filename(parts[-1]) and parts[-1].endswith(b".c"):
            safe_parts[-1] = f"deobfs{_deobfs_count:05}.c"
            _deobfs_count += 1
            renamed_filename = os.path.join(*safe_parts)

        # Final filename safety check
        final_filename = os.path.join(*safe_parts)
        if len(final_filename) > 200:  # Truncate very long filenames
            name, ext = os.path.splitext(safe_parts[-1])
            safe_parts[-1] = f"{name[:100]}_{_deobfs_count:05}{ext}"
            _deobfs_count += 1
            final_filename = os.path.join(*safe_parts)

        # Extract the file
        with open(final_filename, "w+b") as out_file:
            if verbose:
                if renamed_filename is None:
                    print(f"Extracting {pbofile.normalized_filename()}")
                else:
                    print(f"Extracting {pbofile.normalized_filename()} -> {renamed_filename}")

            if deobfuscate:
                buffer = io.BytesIO()
                pbofile.unpack(buffer)
                content = buffer.getvalue()

                if (match := OBFUSCATE_RE.match(content)) is not None:
                    target_filename = match.group(1)

                    if prefix is not None and not target_filename.startswith(prefix + b"\\"):
                        target_filename = prefix + b"\\" + target_filename

                    unobfuscated = reader.file(target_filename)

                    if unobfuscated is None:
                        if verbose:
                            print(f"Unable to deobfuscate {pbofile.normalized_filename()}")
                        out_file.write(content)
                    else:
                        ignored.append(unobfuscated.filename)
                        unobfuscated.unpack(out_file)
                else:
                    out_file.write(content)
            else:
                pbofile.unpack(out_file)
    
    except Exception as e:
        # Last resort: create a safe fallback filename
        safe_filename = f"failed_extraction_{_deobfs_count:05d}.bin"
        _deobfs_count += 1
        if verbose:
            print(f"Extraction failed for {pbofile.normalized_filename()}, saving as: {safe_filename} - Error: {e}")
        
        try:
            with open(safe_filename, "wb") as out_file:
                pbofile.unpack(out_file)
        except Exception as final_error:
            if verbose:
                print(f"Complete failure extracting {pbofile.normalized_filename()}: {final_error}")

def extract_pbo_with_error_handling(
    reader: pbo_reader.PBOReader, files_to_extract: typing.List[str], *, verbose: bool,
    deobfuscate: bool, cfgconvert: typing.Optional[str]
) -> None:
    global _deobfs_count
    _deobfs_count = 0

    ignored: typing.List[bytes] = []
    successful_extractions = 0
    failed_extractions = 0

    files_list = list(reader.files()) if len(files_to_extract) == 0 else []
    
    if len(files_to_extract) == 0:
        for file in files_list:
            try:
                _extract_file_safe(reader, file, verbose, deobfuscate, cfgconvert, ignored)
                successful_extractions += 1
            except Exception as e:
                failed_extractions += 1
                if verbose:
                    print(f"Failed to extract {file.normalized_filename()}: {e}")
                continue
    else:
        for file_to_extract in files_to_extract:
            try:
                pbofile = reader.file(file_to_extract)
                if pbofile is None:
                    print(f"File not found: {file_to_extract}")
                    failed_extractions += 1
                    continue
                _extract_file_safe(reader, pbofile, verbose, deobfuscate, cfgconvert, [])
                successful_extractions += 1
            except Exception as e:
                failed_extractions += 1
                if verbose:
                    print(f"Failed to extract {file_to_extract}: {e}")
                continue
    
    print(f"\nExtraction Summary:")
    print(f"  Successful: {successful_extractions}")
    print(f"  Failed: {failed_extractions}")

def extract_pbo_files(pbo_path, output_dir="./extracted", verbose=True, deobfuscate=True, files_to_extract=None):
    """Extract files from PBO archive with improved error handling"""
    if files_to_extract is None:
        files_to_extract = []
    
    # Only apply deobfuscation if PBO is in the target folder
    target_folder = "/home/alca/Schreibtisch/test/AdvancedGroups_Server_latest/"
    should_deobfuscate = deobfuscate and os.path.abspath(pbo_path).startswith(os.path.abspath(target_folder))
    
    os.makedirs(output_dir, exist_ok=True)
    original_dir = os.getcwd()
    os.chdir(output_dir)
    
    try:
        with open(pbo_path, 'rb') as pbo_file:
            reader = pbo_reader.PBOReader(pbo_file)
            extract_pbo_with_error_handling(
                reader=reader,
                files_to_extract=files_to_extract,
                verbose=verbose,
                deobfuscate=should_deobfuscate,
                cfgconvert=None
            )
        
        print(f"Extraction completed to: {output_dir}")
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        # Don't re-raise the error, just report it
        
    finally:
        os.chdir(original_dir)

def list_pbo_contents(pbo_path):
    """List all files in a PBO archive"""
    try:
        with open(pbo_path, 'rb') as pbo_file:
            reader = pbo_reader.PBOReader(pbo_file)
            print(f"PBO: {pbo_path}")
            print(f"Prefix: {reader.prefix()}")
            print(f"\nTotal files: {len(list(reader.files()))}")
            print("\nFiles (first 20):")
            
            for i, file in enumerate(reader.files()):
                if i >= 20:
                    print("  ... (showing first 20 files only)")
                    break
                print(f"  {file.normalized_filename()} ({file.data_size} bytes)")
    except Exception as e:
        print(f"Error listing PBO contents: {e}")

def main():
    parser = argparse.ArgumentParser(description='Extract files from PBO archives')
    parser.add_argument('pbo_file', help='Path to the PBO file')
    parser.add_argument('-o', '--output', default='./extracted', help='Output directory')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-d', '--deobfuscate', action='store_true', help='Attempt deobfuscation')
    parser.add_argument('-l', '--list', action='store_true', help='List contents only')
    parser.add_argument('-f', '--files', nargs='+', help='Specific files to extract')
    
    args = parser.parse_args()
    
    if not Path(args.pbo_file).exists():
        print(f"Error: PBO file '{args.pbo_file}' not found")
        sys.exit(1)
    
    if args.list:
        list_pbo_contents(args.pbo_file)
    else:
        extract_pbo_files(
            pbo_path=args.pbo_file,
            output_dir=args.output,
            verbose=args.verbose,
            deobfuscate=args.deobfuscate,
            files_to_extract=args.files
        )

if __name__ == "__main__":
    main()