#!/usr/bin/env python3
"""
PBO Junk File Filter
Removes obfuscated/junk files from extracted PBO contents
"""

import os
import re
import argparse
import shutil
from pathlib import Path
from typing import List, Tuple

class JunkFileFilter:
    def __init__(self, verbose: bool = False, dry_run: bool = False):
        self.verbose = verbose
        self.dry_run = dry_run
        self.stats = {
            'total_files': 0,
            'junk_files': 0,
            'junk_dirs': 0,
            'bytes_saved': 0
        }
    
    def is_junk_filename(self, filepath: Path) -> bool:
        """Detect if filename appears to be junk/obfuscation"""
        filename = filepath.name
        full_path = str(filepath)
        
        # Very long random character sequences
        if re.search(r'[A-Za-z0-9]{20,}', filename):
            return True
        
        # Semicolons or colons in filename/extension
        if re.search(r'[;:]', filename):
            return True
        
        # Multiple suspicious extensions
        if filename.count('.') > 3:
            return True
        
        # Suspicious extension patterns
        if re.search(r'\.[^.]*[;:][^.]*$', filename):
            return True
        
        # Random uppercase sequences
        if len(re.findall(r'[A-Z]{4,}', filename)) > 2:
            return True
        
        # Files with LPT, COM, AUX patterns (Windows reserved + obfuscation)
        if re.search(r'\b(LPT\d+|COM\d+|AUX)\b', full_path, re.IGNORECASE):
            return True
        
        # Very short or very long filenames (excluding extension)
        name_only = filepath.stem
        if len(name_only) > 50 or (len(name_only) < 3 and not filepath.suffix):
            return True
        
        return False
    
    def is_junk_content(self, filepath: Path) -> bool:
        """Detect if file content appears to be junk/obfuscation"""
        try:
            if filepath.stat().st_size == 0:
                return True
            
            # Don't analyze very large files (likely legitimate)
            if filepath.stat().st_size > 1024 * 1024:  # 1MB
                return False
            
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # Try to decode as text
            try:
                text = content.decode('utf-8', errors='ignore')
            except:
                try:
                    text = content.decode('latin-1', errors='ignore')
                except:
                    return False  # Binary file, keep it
            
            # Empty or whitespace only
            if not text.strip():
                return True
            
            # Common junk patterns
            junk_patterns = [
                r'^\s*/\*\*\s*$',  # Just "/**"
                r'^\s*/\*\s*//\s*\*/\s*$',  # Just "/* // */"
                r'^\s*/\*.*\*/\s*$',  # Single line comment blocks only
                r'^#include\s+"[^"]*[;:][^"]*".*$',  # Include with semicolons/colons
            ]
            
            for pattern in junk_patterns:
                if re.match(pattern, text.strip(), re.MULTILINE | re.DOTALL):
                    return True
            
            # Check for obfuscated include statements
            if text.strip().startswith('#include') and len(text.strip().split('\n')) == 1:
                include_path = text.strip()
                if re.search(r'[;:]', include_path) or len(include_path) > 200:
                    return True
            
            # Excessive random character sequences
            random_sequences = re.findall(r'[A-Za-z]{10,}', text)
            if len(random_sequences) > 10:
                # Check if they look random (high ratio of uppercase)
                random_count = sum(1 for seq in random_sequences 
                                 if sum(1 for c in seq if c.isupper()) / len(seq) > 0.3)
                if random_count > 5:
                    return True
            
            # Files that are mostly comments and random identifiers
            lines = text.split('\n')
            comment_lines = sum(1 for line in lines if line.strip().startswith(('/*', '//', '*')))
            if len(lines) > 0 and comment_lines / len(lines) > 0.8:
                return True
            
            return False
            
        except Exception as e:
            if self.verbose:
                print(f"Error analyzing {filepath}: {e}")
            return False
    
    def is_junk_directory(self, dirpath: Path) -> bool:
        """Detect if directory name appears to be junk"""
        dirname = dirpath.name
        
        # Very long random sequences
        if re.search(r'[A-Za-z0-9]{15,}', dirname):
            return True
        
        # Contains semicolons or other suspicious chars
        if re.search(r'[;:]', dirname):
            return True
        
        # LPT/COM patterns
        if re.search(r'\b(LPT\d+|COM\d+|AUX)\b', dirname, re.IGNORECASE):
            return True
        
        return False
    
    def should_keep_file(self, filepath: Path) -> bool:
        """Determine if file should be kept (not junk)"""
        # Always keep certain file types
        keep_extensions = {'.cfg', '.cpp', '.hpp', '.c', '.h', '.txt', '.md', '.json', '.xml'}
        if filepath.suffix.lower() in keep_extensions and filepath.stat().st_size > 10:
            # But still check for junk content in code files
            if filepath.suffix.lower() in {'.c', '.cpp', '.hpp', '.h'}:
                return not self.is_junk_content(filepath)
            return True
        
        # Check filename patterns
        if self.is_junk_filename(filepath):
            return False
        
        # Check content
        if self.is_junk_content(filepath):
            return False
        
        return True
    
    def filter_files(self, directory: Path) -> None:
        """Filter junk files from directory"""
        if not directory.exists():
            print(f"Directory not found: {directory}")
            return
        
        print(f"Filtering junk files from: {directory}")
        print(f"Dry run: {'Yes' if self.dry_run else 'No'}")
        print("-" * 50)
        
        # Collect all files first
        all_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                filepath = Path(root) / file
                all_files.append(filepath)
        
        self.stats['total_files'] = len(all_files)
        
        # Process files
        for filepath in all_files:
            try:
                file_size = filepath.stat().st_size
                
                if not self.should_keep_file(filepath):
                    self.stats['junk_files'] += 1
                    self.stats['bytes_saved'] += file_size
                    
                    if self.verbose:
                        print(f"JUNK FILE: {filepath} ({file_size} bytes)")
                    
                    if not self.dry_run:
                        filepath.unlink()
                
            except Exception as e:
                if self.verbose:
                    print(f"Error processing {filepath}: {e}")
        
        # Remove empty directories (junk dirs and dirs emptied by file removal)
        self.remove_empty_directories(directory)
        
        self.print_stats()
    
    def remove_empty_directories(self, directory: Path) -> None:
        """Remove empty directories, including junk named directories"""
        for root, dirs, files in os.walk(directory, topdown=False):
            for dirname in dirs:
                dirpath = Path(root) / dirname
                try:
                    # Check if directory is empty or contains only junk
                    if self.is_directory_empty_or_junk(dirpath):
                        is_junk_name = self.is_junk_directory(dirpath)
                        
                        if is_junk_name or not any(dirpath.iterdir()):
                            self.stats['junk_dirs'] += 1
                            
                            if self.verbose:
                                reason = "junk name" if is_junk_name else "empty"
                                print(f"JUNK DIR ({reason}): {dirpath}")
                            
                            if not self.dry_run:
                                shutil.rmtree(dirpath)
                
                except Exception as e:
                    if self.verbose:
                        print(f"Error processing directory {dirpath}: {e}")
    
    def is_directory_empty_or_junk(self, dirpath: Path) -> bool:
        """Check if directory is empty or contains only junk"""
        try:
            contents = list(dirpath.iterdir())
            if not contents:
                return True
            
            # If it has a junk name, remove it regardless
            if self.is_junk_directory(dirpath):
                return True
            
            # Check if all contents are junk files
            for item in contents:
                if item.is_file():
                    if self.should_keep_file(item):
                        return False
                elif item.is_dir():
                    if not self.is_directory_empty_or_junk(item):
                        return False
            
            return True
            
        except Exception:
            return False
    
    def print_stats(self) -> None:
        """Print filtering statistics"""
        print("\n" + "=" * 50)
        print("FILTERING RESULTS")
        print("=" * 50)
        print(f"Total files processed: {self.stats['total_files']}")
        print(f"Junk files removed: {self.stats['junk_files']}")
        print(f"Junk directories removed: {self.stats['junk_dirs']}")
        print(f"Space saved: {self.stats['bytes_saved']:,} bytes ({self.stats['bytes_saved'] / 1024:.1f} KB)")
        
        if self.stats['total_files'] > 0:
            junk_percent = (self.stats['junk_files'] / self.stats['total_files']) * 100
            print(f"Junk percentage: {junk_percent:.1f}%")
        
        if self.dry_run:
            print("\n⚠️  This was a dry run - no files were actually deleted!")

def main():
    parser = argparse.ArgumentParser(
        description='Filter junk/obfuscated files from extracted PBO contents'
    )
    parser.add_argument(
        'directory', 
        help='Directory containing extracted PBO files to filter'
    )
    parser.add_argument(
        '-v', '--verbose', 
        action='store_true', 
        help='Verbose output showing each file processed'
    )
    parser.add_argument(
        '-n', '--dry-run', 
        action='store_true', 
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--backup', 
        action='store_true', 
        help='Create backup before filtering'
    )
    
    args = parser.parse_args()
    
    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist")
        return 1
    
    # Create backup if requested
    if args.backup and not args.dry_run:
        backup_dir = directory.parent / f"{directory.name}_backup"
        print(f"Creating backup at: {backup_dir}")
        shutil.copytree(directory, backup_dir)
    
    # Filter files
    filter_tool = JunkFileFilter(verbose=args.verbose, dry_run=args.dry_run)
    filter_tool.filter_files(directory)
    
    return 0

if __name__ == "__main__":
    exit(main())