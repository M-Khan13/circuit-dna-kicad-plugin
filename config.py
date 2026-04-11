import json
import os


DEFAULT_CONFIG = {
    "ngspice_path": r"C:\FOSSEE\nghdl-simulator\bin\ngspice.exe",
    "population_size": 20,
    "generations": 15,
    "mutation_rate": 0.3,
    "crossover_rate": 0.7,
    "elite_count": 2,
    "mutation_scale": 0.5,
    "tournament_size": 3,
    "simulation_timeout": 30,
    "snap_to_e24": True,
}


class ConfigManager:
    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = os.path.join(os.path.expanduser("~"), ".circuit_dna")
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, "config.json")
        self.config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    saved = json.load(f)
                self.config.update(saved)
            except (json.JSONDecodeError, IOError):
                pass
        return self.config

    def save(self):
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def get_ga_config(self):
        return {
            "population_size": self.config["population_size"],
            "generations": self.config["generations"],
            "mutation_rate": self.config["mutation_rate"],
            "crossover_rate": self.config["crossover_rate"],
            "elite_count": self.config["elite_count"],
            "mutation_scale": self.config["mutation_scale"],
            "tournament_size": self.config["tournament_size"],
        }
