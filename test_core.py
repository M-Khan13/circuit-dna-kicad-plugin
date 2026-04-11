import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_dna.parser.netlist_parser import NetlistParser, Component
from circuit_dna.engine.fitness import Specification, FitnessEvaluator
from circuit_dna.engine.ngspice_runner import SimulationResult
from circuit_dna.utils.config import ConfigManager


def test_component_value_parsing():
    cases = [
        ("1k", 1000), ("4.7k", 4700), ("100n", 1e-7), ("10u", 1e-5),
        ("1M", 1e6), ("3.3", 3.3), ("470p", 470e-12), ("1meg", 1e6),
        ("100", 100), ("2.2k", 2200),
    ]
    passed = 0
    for val_str, expected in cases:
        comp = Component("R1", val_str, "R")
        actual = comp.numeric_value
        if actual is not None and abs(actual - expected) / expected < 0.01:
            passed += 1
        else:
            print(f"  FAIL: '{val_str}' -> {actual}, expected {expected}")
    print(f"Value parsing: {passed}/{len(cases)} passed")


def test_value_formatting():
    comp = Component("R1", "1k", "R")
    cases = [
        (1000, "1k"), (4700, "4.7k"), (1e-7, "100n"),
        (1e6, "1M"), (470e-12, "470p"), (2200, "2.2k"),
    ]
    passed = 0
    for numeric, expected in cases:
        result = comp.format_value(numeric)
        if result == expected:
            passed += 1
        else:
            print(f"  FAIL: {numeric} -> '{result}', expected '{expected}'")
    print(f"Value formatting: {passed}/{len(cases)} passed")


def test_netlist_parsing():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    cir_path = os.path.join(test_dir, "rc_lowpass.cir")
    parser = NetlistParser(test_dir)
    components = parser.parse(cir_path)
    assert len(components) >= 2, f"Expected >=2 components, got {len(components)}"
    mutable = parser.get_mutable_components()
    assert len(mutable) >= 2, f"Expected >=2 mutable, got {len(mutable)}"
    refs = [c.ref for c in mutable]
    assert "R1" in refs, "R1 not found in mutable components"
    assert "C1" in refs, "C1 not found in mutable components"
    print(f"Netlist parsing: OK ({len(components)} components, {len(mutable)} mutable)")


def test_netlist_modification():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    cir_path = os.path.join(test_dir, "rc_lowpass.cir")
    parser = NetlistParser(test_dir)
    parser.parse(cir_path)
    new_netlist = parser.generate_modified_netlist({"R1": 2200, "C1": 47e-9})
    assert "2.2k" in new_netlist or "2200" in new_netlist, "R1 not updated"
    assert "47n" in new_netlist or "4.7e" in new_netlist, "C1 not updated"
    print(f"Netlist modification: OK")


def test_fitness_scoring():
    spec_ge = Specification("test_ge", "gain_db_at_freq", ">=", -3, frequency=1000)
    spec_le = Specification("test_le", "gain_db_at_freq", "<=", -20, frequency=10000)
    evaluator = FitnessEvaluator([spec_ge, spec_le])
    result = SimulationResult()
    result.success = False
    score, details = evaluator.evaluate(result)
    assert score == -1e6, "Failed sim should get -1e6"
    print("Fitness scoring: OK")


def test_config():
    cfg = ConfigManager("/tmp/cdna_test_config")
    cfg.set("population_size", 30)
    cfg.save()
    cfg2 = ConfigManager("/tmp/cdna_test_config")
    assert cfg2.get("population_size") == 30, "Config not persisted"
    print("Config: OK")


def test_e24_snap():
    from circuit_dna.engine.genetic_algorithm import GeneticAlgorithm
    from circuit_dna.engine.ngspice_runner import NgspiceRunner
    ga = GeneticAlgorithm.__new__(GeneticAlgorithm)
    cases = [(999, 1000), (4800, 4700), (6500, 6800), (2100, 2200)]
    passed = 0
    for val, expected in cases:
        result = ga._snap_to_series(val, "R")
        if abs(result - expected) / expected < 0.1:
            passed += 1
        else:
            print(f"  FAIL: snap({val}) -> {result}, expected ~{expected}")
    print(f"E24 snap: {passed}/{len(cases)} passed")


if __name__ == "__main__":
    print("=" * 50)
    print("Circuit DNA — Unit Tests")
    print("=" * 50)
    test_component_value_parsing()
    test_value_formatting()
    test_netlist_parsing()
    test_netlist_modification()
    test_fitness_scoring()
    test_config()
    test_e24_snap()
    print("=" * 50)
    print("All tests complete.")
