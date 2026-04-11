import random
import copy
import os
import tempfile
import time


class Individual:
    def __init__(self, genes, fitness=None, details=None, generation=0):
        self.genes = genes
        self.fitness = fitness
        self.details = details or {}
        self.generation = generation

    def __repr__(self):
        return f"Individual(fitness={self.fitness:.4f}, genes={self.genes})"


class GeneticAlgorithm:
    def __init__(self, parser, runner, evaluator, config=None):
        self.parser = parser
        self.runner = runner
        self.evaluator = evaluator
        self.config = config or {}
        self.population_size = self.config.get("population_size", 20)
        self.generations = self.config.get("generations", 15)
        self.mutation_rate = self.config.get("mutation_rate", 0.3)
        self.crossover_rate = self.config.get("crossover_rate", 0.7)
        self.elite_count = self.config.get("elite_count", 2)
        self.mutation_scale = self.config.get("mutation_scale", 0.5)
        self.tournament_size = self.config.get("tournament_size", 3)
        self.mutable_components = []
        self.gene_bounds = {}
        self.history = []
        self.best_individual = None
        self.callback = None
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def setup(self):
        self.mutable_components = self.parser.get_mutable_components()
        if not self.mutable_components:
            raise ValueError("No mutable components (R, C, L) found in netlist")
        for comp in self.mutable_components:
            val = comp.numeric_value
            self.gene_bounds[comp.ref] = {
                "min": val * 0.01,
                "max": val * 100,
                "original": val,
                "type": comp.comp_type
            }

    def run(self):
        self._stop_flag = False
        self.setup()
        population = self._initialize_population()
        self._evaluate_population(population)
        population.sort(key=lambda ind: ind.fitness if ind.fitness is not None else -1e9, reverse=True)
        self.history = []
        for gen in range(self.generations):
            if self._stop_flag:
                break
            gen_stats = {
                "generation": gen,
                "best_fitness": population[0].fitness,
                "avg_fitness": sum(i.fitness for i in population if i.fitness) / len(population),
                "best_genes": dict(population[0].genes),
                "specs_met": sum(1 for v in population[0].details.values() if v.get("met", False)),
                "total_specs": len(population[0].details)
            }
            self.history.append(gen_stats)
            if self.callback:
                self.callback(gen, self.generations, population[0], gen_stats)
            self.best_individual = population[0]
            new_population = []
            elites = population[:self.elite_count]
            new_population.extend(copy.deepcopy(elites))
            while len(new_population) < self.population_size:
                if self._stop_flag:
                    break
                parent1 = self._tournament_select(population)
                parent2 = self._tournament_select(population)
                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2)
                else:
                    child1 = copy.deepcopy(parent1)
                    child2 = copy.deepcopy(parent2)
                self._mutate(child1)
                self._mutate(child2)
                child1.generation = gen + 1
                child2.generation = gen + 1
                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)
            population = new_population[:self.population_size]
            self._evaluate_population(population)
            population.sort(key=lambda ind: ind.fitness if ind.fitness is not None else -1e9, reverse=True)

        self.best_individual = population[0]
        return population[:5]

    def _initialize_population(self):
        population = []
        original_genes = {c.ref: c.numeric_value for c in self.mutable_components}
        population.append(Individual(dict(original_genes), generation=0))
        for _ in range(self.population_size - 1):
            genes = {}
            for comp in self.mutable_components:
                bounds = self.gene_bounds[comp.ref]
                log_min = self._safe_log(bounds["min"])
                log_max = self._safe_log(bounds["max"])
                log_val = random.uniform(log_min, log_max)
                genes[comp.ref] = 10 ** log_val
                genes[comp.ref] = self._snap_to_series(genes[comp.ref], bounds["type"])
            population.append(Individual(genes, generation=0))
        return population

    def _evaluate_population(self, population):
        work_dir = tempfile.mkdtemp(prefix="cdna_eval_")
        for i, individual in enumerate(population):
            if self._stop_flag:
                break
            if individual.fitness is not None:
                continue
            netlist = self.parser.generate_modified_netlist(individual.genes)
            sim_dir = os.path.join(work_dir, f"ind_{i}")
            os.makedirs(sim_dir, exist_ok=True)
            result = self.runner.run(netlist, sim_dir)
            fitness, details = self.evaluator.evaluate(result)
            individual.fitness = fitness
            individual.details = details

    def _tournament_select(self, population):
        contestants = random.sample(population, min(self.tournament_size, len(population)))
        return max(contestants, key=lambda i: i.fitness if i.fitness is not None else -1e9)

    def _crossover(self, parent1, parent2):
        genes1, genes2 = {}, {}
        keys = list(parent1.genes.keys())
        if len(keys) <= 1:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)
        cx_point = random.randint(1, len(keys) - 1)
        for i, key in enumerate(keys):
            if i < cx_point:
                genes1[key] = parent1.genes[key]
                genes2[key] = parent2.genes[key]
            else:
                genes1[key] = parent2.genes[key]
                genes2[key] = parent1.genes[key]
        return Individual(genes1), Individual(genes2)

    def _mutate(self, individual):
        for ref in individual.genes:
            if random.random() < self.mutation_rate:
                bounds = self.gene_bounds[ref]
                current = individual.genes[ref]
                log_current = self._safe_log(current)
                log_min = self._safe_log(bounds["min"])
                log_max = self._safe_log(bounds["max"])
                sigma = (log_max - log_min) * self.mutation_scale * 0.1
                new_log = log_current + random.gauss(0, sigma)
                new_log = max(log_min, min(log_max, new_log))
                new_val = 10 ** new_log
                individual.genes[ref] = self._snap_to_series(new_val, bounds["type"])
                individual.fitness = None

    def _snap_to_series(self, value, comp_type):
        e24 = [
            1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4,
            2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2,
            6.8, 7.5, 8.2, 9.1
        ]
        if value <= 0:
            return 1.0
        import math
        decade = math.floor(math.log10(value))
        normalized = value / (10 ** decade)
        closest = min(e24, key=lambda x: abs(x - normalized))
        return closest * (10 ** decade)

    def _safe_log(self, val):
        import math
        if val <= 0:
            return -15
        return math.log10(val)

    def get_diff(self):
        if not self.best_individual:
            return []
        diffs = []
        for comp in self.mutable_components:
            original = comp.numeric_value
            optimized = self.best_individual.genes.get(comp.ref, original)
            if abs(original - optimized) / max(abs(original), 1e-15) > 0.001:
                diffs.append({
                    "ref": comp.ref,
                    "type": comp.comp_type,
                    "original_value": comp.value,
                    "original_numeric": original,
                    "new_numeric": optimized,
                    "new_value": comp.format_value(optimized),
                    "change_pct": ((optimized - original) / original) * 100
                })
        return diffs
