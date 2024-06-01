import math
import pathlib as pl
import numpy as np
from time import sleep
import pyqtgraph as pg
from loguru import logger
from PyQt5 import uic, QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PyQt5.QtWidgets import QWidget, QMainWindow


pg.setConfigOption('foreground', 'k')
pg.setConfigOption('background', (255, 255, 255, 0))

_grid_10x10 = '10x10'
_grid_25x25 = '25x25'
_grid_50x50 = '50x50'
_grid_custom = 'Custom'


class _RectItem(pg.GraphicsObject):
    def __init__(self, rect, parent=None):
        super().__init__(parent)
        self._rect = rect
        self.picture = QtGui.QPicture()
        self._generate_picture()

    @property
    def rect(self):
        return self._rect

    def _generate_picture(self):
        painter = QtGui.QPainter(self.picture)
        painter.setPen(pg.mkPen("w"))
        painter.setBrush(pg.mkBrush("k"))
        painter.drawRect(self.rect)
        painter.end()

    def paint(self, painter, option, widget=None):
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())


class GameGridPlot:
    def __init__(self, widget: QWidget, clickedFnc) -> None:
        self._clickedFnc = clickedFnc
        self.plot_graph = pg.PlotWidget()
        self.plot_graph.setAspectLocked(lock=True, ratio=1)
        self.plot_graph.getPlotItem().hideAxis('bottom')
        self.plot_graph.getPlotItem().hideAxis('left')
        self.plot_graph.setMenuEnabled(False)
        self.plot_graph.setMouseEnabled(x=False, y=False)
        self.plot_graph.hideButtons()
        widget.addWidget(self.plot_graph)
        self.size = None
        self.grid = []

        self.plot_graph.scene().sigMouseClicked.connect(self._mouse_clicked)

    def set_size(self, size: tuple[int, int]):
        self.size = size
        self.plot_graph.clear()
        pen = pg.mkPen('k', width=2)
        for i in range(-1, size[0]):
            self.plot_graph.plot([i+1, i+1], [0, size[1]], pen=pen)
        for i in range(-1, size[1]):
            self.plot_graph.plot([0, size[0]], [i+1, i+1], pen=pen)
        self.grid = []
        for i in range(self.size[0]):
            self.grid.append([])
            for j in range(self.size[1]):
                self.grid[-1].append(None)

    def select_cell(self, pos: tuple[int, int]):
        self._validate_pos(pos)
        if self.grid[pos[0]][pos[1]] is not None:
            # remove existing square
            logger.warning(f"Cell {pos} already selected")
        
        rect = _RectItem(QtCore.QRectF(pos[0], pos[1], 1, 1))
        self.grid[pos[0]][pos[1]] = rect
        self.plot_graph.addItem(rect)

    def unselect_cell(self, pos: tuple[int, int]):
        self._validate_pos(pos)
        rect = self.grid[pos[0]][pos[1]]
        self.plot_graph.removeItem(rect)
        self.grid[pos[0]][pos[1]] = None

    def _validate_pos(self, pos: tuple[int, int]):
        if len(pos) != 2:
            raise ValueError
        if pos[0] < 0 or pos[1] < 0:
            raise ValueError
        if pos[0] >= self.size[0] or pos[1] >= self.size[1]:
            raise ValueError
        
    def _mouse_clicked(self, x):
        if self.size is None:
            return

        pos = self.plot_graph.getPlotItem().getViewBox().mapSceneToView(x.scenePos())
        x = math.floor(pos.x())
        y = math.floor(pos.y())

        if x < 0 or y < 0:
            return
        if x >= self.size[0] or y >= self.size[1]:
            return

        self._clickedFnc((x, y))


class GameGrid:
    def __init__(self, clickedFnc, size: tuple[int, int] = (10, 10)) -> None:
        self.grid: np.ndarray = None
        self.plot: GameGridPlot = None
        self.size = size
        self._clickedFnc = clickedFnc

        self.set_size(size)

    def init_plot(self, widget: QWidget):
        self.plot = GameGridPlot(widget, self._clickedFnc)
        self.set_size(self.size)
    
    def set_size(self, size: tuple[int, int]):
        """ Change size of game grid """
        self.grid = np.zeros(size)
        self.size = size
        if self.plot is not None:
            self.plot.set_size(size)

    def cell_state(self, pos: tuple[int, int]):
        return self.grid[pos[0]][pos[1]]

    def select_cell(self, pos: tuple[int, int]):
        """ Make cell black """
        self.grid[pos[0]][pos[1]] = 1
        self.plot.select_cell(pos)

    def unselect_cell(self, pos: tuple[int, int]):
        """ Make cell white """
        self.grid[pos[0]][pos[1]] = 0
        self.plot.unselect_cell(pos)

    def step_next(self):
        new_alive = []
        new_dead = []

        for i in range(self.grid.shape[0]):
            for j in range(self.grid.shape[1]):
                n_alive = self._neighs_alive((i, j))
                if self.grid[i][j] == 1:
                    if n_alive not in [2, 3]:
                        new_dead.append((i, j))
                elif self.grid[i][j] == 0:
                    if n_alive == 3:
                        new_alive.append((i, j))
                else:
                    raise ValueError

        for pos in new_dead:
            self.plot.unselect_cell(pos)
            self.grid[pos[0]][pos[1]] = 0
        for pos in new_alive:
            self.plot.select_cell(pos)
            self.grid[pos[0]][pos[1]] = 1

    def _neighs_alive(self, pos: tuple[int, int]) -> int:
        x, y = pos
        n_alive = 0
        if x > 0:
            n_alive += self.grid[x-1][y]
        if x < self.grid.shape[0] - 1:
            n_alive += self.grid[x+1][y]
        if y > 0:
            n_alive += self.grid[x][y-1]
        if y < self.grid.shape[1] - 1:
            n_alive += self.grid[x][y+1]

        if y > 0 and x > 0:
            n_alive += self.grid[x-1][y-1]
        if x < self.grid.shape[0] - 1 and y < self.grid.shape[1] - 1:
            n_alive += self.grid[x+1][y+1]

        if y > 0 and x < self.grid.shape[0] - 1:
            n_alive += self.grid[x+1][y-1]
        if x > 0 and y < self.grid.shape[1] - 1:
            n_alive += self.grid[x-1][y+1]

        return n_alive

    def reset(self):
        for i in range(self.grid.shape[0]):
            for j in range(self.grid.shape[1]):
                pos = (i, j)
                self.plot.unselect_cell(pos)
        self.grid = np.zeros(self.size)


class _Worker(QObject):
    tick = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = False
        self.turn_time = 1

    def run(self):
        """Long-running task."""
        while True:
            sleep(1 / self.turn_time)
            if self.running:
                self.tick.emit()


class WidgetController(QWidget):
    def __init__(self, parent=None) -> None:
        super(WidgetController, self).__init__(parent=parent)
        widget_path = pl.Path(__file__).parent / 'game_of_life.ui'
        uic.loadUi(widget_path, self)
        self.parent = parent
        self.game_grid = GameGrid(self._grid_clicked)
        self.game_grid.init_plot(self.widget_main)

        self._connect()

        self.thread = QThread()
        # Step 3: Create a worker object
        self.worker = _Worker()
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.tick.connect(self.game_grid.step_next)
        # Step 6: Start the thread
        self.thread.start()

    def _connect(self, connect: bool = True):
        self._connect_spins()
        self._connect_speed_buttons()
        self.pushButton_next.clicked.connect(self.game_grid.step_next)
        self.pushButton_reset.clicked.connect(self.game_grid.reset)
        self.pushButton_start_stop.clicked.connect(self._start_stop_clicked)
        self.comboBox.currentTextChanged.connect(self._combo_changed)

    def _connect_spins(self, connect: bool = True):
        if connect:
            self.spinBox_columns.valueChanged.connect(self._spins_changed)
            self.spinBox_rows.valueChanged.connect(self._spins_changed)
        else:
            self.spinBox_rows.disconnect()
            self.spinBox_columns.disconnect()

    def _connect_speed_buttons(self, connect: bool = True):
        if connect:
            self.doubleSpinBox.valueChanged.connect(self._speed_changed)
        else:
            self.doubleSpinBox.disconnect()

    def _grid_clicked(self, pos: tuple[int, int]):
        cell_state = self.game_grid.cell_state(pos)
        if cell_state == 0:
            self.game_grid.select_cell(pos)
        elif cell_state == 1:
            self.game_grid.unselect_cell(pos)
        else:
            raise ValueError

    def _combo_changed(self, a):
        if a == _grid_10x10:
            x, y = 10, 10
        elif a == _grid_25x25:
            x, y = 25, 25
        elif a == _grid_50x50:
            x, y = 50, 50
        elif a == _grid_custom:
            return
        else:
            raise ValueError

        self._connect_spins(False)
        self.spinBox_columns.setValue(x)
        self.spinBox_rows.setValue(y)
        self._connect_spins(True)
        self._spins_changed()

    def _spins_changed(self, _=None):
        x = self.spinBox_columns.value()
        y = self.spinBox_rows.value()
        self.game_grid.set_size((x, y))

    def _start_stop_clicked(self):
        self.worker.running = not self.worker.running

    def _speed_changed(self, val: float):
        self.worker.turn_time = val


class Main(QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        window_path = pl.Path(__file__).parent / 'main_window.ui'
        uic.loadUi(window_path, self)
        widget = WidgetController(parent=self)
        self.stackedWidget.addWidget(widget)
        self.show()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    main = Main()
    app.exec_()
