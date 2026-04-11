import os
import datetime
import json
import math


class ReportGenerator:
    def __init__(self, ga, project_path, runner=None, parser=None):
        self.ga = ga
        self.project_path = project_path
        self.runner = runner
        self.parser = parser

    def _get_waveform_data(self):
        if not self.runner or not self.parser:
            return None, None
        try:
            orig_result = self.runner.run(self.parser.raw_spice)
            if not orig_result.success:
                return None, None
            best = self.ga.best_individual
            if not best:
                return orig_result, None
            opt_netlist = self.parser.generate_modified_netlist(best.genes)
            opt_result = self.runner.run(opt_netlist)
            if not opt_result.success:
                return orig_result, None
            return orig_result, opt_result
        except Exception:
            return None, None

    def _extract_plot_data(self, sim_result, max_points=300):
        if not sim_result or not sim_result.data:
            return None
        freq_data = sim_result.get_signal("frequency")
        time_data = sim_result.get_signal("time")
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
        if freq_data is not None:
            x_raw = [f.real if isinstance(f, complex) else f for f in freq_data]
            y_raw = []
            for v in out_signal:
                mag = abs(v) if isinstance(v, complex) else abs(v)
                db = 20 * math.log10(mag) if mag > 0 else -200
                y_raw.append(db)
            step = max(1, len(x_raw) // max_points)
            x = x_raw[::step]
            y = y_raw[::step]
            return {"type": "ac", "x": x, "y": y, "xlabel": "Frequency (Hz)", "ylabel": "Gain (dB)"}
        elif time_data is not None:
            x_raw = [t.real if isinstance(t, complex) else t for t in time_data]
            y_raw = [v.real if isinstance(v, complex) else v for v in out_signal]
            step = max(1, len(x_raw) // max_points)
            x = x_raw[::step]
            y = y_raw[::step]
            return {"type": "tran", "x": x, "y": y, "xlabel": "Time (s)", "ylabel": "Voltage (V)"}
        return None

    def generate(self, output_path=None):
        if output_path is None:
            output_path = os.path.join(self.project_path, "circuit_dna_report.html")
        diffs = self.ga.get_diff()
        history = self.ga.history
        best = self.ga.best_individual
        gen_labels = json.dumps([h["generation"] for h in history])
        best_fitness = json.dumps([round(h["best_fitness"], 4) for h in history])
        avg_fitness = json.dumps([round(h["avg_fitness"], 4) for h in history])
        specs_met_data = json.dumps([h.get("specs_met", 0) for h in history])
        total_specs = history[0].get("total_specs", 0) if history else 0
        pop_size = self.ga.population_size
        mut_rate = self.ga.mutation_rate
        cx_rate = self.ga.crossover_rate
        elite_count = self.ga.elite_count
        total_sims = pop_size * len(history)
        first_fit = history[0]["best_fitness"] if history else 0
        last_fit = history[-1]["best_fitness"] if history else 0
        improvement = ((last_fit - first_fit) / max(abs(first_fit), 1e-12)) * 100

        orig_result, opt_result = self._get_waveform_data()
        orig_plot = self._extract_plot_data(orig_result)
        opt_plot = self._extract_plot_data(opt_result)
        has_waveforms = orig_plot is not None and opt_plot is not None
        orig_plot_json = json.dumps(orig_plot) if orig_plot else "null"
        opt_plot_json = json.dumps(opt_plot) if opt_plot else "null"

        diff_rows = ""
        for d in diffs:
            pct = d["change_pct"]
            direction = "+" if pct > 0 else ""
            orig_num = f"{d['original_numeric']:.4g}"
            new_num = f"{d['new_numeric']:.4g}"
            diff_rows += f"""
            <tr>
                <td class="mono">{d['ref']}</td>
                <td>{d['type']}</td>
                <td class="mono">{d['original_value']}</td>
                <td class="mono">{orig_num}</td>
                <td class="mono bold">{d['new_value']}</td>
                <td class="mono bold">{new_num}</td>
                <td class="mono">{direction}{pct:.1f}%</td>
            </tr>"""

        spec_rows = ""
        if best and best.details:
            for name, info in best.details.items():
                met = info.get("met", False)
                status = "Met" if met else "Not met"
                status_class = "met" if met else "notmet"
                measured = info.get("measured")
                m_str = f"{measured:.4g}" if measured is not None else "N/A"
                target_str = f"{info['operator']} {info['target']}"
                score = info.get("score", 0)
                spec_rows += f"""
                <tr>
                    <td>{name}</td>
                    <td class="mono">{target_str}</td>
                    <td class="mono bold">{m_str}</td>
                    <td class="mono">{score:.2f}</td>
                    <td class="{status_class}">{status}</td>
                </tr>"""

        all_comps_rows = ""
        if self.ga.mutable_components:
            for comp in self.ga.mutable_components:
                orig = comp.numeric_value
                new_val = best.genes.get(comp.ref, orig) if best else orig
                changed = abs(orig - new_val) / max(abs(orig), 1e-15) > 0.001
                new_formatted = comp.format_value(new_val)
                all_comps_rows += f"""
                <tr>
                    <td class="mono">{comp.ref}</td>
                    <td>{comp.comp_type}</td>
                    <td class="mono">{comp.value}</td>
                    <td class="mono{' bold' if changed else ''}">{new_formatted}</td>
                    <td>{'Yes' if changed else '-'}</td>
                </tr>"""

        gene_history_data = "{}"
        if history and best:
            gene_traces = {}
            for h in history:
                for ref, val in h.get("best_genes", {}).items():
                    if ref not in gene_traces:
                        gene_traces[ref] = []
                    gene_traces[ref].append(val)
            gene_history_data = json.dumps(gene_traces)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        netlist_name = ""
        if self.parser and hasattr(self.parser, 'raw_spice'):
            first_line = self.parser.raw_spice.strip().splitlines()[0] if self.parser.raw_spice.strip() else ""
            if first_line.lower().startswith(".title"):
                netlist_name = first_line[6:].strip()

        waveform_section = ""
        if has_waveforms:
            is_ac = orig_plot["type"] == "ac"
            chart_title = "Frequency Response (Before vs After)" if is_ac else "Output Waveform (Before vs After)"
            fig_caption = "Fig. 4 &mdash; Original vs optimized circuit response" if is_ac else "Fig. 4 &mdash; Original vs optimized output waveform"
            waveform_section = f"""
  <h2>Waveform Comparison</h2>
  <p>
    The chart below overlays the {'frequency response' if is_ac else 'transient output'} of the original circuit
    (dashed) against the optimized circuit (solid), showing the effect of the GA-selected component values.
  </p>
  <div class="chart-wrap">
    <canvas id="waveformChart" height="280"></canvas>
    <div class="chart-caption">{fig_caption}</div>
  </div>"""

        waveform_script = ""
        if has_waveforms:
            is_ac = orig_plot["type"] == "ac"
            waveform_script = f"""
const origData = {orig_plot_json};
const optData = {opt_plot_json};
const isAC = {'true' if is_ac else 'false'};
new Chart(document.getElementById('waveformChart'), {{
  type: 'line',
  data: {{
    labels: origData.x.map(v => isAC ? v.toFixed(0) : v.toFixed(4)),
    datasets: [
      {{
        label: 'Original',
        data: origData.y,
        borderColor: '#999',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [6, 3],
        pointRadius: 0,
        tension: 0.3
      }},
      {{
        label: 'Optimized',
        data: optData.y,
        borderColor: '#222',
        backgroundColor: 'rgba(0,0,0,0.03)',
        fill: true,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3
      }}
    ]
  }},
  options: {{
    responsive: true,
    animation: false,
    plugins: {{ legend: {{ labels: {{ color: '#555', font: {{ family: "'Inter', sans-serif", size: 11.5 }}, usePointStyle: true, pointStyle: 'line', padding: 12 }} }} }},
    scales: {{
      x: {{
        type: isAC ? 'logarithmic' : 'linear',
        title: {{ display: true, text: origData.xlabel, color: '#999', font: {{ family: "'Inter', sans-serif", size: 11 }} }},
        ticks: {{ color: '#999', font: {{ family: "'Inter', sans-serif", size: 11 }}, maxTicksLimit: 10, callback: function(v) {{ return isAC ? (Number(v) >= 1000 ? (Number(v)/1000)+'k' : v) : v; }} }},
        grid: {{ color: '#e8e6e1' }}
      }},
      y: {{
        title: {{ display: true, text: origData.ylabel, color: '#999', font: {{ family: "'Inter', sans-serif", size: 11 }} }},
        ticks: {{ color: '#999', font: {{ family: "'Inter', sans-serif", size: 11 }} }},
        grid: {{ color: '#e8e6e1' }}
      }}
    }}
  }}
}});
"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Circuit DNA Report</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=JetBrains+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif;
    background: #fff;
    color: #222;
    line-height: 1.75;
    font-size: 15px;
    -webkit-font-smoothing: antialiased;
  }}
  .page {{
    max-width: 780px;
    margin: 0 auto;
    padding: 3.5rem 2rem 3rem;
  }}
  .header {{
    margin-bottom: 2.5rem;
    text-align: center;
  }}
  .header h1 {{
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.3px;
    margin-bottom: 0.3rem;
    color: #111;
  }}
  .header .circuit-name {{
    font-size: 1.05rem;
    color: #555;
    font-style: italic;
    margin-bottom: 0.5rem;
  }}
  .header .meta {{
    font-size: 0.82rem;
    color: #999;
    font-family: 'Inter', sans-serif;
  }}
  .header hr {{
    border: none;
    border-top: 1.5px solid #111;
    margin-top: 1.25rem;
  }}
  h2 {{
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    margin-top: 2.8rem;
    margin-bottom: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #444;
  }}
  h2::before {{
    content: '';
    display: inline-block;
    width: 12px;
    height: 2px;
    background: #111;
    margin-right: 8px;
    vertical-align: middle;
  }}
  p {{ margin-bottom: 0.9rem; color: #333; text-align: justify; }}
  .highlight-box {{
    background: #f8f8f6;
    border: 1px solid #e8e6e1;
    padding: 1rem 1.3rem;
    margin: 1rem 0 1.5rem;
    border-radius: 3px;
    font-size: 0.93rem;
  }}
  .highlight-box strong {{ color: #111; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 0.6rem 0 1.8rem;
    font-size: 0.87rem;
    font-family: 'Inter', sans-serif;
  }}
  th {{
    text-align: left;
    padding: 0.5rem 0.65rem;
    border-bottom: 1.5px solid #222;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #666;
  }}
  td {{
    padding: 0.45rem 0.65rem;
    border-bottom: 1px solid #eee;
  }}
  tr:last-child td {{ border-bottom: 1px solid #bbb; }}
  .mono {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
  }}
  .bold {{ font-weight: 600; }}
  .met {{ color: #1a6b37; font-weight: 600; font-family: 'Inter', sans-serif; }}
  .notmet {{ color: #a3261b; font-weight: 600; font-family: 'Inter', sans-serif; }}
  .chart-wrap {{
    margin: 1rem 0 2rem;
    border: 1px solid #e5e3de;
    border-radius: 3px;
    padding: 1rem 1rem 0.5rem;
    background: #fefefe;
  }}
  .chart-wrap canvas {{ width: 100% !important; }}
  .chart-caption {{
    font-size: 0.78rem;
    color: #888;
    text-align: center;
    margin-top: 0.25rem;
    font-family: 'Inter', sans-serif;
    font-style: italic;
  }}
  .side-by-side {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
  }}
  .params-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 2.5rem;
    font-family: 'Inter', sans-serif;
    font-size: 0.87rem;
    margin: 0.5rem 0 1.5rem;
  }}
  .param-row {{
    display: flex;
    justify-content: space-between;
    padding: 0.3rem 0;
    border-bottom: 1px dotted #ddd;
  }}
  .param-row .k {{ color: #666; }}
  .param-row .v {{ font-family: 'JetBrains Mono', monospace; font-weight: 500; font-size: 0.83rem; color: #222; }}
  .footer {{
    margin-top: 3.5rem;
    padding-top: 0.8rem;
    border-top: 1px solid #ccc;
    font-size: 0.78rem;
    color: #aaa;
    text-align: center;
    font-family: 'Inter', sans-serif;
  }}
  @media print {{
    body {{ font-size: 11.5px; }}
    .page {{ padding: 0.5rem; max-width: 100%; }}
    .chart-wrap {{ break-inside: avoid; }}
    h2 {{ break-after: avoid; }}
    table {{ break-inside: avoid; }}
  }}
  @media (max-width: 680px) {{
    .side-by-side {{ grid-template-columns: 1fr; }}
    .params-grid {{ grid-template-columns: 1fr; }}
    .page {{ padding: 1.5rem 1rem; }}
  }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <h1>Circuit DNA &mdash; Optimization Report</h1>
    <div class="circuit-name">{netlist_name or 'Circuit Under Test'}</div>
    <div class="meta">{timestamp} &nbsp;&middot;&nbsp; {len(history)} generations &nbsp;&middot;&nbsp; {total_sims} simulations</div>
    <hr>
  </div>

  <h2>Summary</h2>
  <div class="highlight-box">
    <p style="margin:0">
      A genetic algorithm with population size {pop_size} was run for <strong>{len(history)} generations</strong>,
      evaluating {total_sims} circuit variants via ngspice simulation.
      The best fitness improved from {first_fit:.1f} to <strong>{last_fit:.1f}</strong>
      ({f"{improvement:+.1f}%" if abs(improvement) > 0.1 else "stable"}).
      Of the {len(self.ga.mutable_components)} mutable R/C/L components,
      <strong>{len(diffs)}</strong> were modified to meet the target specifications.
      {"All specifications were satisfied." if best and best.details and all(d.get("met") for d in best.details.values()) else ""}
    </p>
  </div>

  <h2>Fitness Convergence</h2>
  <div class="side-by-side">
    <div class="chart-wrap">
      <canvas id="fitnessChart" height="210"></canvas>
      <div class="chart-caption">Fig. 1 &mdash; Best and average fitness per generation</div>
    </div>
    <div class="chart-wrap">
      <canvas id="specsChart" height="210"></canvas>
      <div class="chart-caption">Fig. 2 &mdash; Specifications met per generation</div>
    </div>
  </div>

  <h2>Specification Results</h2>
  <table>
    <tr><th>Specification</th><th>Target</th><th>Measured</th><th>Score</th><th>Status</th></tr>
    {spec_rows}
  </table>

  <h2>Component Changes</h2>
  <p>
    Values below reflect the best individual from the final generation.
    Optimized values are snapped to the E24 preferred number series.
  </p>
  <table>
    <tr><th>Ref</th><th>Type</th><th>Original</th><th>SI Value</th><th>Optimized</th><th>SI Value</th><th>Change</th></tr>
    {diff_rows}
  </table>

  {waveform_section}

  <h2>Value Trajectories</h2>
  <div class="chart-wrap">
    <canvas id="geneChart" height="250"></canvas>
    <div class="chart-caption">Fig. 3 &mdash; Component values of best individual across generations (log scale)</div>
  </div>

  <h2>Full Component Table</h2>
  <table>
    <tr><th>Ref</th><th>Type</th><th>Original</th><th>Final</th><th>Modified</th></tr>
    {all_comps_rows}
  </table>

  <h2>Algorithm Configuration</h2>
  <div class="params-grid">
    <div class="param-row"><span class="k">Population size</span><span class="v">{pop_size}</span></div>
    <div class="param-row"><span class="k">Generations</span><span class="v">{len(history)}</span></div>
    <div class="param-row"><span class="k">Mutation rate</span><span class="v">{mut_rate}</span></div>
    <div class="param-row"><span class="k">Crossover rate</span><span class="v">{cx_rate}</span></div>
    <div class="param-row"><span class="k">Elitism</span><span class="v">{elite_count}</span></div>
    <div class="param-row"><span class="k">Tournament size</span><span class="v">{self.ga.tournament_size}</span></div>
    <div class="param-row"><span class="k">Selection method</span><span class="v">Tournament</span></div>
    <div class="param-row"><span class="k">Value snapping</span><span class="v">E24 series</span></div>
  </div>

  <div class="footer">
    Circuit DNA &middot; KiCad Genetic Circuit Optimizer &middot; FOSSEE eSim Fellowship, IIT Bombay
  </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const lf = {{ family: "'Inter', sans-serif", size: 11 }};
const gc = '#e8e6e1';
const tc = '#999';
const bOpts = {{
  responsive: true,
  animation: false,
  plugins: {{ legend: {{ labels: {{ color: '#555', font: {{ ...lf, size: 11.5 }}, usePointStyle: true, pointStyle: 'line', padding: 12 }} }} }},
  scales: {{
    x: {{ ticks: {{ color: tc, font: lf }}, grid: {{ color: gc }} }},
    y: {{ ticks: {{ color: tc, font: lf }}, grid: {{ color: gc }} }}
  }}
}};

new Chart(document.getElementById('fitnessChart'), {{
  type: 'line',
  data: {{
    labels: {gen_labels},
    datasets: [
      {{ label:'Best', data:{best_fitness}, borderColor:'#222', backgroundColor:'rgba(0,0,0,0.03)', fill:true, tension:0.3, pointRadius:3, pointBackgroundColor:'#222', borderWidth:1.8 }},
      {{ label:'Average', data:{avg_fitness}, borderColor:'#aaa', backgroundColor:'transparent', tension:0.3, pointRadius:2, pointBackgroundColor:'#aaa', borderWidth:1.2, borderDash:[5,3] }}
    ]
  }},
  options: {{ ...bOpts,
    scales: {{
      x: {{ ...bOpts.scales.x, title: {{ display:true, text:'Generation', color:tc, font:lf }} }},
      y: {{ ...bOpts.scales.y, title: {{ display:true, text:'Fitness', color:tc, font:lf }} }}
    }}
  }}
}});

new Chart(document.getElementById('specsChart'), {{
  type: 'bar',
  data: {{
    labels: {gen_labels},
    datasets: [{{ data:{specs_met_data}, backgroundColor:'#333', borderRadius:2, barPercentage:0.55 }}]
  }},
  options: {{ ...bOpts,
    plugins: {{ legend: {{ display:false }} }},
    scales: {{
      x: {{ ...bOpts.scales.x, title: {{ display:true, text:'Generation', color:tc, font:lf }} }},
      y: {{ ...bOpts.scales.y, title: {{ display:true, text:'Count', color:tc, font:lf }}, beginAtZero:true, max:{total_specs+1}, ticks:{{ stepSize:1, color:tc, font:lf }} }}
    }}
  }}
}});

const gd = {gene_history_data};
const ls = [
  {{ c:'#222', d:[] }}, {{ c:'#b91c1c', d:[] }}, {{ c:'#0e7c47', d:[] }}, {{ c:'#b45309', d:[] }},
  {{ c:'#222', d:[6,3] }}, {{ c:'#b91c1c', d:[6,3] }}, {{ c:'#0e7c47', d:[6,3] }}, {{ c:'#b45309', d:[6,3] }}
];
const gds = Object.keys(gd).map((r,i) => {{
  const s = ls[i%ls.length];
  return {{ label:r, data:gd[r], borderColor:s.c, backgroundColor:'transparent', tension:0.25, pointRadius:2.5, pointBackgroundColor:s.c, borderWidth:1.6, borderDash:s.d }};
}});
new Chart(document.getElementById('geneChart'), {{
  type: 'line',
  data: {{ labels:{gen_labels}, datasets:gds }},
  options: {{ ...bOpts,
    scales: {{
      x: {{ ...bOpts.scales.x, title: {{ display:true, text:'Generation', color:tc, font:lf }} }},
      y: {{ ...bOpts.scales.y, type:'logarithmic', title: {{ display:true, text:'Value (SI)', color:tc, font:lf }} }}
    }}
  }}
}});

{waveform_script}
</script>
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path