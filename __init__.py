import pcbnew
import os
import wx


class CircuitDNAPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Circuit DNA"
        self.category = "Simulation"
        self.description = "Genetic Algorithm-based circuit optimizer. Evolves component values to meet user-defined performance specs using ngspice simulation."
        self.show_toolbar_button = True

    def Run(self):
       from .main_window import MainWindow
       board = pcbnew.GetBoard()
       if board is None:
            wx.MessageBox("No board is currently open.", "Circuit DNA", wx.OK | wx.ICON_ERROR)
            return
       project_path = os.path.dirname(board.GetFileName())
       dlg = MainWindow(None, project_path)
       dlg.ShowModal()
       dlg.Destroy()


CircuitDNAPlugin().register()
