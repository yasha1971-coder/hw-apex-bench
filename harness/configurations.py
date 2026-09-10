"""Explicit rows; ACEAPEX presets are checked against the pinned CLI source."""
ACE_SHA = "1b13df34ac8e839dd3232b59bc59560d689a435a"
CODECS = ("bgzip+htslib", "zstd-seekable", "aceapex-interactive", "aceapex-dense")
PROFILES = {
    "interactive": {"ACEAPEX_BS": "16384", "LIT_CHUNK": "65536", "FSE_CHUNK": "4096", "MIN_MATCH": "0"},
    "dense": {"ACEAPEX_BS": "262144", "LIT_CHUNK": "1048576", "FSE_CHUNK": "32768", "MIN_MATCH": "0"},
}
OVERRIDES = ("ACEAPEX_BS", "LIT_CHUNK", "FSE_CHUNK", "MIN_MATCH", "LIT_LEVEL", "LIT_LANES",
             "NO_REP", "DIRECT8", "FORCED_BIN", "ACEAPEX_DUMP", "LD_PRELOAD")
def clean_environment(env):
    return {k: v for k, v in env.items() if k not in OVERRIDES}
def configuration(codec):
    if codec.startswith("aceapex-"):
        profile = codec.removeprefix("aceapex-")
        return {"implementation": "aceapex", "profile": profile, "block": int(PROFILES[profile]["ACEAPEX_BS"]), "level": 2,
                "encoder_requested_threads": 1, "encoder_source": "aceapex_depth.cpp",
                "encoder_profile_flag": "--profile " + profile,
                "encoder_environment_overrides": {}, "effective_environment": PROFILES[profile],
                "reader_environment": PROFILES[profile], "api": "aceapex_decompress_region"}
    if codec == "bgzip+htslib":
        return {"implementation": codec, "block": 65536, "block_note": "BGZF uncompressed size ceiling; actual blocks may be shorter", "level": 6, "encoder_requested_threads": 1,
                "api": "bgzf_useek + bgzf_read", "required_indexes": [".gzi"]}
    return {"implementation": codec, "block": 16384, "level": 3, "frame_bytes": 16384,
            "encoder_requested_threads": 1, "api": "ZSTD_seekable_decompress"}
