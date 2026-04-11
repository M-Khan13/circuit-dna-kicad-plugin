import math
import cmath


class Specification:
    def __init__(self, name, metric, operator, target, weight=1.0, frequency=None, time_point=None):
        self.name = name
        self.metric = metric
        self.operator = operator
        self.target = target
        self.weight = weight
        self.frequency = frequency
        self.time_point = time_point

    def __repr__(self):
        return f"Spec({self.name}: {self.metric} {self.operator} {self.target})"


PRESET_SPECS = {
    "Low Pass Filter": [
        Specification("Passband Gain", "gain_db_at_freq", ">=", -3, frequency=1000),
        Specification("Stopband Attenuation", "gain_db_at_freq", "<=", -20, frequency=10000),
    ],
    "High Pass Filter": [
        Specification("Passband Gain", "gain_db_at_freq", ">=", -3, frequency=10000),
        Specification("Stopband Attenuation", "gain_db_at_freq", "<=", -20, frequency=100),
    ],
    "Amplifier": [
        Specification("Voltage Gain", "gain_db_at_freq", ">=", 20, frequency=1000),
        Specification("Bandwidth", "bandwidth_3db", ">=", 50000),
    ],
    "Oscillator Frequency": [
        Specification("Output Frequency", "dominant_frequency", "~=", 1000),
    ],
}


class FitnessEvaluator:
    def __init__(self, specs):
        self.specs = specs

    def evaluate(self, sim_result):
        if not sim_result.success:
            return -1e6, {}
        total_score = 0.0
        details = {}
        for spec in self.specs:
            measured = self._measure(sim_result, spec)
            score = self._score(measured, spec)
            weighted = score * spec.weight
            total_score += weighted
            details[spec.name] = {
                "measured": measured,
                "target": spec.target,
                "operator": spec.operator,
                "score": score,
                "weighted": weighted,
                "met": self._is_met(measured, spec)
            }
        return total_score, details

    def _measure(self, sim_result, spec):
        method = getattr(self, f"_metric_{spec.metric}", None)
        if method is None:
            return None
        return method(sim_result, spec)

    def _metric_gain_db_at_freq(self, sim_result, spec):
        freq_data = sim_result.get_signal("frequency")
        if freq_data is None:
            freq_data = sim_result.get_signal("Frequency")
        if freq_data is None:
            return None
        out_signal = None
        for name in sim_result.data:
            nl = name.lower()
            if "out" in nl or nl.startswith("v(out") or nl.startswith("v(2"):
                out_signal = sim_result.data[name]
                break
        if out_signal is None:
            keys = [k for k in sim_result.data if k.lower() != "frequency"]
            if keys:
                out_signal = sim_result.data[keys[-1]]
        if out_signal is None or freq_data is None:
            return None
        target_freq = spec.frequency
        closest_idx = 0
        min_dist = float("inf")
        for i, f in enumerate(freq_data):
            f_real = f.real if isinstance(f, complex) else f
            dist = abs(f_real - target_freq)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        val = out_signal[closest_idx]
        mag = abs(val) if isinstance(val, complex) else abs(val)
        if mag <= 0:
            return -200
        return 20 * math.log10(mag)

    def _metric_bandwidth_3db(self, sim_result, spec):
        freq_data = sim_result.get_signal("frequency")
        if freq_data is None:
            freq_data = sim_result.get_signal("Frequency")
        if freq_data is None:
            return None
        out_signal = None
        for name in sim_result.data:
            nl = name.lower()
            if "out" in nl:
                out_signal = sim_result.data[name]
                break
        if out_signal is None:
            return None
        magnitudes = [abs(v) if isinstance(v, complex) else abs(v) for v in out_signal]
        if not magnitudes:
            return None
        peak_mag = max(magnitudes)
        if peak_mag <= 0:
            return 0
        threshold = peak_mag / math.sqrt(2)
        for i, mag in enumerate(magnitudes):
            if mag < threshold:
                f = freq_data[i]
                return f.real if isinstance(f, complex) else f
        f_last = freq_data[-1]
        return f_last.real if isinstance(f_last, complex) else f_last

    def _metric_peak_voltage(self, sim_result, spec):
        for name in sim_result.data:
            nl = name.lower()
            if nl.startswith("v(") and "out" in nl:
                signal = sim_result.data[name]
                vals = [v.real if isinstance(v, complex) else v for v in signal]
                return max(vals) if vals else None
        for name in sim_result.data:
            nl = name.lower()
            if nl.startswith("v(") and nl != "v(vcc)" and "time" not in nl:
                signal = sim_result.data[name]
                vals = [v.real if isinstance(v, complex) else v for v in signal]
                return max(vals) if vals else None
        return None
    def _metric_dominant_frequency(self, sim_result, spec):
        time_data = sim_result.get_signal("time")
        if time_data is None:
            return None
        out_signal = None
        for name in sim_result.data:
            nl = name.lower()
            if nl.startswith("v(") and "out" in nl:
                out_signal = sim_result.data[name]
                break
        if out_signal is None:
            for name in sim_result.data:
                nl = name.lower()
                if nl.startswith("v(") and nl != "v(vcc)" and "time" not in nl:
                    out_signal = sim_result.data[name]
                    break
        if out_signal is None:
            return None
        vals = [v.real if isinstance(v, complex) else v for v in out_signal]
        n = len(vals)
        if n < 4:
            return None
        times = [t.real if isinstance(t, complex) else t for t in time_data]
        crossings = []
        mean_val = sum(vals) / n
        for i in range(1, n):
            if (vals[i-1] - mean_val) * (vals[i] - mean_val) < 0:
                crossings.append(times[i])
        if len(crossings) < 2:
            return None
        periods = [crossings[i+2] - crossings[i] for i in range(len(crossings)-2)]
        if not periods:
            return None
        avg_period = sum(periods) / len(periods)
        if avg_period <= 0:
            return None
        return 1.0 / avg_period

    def _metric_rise_time(self, sim_result, spec):
        time_data = sim_result.get_signal("time")
        if time_data is None:
            return None
        out_signal = None
        for name in sim_result.data:
            nl = name.lower()
            if nl.startswith("v(") and "out" in nl:
                out_signal = sim_result.data[name]
                break
        if out_signal is None:
            for name in sim_result.data:
                nl = name.lower()
                if nl.startswith("v(") and nl != "v(vcc)" and "time" not in nl:
                    out_signal = sim_result.data[name]
                    break
        if out_signal is None:
            return None
        vals = [v.real if isinstance(v, complex) else v for v in out_signal]
        times = [t.real if isinstance(t, complex) else t for t in time_data]
        v_min, v_max = min(vals), max(vals)
        v_range = v_max - v_min
        if v_range <= 0:
            return None
        t10, t90 = None, None
        thresh_10 = v_min + 0.1 * v_range
        thresh_90 = v_min + 0.9 * v_range
        for i, v in enumerate(vals):
            if t10 is None and v >= thresh_10:
                t10 = times[i]
            if t10 is not None and t90 is None and v >= thresh_90:
                t90 = times[i]
                break
        if t10 is not None and t90 is not None:
            return t90 - t10
        return None

    def _score(self, measured, spec):
        if measured is None:
            return -100
        target = spec.target
        op = spec.operator
        if op == ">=":
            if measured >= target:
                return 10 + (measured - target) / max(abs(target), 1e-12)
            return -abs(target - measured) / max(abs(target), 1e-12) * 10
        elif op == "<=":
            if measured <= target:
                return 10 + (target - measured) / max(abs(target), 1e-12)
            return -abs(measured - target) / max(abs(target), 1e-12) * 10
        elif op == "==":
            diff = abs(measured - target)
            if diff < abs(target) * 0.01:
                return 10
            return -diff / max(abs(target), 1e-12) * 10
        elif op == "~=":
            diff = abs(measured - target)
            tolerance = abs(target) * 0.1
            if diff <= tolerance:
                return 10 * (1 - diff / tolerance)
            return -(diff / max(abs(target), 1e-12)) * 10
        return 0

    def _is_met(self, measured, spec):
        if measured is None:
            return False
        op = spec.operator
        target = spec.target
        if op == ">=":
            return measured >= target
        elif op == "<=":
            return measured <= target
        elif op == "==":
            return abs(measured - target) < abs(target) * 0.01
        elif op == "~=":
            return abs(measured - target) <= abs(target) * 0.1
        return False
