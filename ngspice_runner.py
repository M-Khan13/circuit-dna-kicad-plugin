import subprocess
import os
import re
import tempfile
import struct


class SimulationResult:
    def __init__(self):
        self.variables = []
        self.data = {}
        self.success = False
        self.error = ""
        self.raw_output = ""

    def get_signal(self, name):
        name_lower = name.lower()
        for key in self.data:
            if key.lower() == name_lower:
                return self.data[key]
        return None


class NgspiceRunner:
    def __init__(self, ngspice_path=r"C:\FOSSEE\nghdl-simulator\bin\ngspice.exe"):
        self.ngspice_path = ngspice_path
        self.timeout = 60

    def run(self, netlist_content, work_dir=None):
        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix="cdna_")
        netlist_path = os.path.join(work_dir, "circuit.cir")
        raw_path = os.path.join(work_dir, "output.raw")
        raw_path_clean = raw_path.replace("\\", "/")
        if " " in raw_path_clean:
            alt_dir = os.path.join(tempfile.gettempdir(), "cdna_work")
            os.makedirs(alt_dir, exist_ok=True)
            raw_path = os.path.join(alt_dir, "output.raw")
            raw_path_clean = raw_path.replace("\\", "/")

        lines = netlist_content.strip().splitlines()
        control_exists = any(".control" in l.lower() for l in lines)
        if not control_exists:
            insert_idx = len(lines)
            for i, l in enumerate(lines):
                if l.strip().lower() == ".end":
                    insert_idx = i
                    break
            control_block = [
                ".control",
                "run",
                f"write {raw_path_clean} all",
                "quit",
                ".endc"
            ]
            lines = lines[:insert_idx] + control_block + lines[insert_idx:]

        final_netlist = "\n".join(lines)
        with open(netlist_path, "w") as f:
            f.write(final_netlist)

        result = SimulationResult()
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            proc = subprocess.run(
                [self.ngspice_path, "-b", netlist_path],
                capture_output=True, text=True,
                timeout=self.timeout, cwd=work_dir,
                startupinfo=startupinfo
            )
            result.raw_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            if "fatal" in result.raw_output.lower():
                result.success = False
                result.error = self._extract_errors(result.raw_output)
                return result
        except subprocess.TimeoutExpired:
            result.success = False
            result.error = "Simulation timed out"
            return result
        except FileNotFoundError:
            result.success = False
            result.error = f"ngspice not found at {self.ngspice_path}"
            return result
        except Exception as e:
            result.success = False
            result.error = f"Subprocess error: {e}"
            return result

        if os.path.exists(raw_path):
            self._parse_raw_file(raw_path, result)
            result.success = len(result.data) > 0
        else:
            result.success = False
            result.error = f"Raw output file not generated. ngspice output:\n{result.raw_output[-500:]}"

        return result

    def _extract_errors(self, output):
        errors = []
        for line in output.splitlines():
            if "error" in line.lower() or "fatal" in line.lower():
                errors.append(line.strip())
        return "\n".join(errors[:5]) if errors else "Unknown simulation error"

    def _parse_raw_file(self, raw_path, result):
        try:
            with open(raw_path, "rb") as f:
                raw_bytes = f.read()
        except Exception as e:
            result.error = f"Cannot read raw file: {e}"
            return

        try:
            text_preview = raw_bytes[:2000].decode("utf-8", errors="replace")
            if "Binary:" in text_preview:
                marker = b"Binary:\r\n"
                header_end = raw_bytes.find(marker)
                if header_end == -1:
                    marker = b"Binary:\n"
                    header_end = raw_bytes.find(marker)
                if header_end == -1:
                    result.error = "Cannot find Binary data section"
                    return
                header = raw_bytes[:header_end].decode("utf-8", errors="replace")
                binary_data = raw_bytes[header_end + len(marker):]
                self._parse_header(header, result)
                self._parse_binary_data(binary_data, result)
            elif "Values:" in text_preview:
                self._parse_ascii_raw(raw_bytes, result)
            else:
                result.error = "Cannot find data section in raw file"
        except Exception as e:
            result.error = f"Raw file parse error: {e}"

    def _parse_header(self, header, result):
        lines = header.splitlines()
        in_vars = False
        num_vars = 0
        num_points = 0
        result.variables = []
        for line in lines:
            if line.startswith("No. Variables:"):
                num_vars = int(line.split(":")[-1].strip())
            elif line.startswith("No. Points:"):
                num_points = int(line.split(":")[-1].strip())
            elif line.strip() == "Variables:":
                in_vars = True
                continue
            elif in_vars:
                parts = line.strip().split()
                if len(parts) >= 3:
                    idx = int(parts[0])
                    name = parts[1]
                    vtype = parts[2]
                    result.variables.append({"index": idx, "name": name, "type": vtype})
                if len(result.variables) >= num_vars:
                    in_vars = False
        result._num_points = num_points
        result._num_vars = num_vars

    def _parse_binary_data(self, data, result):
        num_vars = getattr(result, "_num_vars", 0)
        num_points = getattr(result, "_num_points", 0)
        if num_vars == 0 or num_points == 0:
            return

        is_complex = any(v.get("type", "").lower() == "frequency" for v in result.variables)
        bytes_per_val = 16 if is_complex else 8
        record_size = num_vars * bytes_per_val

        signals = {v["name"]: [] for v in result.variables}
        var_names = [v["name"] for v in result.variables]

        offset = 0
        for pt in range(num_points):
            if offset + record_size > len(data):
                break
            for vi, vname in enumerate(var_names):
                pos = offset + vi * bytes_per_val
                if is_complex:
                    real = struct.unpack("d", data[pos:pos+8])[0]
                    imag = struct.unpack("d", data[pos+8:pos+16])[0]
                    signals[vname].append(complex(real, imag))
                else:
                    val = struct.unpack("d", data[pos:pos+8])[0]
                    signals[vname].append(val)
            offset += record_size

        result.data = signals

    def _parse_ascii_raw(self, raw_bytes, result):
        text = raw_bytes.decode("utf-8", errors="replace")
        text = text.replace("\r\n", "\n")
        self._parse_header(text, result)
        values_idx = text.find("Values:\n")
        if values_idx == -1:
            result.error = "Cannot find Values section in ASCII raw file"
            return
        data_section = text[values_idx + len("Values:\n"):]
        var_names = [v["name"] for v in result.variables]
        num_vars = len(var_names)
        if num_vars == 0:
            return
        signals = {name: [] for name in var_names}
        current_point = []
        for line in data_section.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'^\d+\s', stripped):
                if current_point and len(current_point) >= num_vars:
                    for i in range(num_vars):
                        signals[var_names[i]].append(current_point[i])
                current_point = []
                parts = stripped.split("\t")
                if len(parts) >= 2:
                    val_text = parts[-1].strip()
                    current_point.append(self._parse_value(val_text))
            else:
                parts = stripped.split("\t")
                val_text = parts[-1].strip() if len(parts) >= 2 else stripped
                current_point.append(self._parse_value(val_text))
        if current_point and len(current_point) >= num_vars:
            for i in range(num_vars):
                signals[var_names[i]].append(current_point[i])
        result.data = signals

    def _parse_value(self, text):
        text = text.strip()
        if "," in text:
            parts = text.split(",")
            try:
                return complex(float(parts[0]), float(parts[1]))
            except (ValueError, IndexError):
                return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0