def manual_deobfuscate(code_snippet):
    # The mappings discovered by the AI
    mappings = {
        'khcvEOGvbYurSEsMtQ': 'missionManager',
        'WClEHQgWLyrJgrAZh': 'clientMission',
        'KXkHsemBMWGbhbceB': 'serverMission',
        'sntwxxdOBLLflUevhaqv': 'missionScript',
        'fgptyDuRuewGdCps': 'currentMission',
        'IsMultiplayer': 'isMultiplayerMode',
        'prWSpdaVXepJJMArnq': 'getMissionProgress',
        'AfrzZUctcucNjQkvIAA': 'gameState',
        'IsClient': 'isClientSide',
        'NeYezhNIBCYplWG': 'checkMissionStatus',
        'asEsJWEBxVifZPReWTd': 'getMissionData',
        'DXOlBuzveQrnsAlUGfHM': 'missionReference',
        'LTXpSFmSkatmzOKnDZM': 'clientMissionData',
        'IsServer': 'isServerSide',
        'cHfENVfRPzKyJXBuxnz': 'checkMissionStatusFunction',
        'GetMission': 'getActiveMission',
        'dhSOiaCmRInzlSCdrHqn': 'defaultMission',
        'ZzTuAJkRReSMEzmnIg': 'currentServerMission'
    }

    # Apply each mapping to the code
    deobfuscated = code_snippet
    for obfuscated, clear in mappings.items():
        deobfuscated = deobfuscated.replace(obfuscated, clear)
    
    return deobfuscated

# Example usage
obfuscated_code = """
        class cHfENVfRPzKyJXBuxnz { static int NeYezhNIBCYplWG() { if (!AfrzZUctcucNjQkvIAA().IsMultiplayer()) return 1; if (AfrzZUctcucNjQkvIAA().IsClient()) { LTXpSFmSkatmzOKnDZM fgptyDuRuewGdCps = khcvEOGvbYurSEsMtQ.asEsJWEBxVifZPReWTd; if (fgptyDuRuewGdCps) { ref DXOlBuzveQrnsAlUGfHM WClEHQgWLyrJgrAZh = fgptyDuRuewGdCps.asEsJWEBxVifZPReWTd; if (WClEHQgWLyrJgrAZh) { return WClEHQgWLyrJgrAZh.prWSpdaVXepJJMArnq(); }} } else if (AfrzZUctcucNjQkvIAA().IsServer()) { KXkHsemBMWGbhbceB ZzTuAJkRReSMEzmnIg = KXkHsemBMWGbhbceB.Cast(AfrzZUctcucNjQkvIAA().GetMission()); if (ZzTuAJkRReSMEzmnIg == dhSOiaCmRInzlSCdrHqn) return -1; return ZzTuAJkRReSMEzmnIg.sntwxxdOBLLflUevhaqv.prWSpdaVXepJJMArnq(); } return -1; }}
"""

print("Deobfuscated code:")
print(manual_deobfuscate(obfuscated_code))