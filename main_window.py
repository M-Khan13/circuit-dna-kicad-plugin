import wx
import wx.lib.agw.aui as aui
import os
import threading
import glob

from .netlist_parser import NetlistParser
from .ngspice_runner import NgspiceRunner
from .fitness import FitnessEvaluator, Specification, PRESET_SPECS
from .genetic_algorithm import GeneticAlgorithm
from .config import ConfigManager
from .report import ReportGenerator

COLOR_BG = wx.Colour(15, 23, 42)
COLOR_CARD = wx.Colour(30, 41, 59)
COLOR_TEXT = wx.Colour(226, 232, 240)
COLOR_ACCENT = wx.Colour(129, 140, 248)
COLOR_GREEN = wx.Colour(52, 211, 153)
COLOR_RED = wx.Colour(239, 68, 68)
COLOR_MUTED = wx.Colour(148, 163, 184)


class MainWindow(wx.Dialog):
    def __init__(self, parent, project_path):
        super().__init__(parent, title="Circuit DNA — Genetic Circuit Optimizer",
                         size=(900, 720),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.project_path = project_path
        self.config = ConfigManager()
        self.parser = None
        self.ga = None
        self.running = False
        self.SetBackgroundColour(COLOR_BG)
        self._build_ui()
        self.Centre()

    def _build_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.Panel(self)
        header.SetBackgroundColour(COLOR_BG)
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(header, label="🧬 Circuit DNA")
        title.SetFont(wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(COLOR_ACCENT)
        h_sizer.Add(title, 0, wx.ALL, 10)
        subtitle = wx.StaticText(header, label="Evolve your circuit to meet specs")
        subtitle.SetForegroundColour(COLOR_MUTED)
        subtitle.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        h_sizer.Add(subtitle, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        header.SetSizer(h_sizer)
        main_sizer.Add(header, 0, wx.EXPAND)

        self.notebook = wx.Notebook(self)
        self.notebook.SetBackgroundColour(COLOR_BG)
        self.notebook.SetForegroundColour(COLOR_TEXT)

        self.setup_panel = self._build_setup_tab()
        self.specs_panel = self._build_specs_tab()
        self.evolution_panel = self._build_evolution_tab()
        self.results_panel = self._build_results_tab()
        self.settings_panel = self._build_settings_tab()

        self.notebook.AddPage(self.setup_panel, "1. Load Circuit")
        self.notebook.AddPage(self.specs_panel, "2. Define Specs")
        self.notebook.AddPage(self.evolution_panel, "3. Evolve")
        self.notebook.AddPage(self.results_panel, "4. Results")
        self.notebook.AddPage(self.settings_panel, "⚙ Settings")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(main_sizer)

    def _build_setup_tab(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(COLOR_BG)
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(panel, label="SPICE Netlist File:")
        lbl.SetForegroundColour(COLOR_TEXT)
        sizer.Add(lbl, 0, wx.ALL, 8)

        file_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.netlist_path_ctrl = wx.TextCtrl(panel, size=(600, -1))
        self.netlist_path_ctrl.SetBackgroundColour(COLOR_CARD)
        self.netlist_path_ctrl.SetForegroundColour(COLOR_TEXT)
        file_sizer.Add(self.netlist_path_ctrl, 1, wx.ALL, 4)
        browse_btn = wx.Button(panel, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        file_sizer.Add(browse_btn, 0, wx.ALL, 4)
        sizer.Add(file_sizer, 0, wx.EXPAND)

        auto_btn = wx.Button(panel, label="Auto-detect from project")
        auto_btn.Bind(wx.EVT_BUTTON, self._on_auto_detect)
        sizer.Add(auto_btn, 0, wx.ALL, 8)

        load_btn = wx.Button(panel, label="Parse Netlist")
        load_btn.SetBackgroundColour(COLOR_ACCENT)
        load_btn.Bind(wx.EVT_BUTTON, self._on_parse)
        sizer.Add(load_btn, 0, wx.ALL, 8)

        self.components_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.components_list.SetBackgroundColour(COLOR_CARD)
        self.components_list.SetForegroundColour(COLOR_TEXT)
        self.components_list.InsertColumn(0, "Ref", width=80)
        self.components_list.InsertColumn(1, "Type", width=60)
        self.components_list.InsertColumn(2, "Value", width=120)
        self.components_list.InsertColumn(3, "Numeric", width=120)
        self.components_list.InsertColumn(4, "Mutable", width=80)
        sizer.Add(self.components_list, 1, wx.EXPAND | wx.ALL, 8)

        self.parse_status = wx.StaticText(panel, label="")
        self.parse_status.SetForegroundColour(COLOR_GREEN)
        sizer.Add(self.parse_status, 0, wx.ALL, 8)

        panel.SetSizer(sizer)
        return panel

    def _build_specs_tab(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(COLOR_BG)
        sizer = wx.BoxSizer(wx.VERTICAL)

        preset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(panel, label="Preset:")
        lbl.SetForegroundColour(COLOR_TEXT)
        preset_sizer.Add(lbl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        presets = ["(Custom)"] + list(PRESET_SPECS.keys())
        self.preset_choice = wx.Choice(panel, choices=presets)
        self.preset_choice.SetSelection(0)
        self.preset_choice.Bind(wx.EVT_CHOICE, self._on_preset)
        preset_sizer.Add(self.preset_choice, 0, wx.ALL, 8)
        sizer.Add(preset_sizer, 0)

        add_sizer = wx.FlexGridSizer(cols=6, hgap=5, vgap=5)
        labels = ["Name", "Metric", "Operator", "Target", "Freq (Hz)", ""]
        for l in labels:
            t = wx.StaticText(panel, label=l)
            t.SetForegroundColour(COLOR_MUTED)
            add_sizer.Add(t, 0, wx.ALL, 4)

        self.spec_name_ctrl = wx.TextCtrl(panel, size=(120, -1))
        self.spec_name_ctrl.SetBackgroundColour(COLOR_CARD)
        self.spec_name_ctrl.SetForegroundColour(COLOR_TEXT)
        add_sizer.Add(self.spec_name_ctrl, 0)

        metrics = ["gain_db_at_freq", "bandwidth_3db", "peak_voltage",
                    "dominant_frequency", "rise_time"]
        self.spec_metric_choice = wx.Choice(panel, choices=metrics)
        self.spec_metric_choice.SetSelection(0)
        add_sizer.Add(self.spec_metric_choice, 0)

        ops = [">=", "<=", "==", "~="]
        self.spec_op_choice = wx.Choice(panel, choices=ops)
        self.spec_op_choice.SetSelection(0)
        add_sizer.Add(self.spec_op_choice, 0)

        self.spec_target_ctrl = wx.TextCtrl(panel, size=(80, -1), value="0")
        self.spec_target_ctrl.SetBackgroundColour(COLOR_CARD)
        self.spec_target_ctrl.SetForegroundColour(COLOR_TEXT)
        add_sizer.Add(self.spec_target_ctrl, 0)

        self.spec_freq_ctrl = wx.TextCtrl(panel, size=(80, -1), value="1000")
        self.spec_freq_ctrl.SetBackgroundColour(COLOR_CARD)
        self.spec_freq_ctrl.SetForegroundColour(COLOR_TEXT)
        add_sizer.Add(self.spec_freq_ctrl, 0)

        add_btn = wx.Button(panel, label="+ Add Spec")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add_spec)
        add_sizer.Add(add_btn, 0)

        sizer.Add(add_sizer, 0, wx.ALL, 8)

        self.specs_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.specs_list.SetBackgroundColour(COLOR_CARD)
        self.specs_list.SetForegroundColour(COLOR_TEXT)
        self.specs_list.InsertColumn(0, "Name", width=150)
        self.specs_list.InsertColumn(1, "Metric", width=150)
        self.specs_list.InsertColumn(2, "Operator", width=60)
        self.specs_list.InsertColumn(3, "Target", width=100)
        self.specs_list.InsertColumn(4, "Frequency", width=100)
        sizer.Add(self.specs_list, 1, wx.EXPAND | wx.ALL, 8)

        rm_btn = wx.Button(panel, label="Remove Selected")
        rm_btn.Bind(wx.EVT_BUTTON, self._on_remove_spec)
        sizer.Add(rm_btn, 0, wx.ALL, 8)

        self.user_specs = []
        panel.SetSizer(sizer)
        return panel

    def _build_evolution_tab(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(COLOR_BG)
        sizer = wx.BoxSizer(wx.VERTICAL)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.evolve_btn = wx.Button(panel, label="▶ Start Evolution")
        self.evolve_btn.SetBackgroundColour(COLOR_GREEN)
        self.evolve_btn.Bind(wx.EVT_BUTTON, self._on_evolve)
        btn_sizer.Add(self.evolve_btn, 0, wx.ALL, 8)

        self.stop_btn = wx.Button(panel, label="⏹ Stop")
        self.stop_btn.Enable(False)
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)
        btn_sizer.Add(self.stop_btn, 0, wx.ALL, 8)
        sizer.Add(btn_sizer, 0)

        self.progress = wx.Gauge(panel, range=100)
        sizer.Add(self.progress, 0, wx.EXPAND | wx.ALL, 8)

        self.gen_label = wx.StaticText(panel, label="Ready")
        self.gen_label.SetForegroundColour(COLOR_ACCENT)
        self.gen_label.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(self.gen_label, 0, wx.ALL, 8)

        self.evo_log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.evo_log.SetBackgroundColour(COLOR_CARD)
        self.evo_log.SetForegroundColour(COLOR_TEXT)
        self.evo_log.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(self.evo_log, 1, wx.EXPAND | wx.ALL, 8)

        panel.SetSizer(sizer)
        return panel

    def _build_results_tab(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(COLOR_BG)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.results_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.results_list.SetBackgroundColour(COLOR_CARD)
        self.results_list.SetForegroundColour(COLOR_TEXT)
        self.results_list.InsertColumn(0, "Ref", width=80)
        self.results_list.InsertColumn(1, "Type", width=60)
        self.results_list.InsertColumn(2, "Original", width=120)
        self.results_list.InsertColumn(3, "Optimized", width=120)
        self.results_list.InsertColumn(4, "Change %", width=100)
        sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 8)

        self.spec_results_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.spec_results_list.SetBackgroundColour(COLOR_CARD)
        self.spec_results_list.SetForegroundColour(COLOR_TEXT)
        self.spec_results_list.InsertColumn(0, "Specification", width=180)
        self.spec_results_list.InsertColumn(1, "Target", width=120)
        self.spec_results_list.InsertColumn(2, "Measured", width=120)
        self.spec_results_list.InsertColumn(3, "Met?", width=80)
        sizer.Add(self.spec_results_list, 1, wx.EXPAND | wx.ALL, 8)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        apply_btn = wx.Button(panel, label="Apply to Netlist")
        apply_btn.SetBackgroundColour(COLOR_GREEN)
        apply_btn.Bind(wx.EVT_BUTTON, self._on_apply)
        btn_sizer.Add(apply_btn, 0, wx.ALL, 8)

        report_btn = wx.Button(panel, label="Generate HTML Report")
        report_btn.SetBackgroundColour(COLOR_ACCENT)
        report_btn.Bind(wx.EVT_BUTTON, self._on_report)
        btn_sizer.Add(report_btn, 0, wx.ALL, 8)

        export_btn = wx.Button(panel, label="Export Optimized Netlist")
        export_btn.Bind(wx.EVT_BUTTON, self._on_export)
        btn_sizer.Add(export_btn, 0, wx.ALL, 8)

        sizer.Add(btn_sizer, 0)
        panel.SetSizer(sizer)
        return panel

    def _build_settings_tab(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(COLOR_BG)
        sizer = wx.FlexGridSizer(cols=2, hgap=10, vgap=10)

        fields = [
            ("ngspice Path:", "ngspice_path", str),
            ("Population Size:", "population_size", int),
            ("Generations:", "generations", int),
            ("Mutation Rate:", "mutation_rate", float),
            ("Crossover Rate:", "crossover_rate", float),
            ("Elite Count:", "elite_count", int),
            ("Mutation Scale:", "mutation_scale", float),
            ("Tournament Size:", "tournament_size", int),
            ("Sim Timeout (s):", "simulation_timeout", int),
        ]
        self.setting_ctrls = {}
        for label, key, vtype in fields:
            lbl = wx.StaticText(panel, label=label)
            lbl.SetForegroundColour(COLOR_TEXT)
            sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
            ctrl = wx.TextCtrl(panel, value=str(self.config.get(key, "")), size=(300, -1))
            ctrl.SetBackgroundColour(COLOR_CARD)
            ctrl.SetForegroundColour(COLOR_TEXT)
            self.setting_ctrls[key] = (ctrl, vtype)
            sizer.Add(ctrl, 0, wx.ALL, 4)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(sizer, 0, wx.ALL, 12)
        save_btn = wx.Button(panel, label="Save Settings")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save_settings)
        outer.Add(save_btn, 0, wx.ALL, 12)
        panel.SetSizer(outer)
        return panel

    def _on_browse(self, event):
        dlg = wx.FileDialog(self, "Select SPICE netlist",
                            wildcard="SPICE files (*.cir;*.spice;*.sp;*.net)|*.cir;*.spice;*.sp;*.net|All files (*.*)|*.*",
                            style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.netlist_path_ctrl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _on_auto_detect(self, event):
        parser = NetlistParser(self.project_path)
        path = parser.find_netlist()
        if path:
            self.netlist_path_ctrl.SetValue(path)
        else:
            wx.MessageBox(f"No SPICE netlist found in:\n{self.project_path}", "Not Found", wx.OK | wx.ICON_WARNING)

    def _on_parse(self, event):
        path = self.netlist_path_ctrl.GetValue().strip()
        if not path:
            wx.MessageBox("Please select a netlist file first.", "Error", wx.OK | wx.ICON_ERROR)
            return
        try:
            self.parser = NetlistParser(self.project_path)
            components = self.parser.parse(path)
        except Exception as e:
            wx.MessageBox(f"Parse error: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return
        self.components_list.DeleteAllItems()
        for comp in components:
            idx = self.components_list.InsertItem(self.components_list.GetItemCount(), comp.ref)
            self.components_list.SetItem(idx, 1, comp.comp_type)
            self.components_list.SetItem(idx, 2, comp.value)
            nv = f"{comp.numeric_value:.4g}" if comp.numeric_value is not None else "—"
            self.components_list.SetItem(idx, 3, nv)
            self.components_list.SetItem(idx, 4, "Yes" if comp.mutable else "No")
        mutable = self.parser.get_mutable_components()
        self.parse_status.SetLabel(f"Parsed {len(components)} components, {len(mutable)} mutable (R/C/L)")

    def _on_preset(self, event):
        sel = self.preset_choice.GetStringSelection()
        if sel in PRESET_SPECS:
            self.user_specs = list(PRESET_SPECS[sel])
            self._refresh_specs_list()

    def _on_add_spec(self, event):
        name = self.spec_name_ctrl.GetValue().strip()
        metric = self.spec_metric_choice.GetStringSelection()
        op = self.spec_op_choice.GetStringSelection()
        try:
            target = float(self.spec_target_ctrl.GetValue())
        except ValueError:
            wx.MessageBox("Target must be a number.", "Error", wx.OK | wx.ICON_ERROR)
            return
        freq = None
        freq_str = self.spec_freq_ctrl.GetValue().strip()
        if freq_str:
            try:
                freq = float(freq_str)
            except ValueError:
                pass
        if not name:
            name = f"{metric} {op} {target}"
        spec = Specification(name, metric, op, target, frequency=freq)
        self.user_specs.append(spec)
        self._refresh_specs_list()

    def _on_remove_spec(self, event):
        sel = self.specs_list.GetFirstSelected()
        if sel >= 0 and sel < len(self.user_specs):
            self.user_specs.pop(sel)
            self._refresh_specs_list()

    def _refresh_specs_list(self):
        self.specs_list.DeleteAllItems()
        for spec in self.user_specs:
            idx = self.specs_list.InsertItem(self.specs_list.GetItemCount(), spec.name)
            self.specs_list.SetItem(idx, 1, spec.metric)
            self.specs_list.SetItem(idx, 2, spec.operator)
            self.specs_list.SetItem(idx, 3, str(spec.target))
            self.specs_list.SetItem(idx, 4, str(spec.frequency) if spec.frequency else "—")

    def _on_evolve(self, event):
        if self.parser is None:
            wx.MessageBox("Parse a netlist first (Tab 1).", "Error", wx.OK | wx.ICON_ERROR)
            return
        if not self.user_specs:
            wx.MessageBox("Add at least one specification (Tab 2).", "Error", wx.OK | wx.ICON_ERROR)
            return
        if not self.parser.get_mutable_components():
            wx.MessageBox("No mutable R/C/L components found.", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.running = True
        self.evolve_btn.Enable(False)
        self.stop_btn.Enable(True)
        self.evo_log.SetValue("")
        self.progress.SetValue(0)

        ngspice_path = self.config.get("ngspice_path")
        runner = NgspiceRunner(ngspice_path)
        runner.timeout = self.config.get("simulation_timeout", 30)
        evaluator = FitnessEvaluator(self.user_specs)
        ga_config = self.config.get_ga_config()
        self.ga = GeneticAlgorithm(self.parser, runner, evaluator, ga_config)
        self.ga.callback = self._evolution_callback

        thread = threading.Thread(target=self._run_evolution, daemon=True)
        thread.start()

    def _run_evolution(self):
        try:
            top5 = self.ga.run()
            wx.CallAfter(self._evolution_complete, top5)
        except Exception as e:
            wx.CallAfter(self._evolution_error, str(e))

    def _evolution_callback(self, gen, total_gens, best, stats):
        pct = int((gen + 1) / total_gens * 100)
        msg = (f"Gen {gen}/{total_gens-1} | "
               f"Best: {stats['best_fitness']:.4f} | "
               f"Avg: {stats['avg_fitness']:.4f} | "
               f"Specs met: {stats['specs_met']}/{stats['total_specs']}")
        wx.CallAfter(self._update_evo_ui, pct, msg)

    def _update_evo_ui(self, pct, msg):
        self.progress.SetValue(pct)
        self.gen_label.SetLabel(msg)
        self.evo_log.AppendText(msg + "\n")

    def _evolution_complete(self, top5):
        self.running = False
        self.evolve_btn.Enable(True)
        self.stop_btn.Enable(False)
        self.progress.SetValue(100)
        self.gen_label.SetLabel("Evolution complete!")
        self.evo_log.AppendText("\n=== Evolution complete ===\n")
        self._populate_results()
        self.notebook.SetSelection(3)

    def _evolution_error(self, error_msg):
        self.running = False
        self.evolve_btn.Enable(True)
        self.stop_btn.Enable(False)
        wx.MessageBox(f"Evolution error:\n{error_msg}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_stop(self, event):
        if self.ga:
            self.ga.stop()
        self.gen_label.SetLabel("Stopping...")

    def _populate_results(self):
        self.results_list.DeleteAllItems()
        self.spec_results_list.DeleteAllItems()
        if not self.ga or not self.ga.best_individual:
            return
        diffs = self.ga.get_diff()
        for d in diffs:
            idx = self.results_list.InsertItem(self.results_list.GetItemCount(), d["ref"])
            self.results_list.SetItem(idx, 1, d["type"])
            self.results_list.SetItem(idx, 2, d["original_value"])
            self.results_list.SetItem(idx, 3, d["new_value"])
            self.results_list.SetItem(idx, 4, f"{d['change_pct']:+.1f}%")
        best = self.ga.best_individual
        for name, info in best.details.items():
            idx = self.spec_results_list.InsertItem(self.spec_results_list.GetItemCount(), name)
            self.spec_results_list.SetItem(idx, 1, f"{info['operator']} {info['target']}")
            m = info.get("measured")
            self.spec_results_list.SetItem(idx, 2, f"{m:.4g}" if m is not None else "N/A")
            self.spec_results_list.SetItem(idx, 3, "✅" if info.get("met") else "❌")

    def _on_apply(self, event):
        if not self.ga or not self.ga.best_individual:
            wx.MessageBox("No results to apply.", "Error", wx.OK | wx.ICON_ERROR)
            return
        path = self.netlist_path_ctrl.GetValue().strip()
        new_netlist = self.parser.generate_modified_netlist(self.ga.best_individual.genes)
        backup_path = path + ".bak"
        try:
            import shutil
            shutil.copy2(path, backup_path)
            with open(path, "w") as f:
                f.write(new_netlist)
            wx.MessageBox(f"Netlist updated!\nBackup saved: {backup_path}", "Applied",
                          wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"Error applying: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_export(self, event):
        if not self.ga or not self.ga.best_individual:
            wx.MessageBox("No results to export.", "Error", wx.OK | wx.ICON_ERROR)
            return
        dlg = wx.FileDialog(self, "Save Optimized Netlist", wildcard="SPICE files (*.cir)|*.cir",
                            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            new_netlist = self.parser.generate_modified_netlist(self.ga.best_individual.genes)
            with open(dlg.GetPath(), "w") as f:
                f.write(new_netlist)
            wx.MessageBox("Exported!", "Success", wx.OK | wx.ICON_INFORMATION)
        dlg.Destroy()

    def _on_report(self, event):
        if not self.ga:
            wx.MessageBox("Run evolution first.", "Error", wx.OK | wx.ICON_ERROR)
            return
        report = ReportGenerator(self.ga, self.project_path)
        path = report.generate()
        wx.MessageBox(f"Report saved:\n{path}", "Report Generated", wx.OK | wx.ICON_INFORMATION)
        try:
            import webbrowser
            webbrowser.open(path)
        except Exception:
            pass

    def _on_save_settings(self, event):
        for key, (ctrl, vtype) in self.setting_ctrls.items():
            val = ctrl.GetValue().strip()
            try:
                if vtype == int:
                    self.config.set(key, int(val))
                elif vtype == float:
                    self.config.set(key, float(val))
                else:
                    self.config.set(key, val)
            except ValueError:
                pass
        self.config.save()
        wx.MessageBox("Settings saved!", "Success", wx.OK | wx.ICON_INFORMATION)
