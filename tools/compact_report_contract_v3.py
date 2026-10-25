"""Small metadata contract; full predecessor verification is mandatory."""


def compact_reference(freeze, policy, inherited, original_verifier):
    ref = freeze["inherited_execution"]
    if {key: ref[key] for key in ("path", "sha256", "bytes")} != policy["inherited_execution"]:
        raise ValueError("original sealed full execution reference changed")
    if freeze["environment"] != {key: inherited["environment"][key] for key in ("executable", "python", "packages")}:
        raise ValueError("inherited environment summary differs")
    return original_verifier(inherited)  # All original source/code/environment pins.
