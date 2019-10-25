import re

target = """
[Parsed_volumedetect_0 @ 0x55c81fc9fac0] n_samples: 23278920
2|aria  | [Parsed_volumedetect_0 @ 0x55c81fc9fac0] mean_volume: -10.1 dB
2|aria  | [Parsed_volumedetect_0 @ 0x55c81fc9fac0] max_volume: 0.0 dB
2|aria  | [Parsed_volumedetect_0 @ 0x55c81fc9fac0] histogram_0db: 88144
"""

volume_match = re.compile(r"max_volume: (-?\d+\.?\d+) dB")
matched = volume_match.findall(target)
print(matched)
print(matched[0])