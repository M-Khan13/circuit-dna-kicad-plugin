import re
import os
import glob


class Component:
    def __init__(self, ref, value, comp_type, unit="", footprint=""):
        self.ref = ref
        self.value = value
        self.comp_type = comp_type
        self.unit = unit
        self.footprint = footprint
        self.numeric_value = self._parse_value(value)
        self.mutable = comp_type in ("R", "C", "L")

    def _parse_value(self, val):
        val = val.strip()
        multipliers = {
            "T": 1e12, "G": 1e9, "M": 1e6, "meg": 1e6, "MEG": 1e6,
            "k": 1e3, "K": 1e3,
            "m": 1e-3, "u": 1e-6, "µ": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15
        }
        pattern = r'^([0-9]*\.?[0-9]+)\s*([a-zA-Zµ]*)'
        match = re.match(pattern, val)
        if not match:
            return None
        number = float(match.group(1))
        suffix = match.group(2)
        if not suffix:
            return number
        for key in sorted(multipliers.keys(), key=len, reverse=True):
            if suffix.startswith(key):
                return number * multipliers[key]
        return number

    def format_value(self, numeric_val):
        if numeric_val is None:
            return self.value
        abs_val = abs(numeric_val)
        if abs_val == 0:
            return "0"
        tiers = [
            (1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "k"),
            (1, ""), (1e-3, "m"), (1e-6, "u"), (1e-9, "n"), (1e-12, "p"), (1e-15, "f")
        ]
        for threshold, suffix in tiers:
            if abs_val >= threshold * 0.999:
                scaled = numeric_val / threshold
                rounded = round(scaled, 10)
                if abs(rounded - round(rounded)) < 1e-9:
                    return f"{int(round(rounded))}{suffix}"
                if abs(rounded) >= 100:
                    return f"{int(round(rounded))}{suffix}"
                if abs(rounded) >= 10:
                    clean = f"{rounded:.1f}".rstrip('0').rstrip('.')
                    return f"{clean}{suffix}"
                clean = f"{rounded:.2f}".rstrip('0').rstrip('.')
                return f"{clean}{suffix}"
        return f"{numeric_val:.3e}"

    def __repr__(self):
        return f"Component({self.ref}, {self.value}, {self.comp_type})"


class NetlistParser:
    COMP_TYPE_MAP = {
        "R": "R", "C": "C", "L": "L", "V": "V", "I": "I",
        "D": "D", "Q": "Q", "M": "M", "X": "X", "U": "U"
    }

    def __init__(self, project_path):
        self.project_path = project_path
        self.components = []
        self.raw_spice = ""

    def find_netlist(self):
        patterns = ["*.cir", "*.spice", "*.sp", "*.net"]
        for pat in patterns:
            matches = glob.glob(os.path.join(self.project_path, pat))
            if matches:
                return matches[0]
        sub_dirs = ["Simulation", "simulation", "spice", "ngspice"]
        for sd in sub_dirs:
            for pat in patterns:
                matches = glob.glob(os.path.join(self.project_path, sd, pat))
                if matches:
                    return matches[0]
        return None

    def parse(self, netlist_path=None):
        if netlist_path is None:
            netlist_path = self.find_netlist()
        if netlist_path is None or not os.path.exists(netlist_path):
            raise FileNotFoundError(f"No SPICE netlist found in {self.project_path}")
        with open(netlist_path, "r") as f:
            self.raw_spice = f.read()
        self.components = []
        for line in self.raw_spice.splitlines():
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("."):
                continue
            comp = self._parse_component_line(line)
            if comp:
                self.components.append(comp)
        return self.components

    def _parse_component_line(self, line):
        parts = line.split()
        if len(parts) < 3:
            return None
        ref = parts[0]
        first_char = ref[0].upper()
        if first_char not in self.COMP_TYPE_MAP:
            return None
        comp_type = self.COMP_TYPE_MAP[first_char]
        if comp_type in ("R", "C", "L"):
            INTERNAL_REFS = {"CLATCH", "RLATCH", "RCOMP", "RDISCH"}
            value = parts[3] if len(parts) > 3 else parts[-1]
            value = re.sub(r'\s*IC=\S*', '', value).strip()
            if not value:
                value = parts[-1]
            comp = Component(ref, value, comp_type)
            if ref.upper() in INTERNAL_REFS or (comp.numeric_value and comp.numeric_value >= 1e8):
                comp.mutable = False
            return comp
        if comp_type == "V":
            value_str = " ".join(parts[3:]) if len(parts) > 3 else parts[-1]
            return Component(ref, value_str, comp_type)
        if comp_type in ("D", "Q", "M", "X", "U"):
            model = parts[-1]
            return Component(ref, model, comp_type)
        return None

    def get_mutable_components(self):
        return [c for c in self.components if c.mutable and c.numeric_value is not None]

    def generate_modified_netlist(self, value_map):
        lines = self.raw_spice.splitlines()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("*") or stripped.startswith("."):
                new_lines.append(line)
                continue
            parts = stripped.split()
            ref = parts[0]
            if ref in value_map:
                comp = next((c for c in self.components if c.ref == ref), None)
                if comp and comp.mutable:
                    first_char = ref[0].upper()
                    if first_char in ("R", "C", "L") and len(parts) > 3:
                        parts[3] = comp.format_value(value_map[ref])
                    else:
                        parts[-1] = comp.format_value(value_map[ref])
                    new_lines.append(" ".join(parts))
                    continue
            new_lines.append(line)
        return "\n".join(new_lines)