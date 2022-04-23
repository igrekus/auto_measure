from pathlib import Path

import pandas
import pyqtgraph as pg

from PyQt5.QtWidgets import QGridLayout, QWidget, QLabel
from PyQt5.QtCore import Qt


# https://www.learnpyqt.com/tutorials/plotting-pyqtgraph/
# https://pyqtgraph.readthedocs.io/en/latest/introduction.html#what-is-pyqtgraph

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
          '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']


class PrimaryPlotWidget(QWidget):
    label_style = {'color': 'k', 'font-size': '15px'}

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)

        self._controller = controller   # TODO decouple from controller, use explicit result passing
        self.only_main_states = False

        self._grid = QGridLayout()

        self._win = pg.GraphicsLayoutWidget(show=True)
        self._win.setBackground('w')

        self._stat_label = QLabel('Mouse:')
        self._stat_label.setAlignment(Qt.AlignRight)

        self._grid.addWidget(self._stat_label, 0, 0)
        self._grid.addWidget(self._win, 1, 0)

        self._plot_00 = self._win.addPlot(row=0, col=0)
        self._plot_01 = self._win.addPlot(row=0, col=1)
        self._plot_10 = self._win.addPlot(row=1, col=0)
        self._plot_11 = self._win.addPlot(row=1, col=1)

        self._curves_00 = dict()
        self._curves_01 = dict()
        self._curves_10 = dict()
        self._curves_11 = dict()

        file_name1 = Path('./tables/plot1.xlsx')
        file_name2 = Path('./tables/plot2.xlsx')
        file_name3 = Path('./tables/plot3.xlsx')
        file_name4 = Path('./tables/plot4.xlsx')

        present_1 = file_name1.is_file()
        present_2 = file_name2.is_file()
        present_3 = file_name3.is_file()
        present_4 = file_name4.is_file()

        df1 = pandas.read_excel(file_name1)
        df2 = pandas.read_excel(file_name2) if present_2 else None
        df3 = pandas.read_excel(file_name3) if present_3 else None
        df4 = pandas.read_excel(file_name4) if present_4 else None

        self._labels = [
            {
                'left': df1.columns[1] if present_1 else '',
                'bottom': df1.columns[2] if present_1 else '',
                'prefix': df1.columns[0].split('#')[0] if present_1 else '',
                'suffix': df1.columns[0].split('#')[1] if present_1 else '',
            },            {
                'left': df2.columns[1] if present_2 else '',
                'bottom': df2.columns[2] if present_2 else '',
                'prefix': df2.columns[0].split('#')[0] if present_2 else '',
                'suffix': df2.columns[0].split('#')[1] if present_2 else '',
            },
            {
                'left': df3.columns[1] if present_3 else '',
                'bottom': df3.columns[2] if present_3 else '',
                'prefix': df3.columns[0].split('#')[0] if present_3 else '',
                'suffix': df3.columns[0].split('#')[1] if present_3 else '',
            },
            {
                'left': df4.columns[1] if present_4 else '',
                'bottom': df4.columns[2] if present_4 else '',
                'prefix': df4.columns[0].split('#')[0] if present_4 else '',
                'suffix': df4.columns[0].split('#')[1] if present_4 else '',
            },
        ]

        self._plot_00.setLabel('left', self._labels[0]['left'], **self.label_style)
        self._plot_00.setLabel('bottom', self._labels[0]['bottom'], **self.label_style)
        self._plot_00.enableAutoRange('x')
        self._plot_00.enableAutoRange('y')
        self._plot_00.showGrid(x=True, y=True)
        self._vb_00 = self._plot_00.vb
        rect = self._vb_00.viewRect()
        self._plot_00.addLegend(offset=(rect.x() + 30, rect.y() + 30))
        self._vLine_00 = pg.InfiniteLine(angle=90, movable=False)
        self._hLine_00 = pg.InfiniteLine(angle=0, movable=False)
        self._plot_00.addItem(self._vLine_00, ignoreBounds=True)
        self._plot_00.addItem(self._hLine_00, ignoreBounds=True)
        self._proxy_00 = pg.SignalProxy(self._plot_00.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved_00)

        self._plot_01.setLabel('left', self._labels[1]['left'], **self.label_style)
        self._plot_01.setLabel('bottom', self._labels[1]['bottom'], **self.label_style)
        self._plot_01.enableAutoRange('x')
        self._plot_01.enableAutoRange('y')
        self._plot_01.showGrid(x=True, y=True)
        self._vb_01 = self._plot_01.vb
        rect = self._vb_01.viewRect()
        self._plot_01.addLegend(offset=(rect.x() + rect.width() - 50, rect.y() + 30))
        self._vLine_01 = pg.InfiniteLine(angle=90, movable=False)
        self._hLine_01 = pg.InfiniteLine(angle=0, movable=False)
        self._plot_01.addItem(self._vLine_01, ignoreBounds=True)
        self._plot_01.addItem(self._hLine_01, ignoreBounds=True)
        self._proxy_01 = pg.SignalProxy(self._plot_01.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved_01)

        self._plot_10.setLabel('left', self._labels[2]['left'], **self.label_style)
        self._plot_10.setLabel('bottom', self._labels[2]['bottom'], **self.label_style)
        self._plot_10.enableAutoRange('x')
        self._plot_10.enableAutoRange('y')
        self._plot_10.showGrid(x=True, y=True)
        self._vb_02 = self._plot_10.vb
        rect = self._vb_02.viewRect()
        self._plot_10.addLegend(offset=(rect.x() + rect.width() - 50, rect.y() + 30))
        self._vLine_02 = pg.InfiniteLine(angle=90, movable=False)
        self._hLine_02 = pg.InfiniteLine(angle=0, movable=False)
        self._plot_10.addItem(self._vLine_02, ignoreBounds=True)
        self._plot_10.addItem(self._hLine_02, ignoreBounds=True)
        self._proxy_02 = pg.SignalProxy(self._plot_10.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved_02)

        self._plot_11.setLabel('left', self._labels[3]['left'], **self.label_style)
        self._plot_11.setLabel('bottom', self._labels[3]['bottom'], **self.label_style)
        self._plot_11.enableAutoRange('x')
        self._plot_11.enableAutoRange('y')
        self._plot_11.showGrid(x=True, y=True)
        self._vb_12 = self._plot_11.vb
        rect = self._vb_12.viewRect()
        self._plot_11.addLegend(offset=(rect.x() + rect.width() - 50, rect.y() + 30))
        self._vLine_12 = pg.InfiniteLine(angle=90, movable=False)
        self._hLine_12 = pg.InfiniteLine(angle=0, movable=False)
        self._plot_11.addItem(self._vLine_12, ignoreBounds=True)
        self._plot_11.addItem(self._hLine_12, ignoreBounds=True)
        self._proxy_12 = pg.SignalProxy(self._plot_11.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved_12)

        if not present_1:
            self._plot_01.hide()

        if not present_2:
            self._plot_01.hide()

        if not present_3:
            self._plot_10.hide()

        if not present_4:
            self._plot_11.hide()

        self.setLayout(self._grid)

    def mouseMoved_00(self, event):
        pos = event[0]
        if self._plot_00.sceneBoundingRect().contains(pos):
            mouse_point = self._vb_00.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            self._vLine_00.setPos(x)
            self._hLine_00.setPos(y)
            if not self._curves_00:
                return

            self._stat_label.setText(_label_text(x, y, [
                [p, curve.yData[_find_value_index(curve.xData, x)]]
                for p, curve in self._curves_00.items()
            ]))

    def mouseMoved_01(self, event):
        pos = event[0]
        if self._plot_01.sceneBoundingRect().contains(pos):
            mouse_point = self._vb_01.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            self._vLine_01.setPos(x)
            self._hLine_01.setPos(y)
            if not self._curves_01:
                return

            self._stat_label.setText(_label_text(x, y, [
                [p, curve.yData[_find_value_index(curve.xData, x)]]
                for p, curve in self._curves_01.items()
            ]))

    def mouseMoved_02(self, event):
        pos = event[0]
        if self._plot_10.sceneBoundingRect().contains(pos):
            mouse_point = self._vb_02.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            self._vLine_02.setPos(x)
            self._hLine_02.setPos(y)
            if not self._curves_10:
                return

            self._stat_label.setText(_label_text(x, y, [
                [p, curve.yData[_find_value_index(curve.xData, x)]]
                for p, curve in self._curves_10.items()
            ]))

    def mouseMoved_12(self, event):
        pos = event[0]
        if self._plot_11.sceneBoundingRect().contains(pos):
            mouse_point = self._vb_12.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            self._vLine_12.setPos(x)
            self._hLine_12.setPos(y)
            if not self._curves_11:
                return

            self._stat_label.setText(_label_text(x, y, [
                [p, curve.yData[_find_value_index(curve.xData, x)]]
                for p, curve in self._curves_11.items()
            ]))

    def clear(self):
        def _remove_curves(plot, curve_dict):
            for _, curve in curve_dict.items():
                plot.removeItem(curve)

        _remove_curves(self._plot_00, self._curves_00)
        _remove_curves(self._plot_01, self._curves_01)
        _remove_curves(self._plot_10, self._curves_10)
        _remove_curves(self._plot_11, self._curves_11)

        self._curves_00.clear()
        self._curves_01.clear()
        self._curves_10.clear()
        self._curves_11.clear()

    def plot(self):
        print('plotting primary stats')
        _plot_curves(self._controller.result.data1, self._curves_00, self._plot_00, prefix=self._labels[0]['prefix'], suffix=self._labels[0]['suffix'])
        _plot_curves(self._controller.result.data2, self._curves_01, self._plot_01, prefix=self._labels[1]['prefix'], suffix=self._labels[1]['suffix'])
        _plot_curves(self._controller.result.data3, self._curves_10, self._plot_10, prefix=self._labels[2]['prefix'], suffix=self._labels[2]['suffix'])
        _plot_curves(self._controller.result.data4, self._curves_11, self._plot_11, prefix=self._labels[3]['prefix'], suffix=self._labels[3]['suffix'])


def _plot_curves(datas, curves, plot, prefix='', suffix=''):
    for pow_lo, data in datas.items():
        curve_xs, curve_ys = zip(*data)
        try:
            curves[pow_lo].setData(x=curve_xs, y=curve_ys)
        except KeyError:
            try:
                color = colors[len(curves)]
            except IndexError:
                color = colors[len(curves) - len(colors)]
            curves[pow_lo] = pg.PlotDataItem(
                curve_xs,
                curve_ys,
                pen=pg.mkPen(
                    color=color,
                    width=2,
                ),
                symbol='o',
                symbolSize=5,
                symbolBrush=color,
                name=f'{prefix}{pow_lo}{suffix}'
            )
            plot.addItem(curves[pow_lo])


def _label_text(x, y, vals):
    vals_str = ''.join(f'   <span style="color:{colors[i]}">{p:0.1f}={v:0.2f}</span>' for i, (p, v) in enumerate(vals))
    return f"<span style='font-size: 8pt'>x={x:0.2f},   y={y:0.2f}   {vals_str}</span>"


def _find_value_index(freqs: list, freq):
    return min(range(len(freqs)), key=lambda i: abs(freqs[i] - freq))
