import struct

def scan_chunk_for_candidates(chunk_data, chunk_offset, min_length=2048*2):
    """
    Scan a single chunk for candidate entropy buffers.
    chunk_data: bytes of the chunk
    chunk_offset: offset in the whole file where this chunk starts
    """
    candidates = []
    length = len(chunk_data)

    # Step size: 2 bytes (16-bit)
    step = 2

    # Only scan until we have room for full buffer
    for offset in range(0, length - min_length + 1, step):
        segment = chunk_data[offset:offset+min_length]
        values = struct.unpack("<" + "H"*(min_length//2), segment)
        
        # Heuristic: enough non-zero values?
        non_zero_count = sum(1 for v in values if v != 0)
        max_val = max(values)
        min_val = min(values)

        if non_zero_count > (min_length // 4) and max_val <= 0xFFFF and min_val >= 0:
            candidates.append((chunk_offset + offset, values))
    return candidates

def chunked_scan_file(filename, chunk_size=10*1024*1024, min_length=2048*2):
    """
    Scan the file in chunks to find candidate entropy buffers.
    chunk_size: how many bytes to read at once (default 10 MB)
    """
    candidates = []
    overlap = min_length - 2  # Overlap to catch buffers crossing chunk boundaries

    with open(filename, "rb") as f:
        offset = 0
        prev_chunk_end = b""

        while True:
            # Read chunk + overlap from previous end
            chunk = prev_chunk_end + f.read(chunk_size)
            if not chunk or len(chunk) < min_length:
                break

            # Scan this chunk for candidates
            chunk_candidates = scan_chunk_for_candidates(chunk, offset - len(prev_chunk_end), min_length)
            candidates.extend(chunk_candidates)

            # Save last overlap bytes to prepend to next chunk
            prev_chunk_end = chunk[-overlap:]

            offset += chunk_size

    return candidates

def main():
    filename = "/home/alca/dump/cores/critical_3s.core"  # Replace with your file
    print(f"Starting chunked scan on {filename}")
    candidates = chunked_scan_file(filename)
    print(f"Found {len(candidates)} candidate entropy buffers")

    # Print first few candidates info
    for i, (offset, values) in enumerate(candidates[:5]):
        print(f"\nCandidate #{i+1} at offset 0x{offset:x}:")
        print(f"First 16 entries: {values[:16]}")

if __name__ == "__main__":
    main()