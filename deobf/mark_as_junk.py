import idautils
import idaapi
import idc

JUNK_OPCODES = {"iret", "iretq", "retf", "iretd"}
JMP_INDIRECT = "jmp"

def is_junk_function(ea):
    """
    Returns True if the function at ea is considered junk
    based on instruction pattern.
    """
    mnem_counts = {}
    instrs = list(idautils.FuncItems(ea))
    
    # If it's super short (1-3 instructions), likely junk
    if len(instrs) <= 3:
        return True

    for insn_ea in instrs:
        mnem = idc.print_insn_mnem(insn_ea)
        mnem_counts[mnem] = mnem_counts.get(mnem, 0) + 1
        
        if mnem == JMP_INDIRECT:
            op = idc.GetOpnd(insn_ea, 0)
            if "[" in op and "+" in op:
                return True
        
        if mnem in JUNK_OPCODES:
            return True

    # If it's all unknown or no real logic
    if len(mnem_counts) == 1 and list(mnem_counts.values())[0] == len(instrs):
        return True
    
    return False

def mark_junk():
    junk_count = 0

    for func_ea in idautils.Functions():
        if is_junk_function(func_ea):
            idc.set_name(func_ea, f"junk_func_{junk_count:04X}", idc.SN_CHECK)
            idc.set_cmt(func_ea, "Marked as junk function (auto)", 0)
            junk_count += 1

    print(f"[+] Marked {junk_count} functions as junk.")

mark_junk()