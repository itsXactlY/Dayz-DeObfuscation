def to_signed32(n):
    n = n & 0xFFFFFFFF
    return n if n < 0x80000000 else n - 0x100000000

target = -117160863
test_string = "server-1"

def java_hash(s, mult=31, init=0):
    h = init
    for c in s:
        h = (h * mult + ord(c)) & 0xFFFFFFFF
    return to_signed32(h)

def djb2_hash(s, init=5381):
    h = init
    for c in s:
        h = ((h << 5) + h) + ord(c)
    return to_signed32(h)

def fnv1a_hash(s, init=0x811c9dc5, prime=0x01000193):
    h = init
    for c in s:
        h ^= ord(c)
        h = (h * prime) & 0xFFFFFFFF
    return to_signed32(h)

def xor_hash(s):
    h = 0
    for c in s:
        h ^= ord(c)
    return to_signed32(h)

def sum_hash(s):
    h = 0
    for c in s:
        h += ord(c)
    return to_signed32(h)

def rolling_hash(s, mult=257):
    h = 0
    for c in s:
        h = (h * mult + ord(c)) & 0xFFFFFFFF
    return to_signed32(h)

# Try various multipliers and initial values for java_hash
for mult in range(1, 100):
    for init in [0, 5381, 12345, 1]:
        h = java_hash(test_string, mult, init)
        if h == target:
            print(f"Java hash match! mult={mult}, init={init}")

# Try DJB2
for init in [5381, 0, 1, 12345]:
    h = djb2_hash(test_string, init)
    if h == target:
        print(f"DJB2 hash match! init={init}")

# Try FNV-1a
for init in [0x811c9dc5, 0, 1, 12345]:
    for prime in [0x01000193, 31, 16777619]:
        h = fnv1a_hash(test_string, init, prime)
        if h == target:
            print(f"FNV-1a hash match! init={init}, prime={prime}")

# Try XOR and SUM
if xor_hash(test_string) == target:
    print("XOR hash match!")
if sum_hash(test_string) == target:
    print("SUM hash match!")

# Try rolling hash
for mult in range(1, 1000, 13):
    h = rolling_hash(test_string, mult)
    if h == target:
        print(f"Rolling hash match! mult={mult}")

print("Done.")