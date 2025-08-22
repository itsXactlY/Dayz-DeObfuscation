import os
import hashlib
import struct

# Define the decoding and processing functions
def decode_value(key, context=""):
    # Fix: Convert hex to int first, then to float
    hex_value = hashlib.sha256((key + context).encode()).hexdigest()[:8]
    int_value = int(hex_value, 16)
    return float(int_value)

def process_input_string(input_string, context=""):
    try:
        value1 = decode_value("HCOJJAGJHPOKCHJEIEPCCIGNHJDLGJPOBGIGNLFHOFIO", context)
        value2 = decode_value("GCBIPBBJEPKKAHMENEACFIHNPJDLNJLOKGNGDIDBKODG", context)
        value3 = decode_value("MOHJAFPKGKDAFPODGPHJDPNMKFMEPAIMEHPAKMLDPOFEFDLK", context)
        value4 = decode_value("ECBIABEJBPKKHHGELEFCFIGNEJBLGJEOBGLGNHNGMHAL", context)
        value5 = decode_value("NCDOGBBDOOEMGLPOPNMIKPCCIEAOFJMBHECKNJCKKH", context)
        value6 = decode_value("GCBIOBCJHPNKMHJEKECCAIKNAJBLDJNOEGJGADDCHKKI", context)
        vector1 = (1, 1, 1)  
        value7 = decode_value("GCBIOBBJDPKKFHOEAEBCFIINCJDLNJMOCGEGIFLPFEHC", context)
        string1 = decode_value("LAEMBPGBMBJNEFMAFHGPLDALDNEM", context)  
        value8 = decode_value("LMDCPKJMHDEOJNIBBKCMHPOHOKNDCGJLGFHFMCKEIMFBGE", context)
        value9 = decode_value("LMDCMKPMFDBOBNPBPKFMBPIHOKODOGJLBFKFJCNIJMBBLM", context)
        value10 = decode_value("CCDOGBBDMOGMGLKOANIIPPLCKEBODJEBGEOCCJOMOB", context)
        value11 = decode_value("HCHJGBMIDPKKFHPEPEGCJIKNBJBLMJJOGGEGCJHDHFID", context)
        value12 = decode_value("ICMPPBJCPOAMALNOCNKIMPCCMEAOEJFBPEDOMLECJB", context)
        vector2 = (2, 3, 4)  
        value13 = decode_value("DCAODBBDJOGMILPODNDIIPCCMEBOEJEBIECDMHFCPF", context)
        value14 = decode_value("GCBIEBKJJPKKMHKEOEPCJIGNHJDLGJIOCGFGBBNHBEIC", context)
        vector3 = (5, 6, 7)  
        string2 = decode_value("OOLAOALOJKAN", context)  
        string3 = decode_value("OOLAOALOJKAN", context)  

        # Check if input_string is long enough for the slice operation
        if len(input_string) < 43:
            raise ValueError(f"Input string too short: {len(input_string)} < 43")
        
        result1 = (-547234341 - int(hashlib.md5(input_string[35:43].encode()).hexdigest(), 16) * 1983144419) ^ -1899935677

        return {
            'values': [value1, value2, value3, value4, value5, value6, value7, value8, value9, value10, value11, value12, value13, value14],
            'vectors': [vector1, vector2, vector3],
            'strings': [string1, string2, string3],
            'result': result1,
            'original': input_string
        }
    except Exception as e:
        raise Exception(f"Error in process_input_string: {str(e)}")

def process_input_string2(input_string, context=""):
    try:
        value15 = decode_value("BINJDEMEPDMFNEJHMMGPHJKI", context)
        vector4 = (8, 9, 10)  
        vector5 = (11, 12, 13)  
        value16 = decode_value("GCBIABCJBPKKGHJEJEFCAIMNDJGLCJIOCGOGDPNOLHMC", context)
        string4 = decode_value("FJDGLCFEGKNCDHKMPBCIGMEGBJ", context)  
        value17 = decode_value("DCBOCBBDKOHMCLKOENCILPKCNEGOEJNBHEEHJPCDHL", context)
        
        # Check if input_string is long enough for the slice operation
        if len(input_string) < 116:
            raise ValueError(f"Input string too short: {len(input_string)} < 116")
        
        result2 = (872895793 - int(hashlib.md5(input_string[109:116].encode()).hexdigest(), 16) * 1544140062) ^ -531823200

        value18 = decode_value("MCGOBBBDJOHMJLIOONJIMPCCMEAOAJPBGEJKNOBGOM", context)
        vector6 = (14, 15, 16)  
        value19 = decode_value("GNMDDLIMFDHOKNKBLKFMAPBHLKFDEGKLHFAFLCMILGGIBB", context)
        vector7 = (17, 18, 19)  
        string5 = decode_value("JKLFMEELLCKNCCEFOCCPJJPJKFHDCH", context)  
        string6 = decode_value("JKLFMEELLCKNCCEFOCCPJJPJKFHDCH", context)  

        return {
            'values': [value15, value16, value17, value18, value19],
            'vectors': [vector4, vector5, vector6, vector7],
            'strings': [string4, string5, string6],
            'result': result2,
            'original': input_string
        }
    except Exception as e:
        raise Exception(f"Error in process_input_string2: {str(e)}")

def reverse_process_input_string(output_dict):
    result1 = output_dict['result']
    try:
        calc_value = (-result1 - 547234341 + 1899935677) // 1983144419
        if calc_value < 0:
            calc_value = abs(calc_value)
        fake_hash = hex(calc_value)[2:].zfill(8)
        fake_substring = bytes.fromhex(fake_hash).decode('latin1', errors='ignore')  
        fake_input_string = "A" * 35 + fake_substring + "B" * (100 - 43)
        fake_input_string = fake_input_string.replace("50", "#").replace("05", "50").replace("#", "05")
        return fake_input_string
    except Exception as e:
        return f"Could not reverse process: {str(e)}"

def reverse_process_input_string2(output_dict):
    result2 = output_dict['result']
    try:
        calc_value = (872895793 - result2 + 531823200) // 1544140062
        if calc_value < 0:
            calc_value = abs(calc_value)
        fake_hash = hex(calc_value)[2:].zfill(8)
        fake_substring = bytes.fromhex(fake_hash).decode('latin1', errors='ignore')  
        fake_input_string = "A" * 109 + fake_substring + "B" * (150 - 116)
        fake_input_string = fake_input_string.replace("31", "#").replace("13", "31").replace("#", "13")
        return fake_input_string
    except Exception as e:
        return f"Could not reverse process: {str(e)}"

def is_encoded_file(file_path):
    try:
        # Try different encodings
        encodings = ['utf-8', 'latin1', 'cp1252', 'ascii']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read(1000)  # Read more characters for better detection
                    if "GA91UCDQYUVawLMs" in content or "EVy2D5PaA01T99Ml" in content:
                        return True, encoding, content
            except UnicodeDecodeError:
                continue
        
        # If text reading fails, try binary mode
        try:
            with open(file_path, 'rb') as f:
                content = f.read(1000)
                content_str = content.decode('latin1', errors='ignore')
                if "GA91UCDQYUVawLMs" in content_str or "EVy2D5PaA01T99Ml" in content_str:
                    return True, 'binary', content_str
        except:
            pass
            
        return False, None, None
    except Exception as e:
        print(f"Error checking file {file_path}: {str(e)}")
        return False, None, None

def try_multiple_contexts(content, process_func):
    """Try multiple common context strings to see if any produce meaningful results"""
    common_contexts = [
        "",  # Empty context
        "default",
        "secret",
        "password", 
        "key",
        "context",
        "decode",
        "obfuscate",
        "hidden",
        "private",
        "test",
        "admin",
        "root",
        "config"
    ]
    
    results = []
    errors = []
    
    for context in common_contexts:
        try:
            result = process_func(content, context)
            results.append((context, result))
        except Exception as e:
            errors.append((context, str(e)))
            continue
    
    return results, errors

def analyze_file_content(file_path, content):
    """Analyze the file content to provide debugging information"""
    analysis = {
        'file_size': len(content),
        'has_marker1': "GA91UCDQYUVawLMs" in content,
        'has_marker2': "EVy2D5PaA01T99Ml" in content,
        'marker1_pos': content.find("GA91UCDQYUVawLMs") if "GA91UCDQYUVawLMs" in content else -1,
        'marker2_pos': content.find("EVy2D5PaA01T99Ml") if "EVy2D5PaA01T99Ml" in content else -1,
        'printable_chars': sum(1 for c in content if c.isprintable()),
        'first_200_chars': repr(content[:200]),
        'last_200_chars': repr(content[-200:]) if len(content) > 200 else repr(content),
        'chars_35_to_43': repr(content[35:43]) if len(content) > 43 else "N/A (too short)",
        'chars_109_to_116': repr(content[109:116]) if len(content) > 116 else "N/A (too short)"
    }
    return analysis

def process_file(file_path, output_folder):
    is_encoded, encoding, preview_content = is_encoded_file(file_path)
    
    if not is_encoded:
        return
    
    print(f"Processing: {file_path} (encoding: {encoding})")
    
    # Read the full file content
    try:
        if encoding == 'binary':
            with open(file_path, 'rb') as f:
                full_content = f.read().decode('latin1', errors='ignore')
        else:
            with open(file_path, 'r', encoding=encoding or 'utf-8', errors='ignore') as f:
                full_content = f.read()
    except Exception as e:
        print(f"Could not read full content of {file_path}: {str(e)}")
        return

    # Analyze file content
    analysis = analyze_file_content(file_path, full_content)
    
    results_list = []
    errors_list = []
    
    if "GA91UCDQYUVawLMs" in full_content:
        results_list, errors_list = try_multiple_contexts(full_content, process_input_string)
        process_type = "Type 1 (GA91UCDQYUVawLMs)"
    elif "EVy2D5PaA01T99Ml" in full_content:
        results_list, errors_list = try_multiple_contexts(full_content, process_input_string2)
        process_type = "Type 2 (EVy2D5PaA01T99Ml)"
    else:
        print(f"No recognized encoding markers found in {file_path}")
        return

    # Save the results
    file_name = os.path.basename(file_path)
    output_file_path = os.path.join(output_folder, f"{file_name}.analysis.txt")
    
    with open(output_file_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(f"File: {file_path}\n")
        f.write(f"Process Type: {process_type}\n")
        f.write(f"File Encoding: {encoding}\n")
        f.write(f"File Analysis:\n")
        for key, value in analysis.items():
            f.write(f"  {key}: {value}\n")
        f.write("\n" + "="*50 + "\n")
        
        if results_list:
            f.write(f"\nSuccessful processing attempts: {len(results_list)}\n")
            for i, (context, output) in enumerate(results_list):
                f.write(f"\nContext '{context}' (attempt {i+1}):\n")
                f.write("-" * 30 + "\n")
                f.write(f"Decoded Values: {output['values']}\n")
                f.write(f"Decoded Vectors: {output['vectors']}\n")
                f.write(f"Decoded Strings: {output['strings']}\n")
                f.write(f"Result: {output['result']}\n")
                
                if process_type.startswith("Type 1"):
                    reversed_input = reverse_process_input_string(output)
                else:
                    reversed_input = reverse_process_input_string2(output)
                
                f.write(f"Reversed Input: {reversed_input}\n")
                f.write("\n")
        else:
            f.write(f"\nNo successful processing attempts\n")
        
        if errors_list:
            f.write(f"\nErrors encountered: {len(errors_list)}\n")
            for context, error in errors_list:
                f.write(f"Context '{context}': {error}\n")

    if results_list:
        print(f"Successfully processed {file_path} -> {output_file_path} ({len(results_list)} successful attempts)")
    else:
        print(f"Failed to process {file_path} - see analysis file: {output_file_path}")

def main():
    target_folder = input("Enter the path to your target folder: ").strip()
    
    if not os.path.exists(target_folder):
        print(f"Error: Folder '{target_folder}' does not exist.")
        return
    
    output_folder = os.path.join(target_folder, 'decoded_results')
    os.makedirs(output_folder, exist_ok=True)
    
    processed_count = 0
    successful_count = 0
    total_files = 0

    print(f"Scanning directory: {target_folder}")
    print(f"Output will be saved to: {output_folder}\n")

    for root, dirs, files in os.walk(target_folder):
        # Skip the output folder itself
        if 'decoded_results' in root:
            continue
            
        for file in files:
            if file.startswith('.'):
                continue  # Skip hidden files
            
            total_files += 1
            file_path = os.path.join(root, file)
            
            is_encoded, _, _ = is_encoded_file(file_path)
            if is_encoded:
                process_file(file_path, output_folder)
                processed_count += 1

    print(f"\nScan complete!")
    print(f"Total files scanned: {total_files}")
    print(f"Encoded files found: {processed_count}")
    print(f"Results saved in: {output_folder}")

if __name__ == "__main__":
    main()